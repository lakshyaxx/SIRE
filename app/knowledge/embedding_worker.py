"""Offline ONNX mean-pooling worker; no remote model code or hub loading."""

import json
import importlib
import sys
import time
from app.core.config import ROOT
from app.knowledge.embeddings import POLICY, model_files
from app.core.process_metrics import usage


def create_engine() -> tuple:
    """Create the pinned CPU tokenizer/session once; never retain query histories."""
    sys.path.insert(0, str(ROOT / POLICY["dependencies"]))
    import onnxruntime as ort
    from tokenizers import Tokenizer

    ort.disable_telemetry_events()

    paths = model_files()
    tokenizer = Tokenizer.from_file(str(paths["tokenizer.json"]))
    tokenizer.enable_truncation(max_length=POLICY["max_tokens"])
    tokenizer.enable_padding()
    options = ort.SessionOptions()
    options.intra_op_num_threads = POLICY["threads"]
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(paths["onnx/model_quint8_avx2.onnx"]),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    return tokenizer, session, ort.__version__


def embed(texts: list[str], engine: tuple) -> dict:
    """Generate fresh actual vectors with unchanged truncation, pooling and normalization."""
    import numpy as np

    tokenizer, session, version = engine
    began = time.perf_counter()
    vectors = []
    truncated = 0
    for offset in range(0, len(texts), POLICY["batch_size"]):
        tokens = tokenizer.encode_batch(texts[offset : offset + POLICY["batch_size"]])
        truncated += sum(bool(t.overflowing) for t in tokens)
        inputs = {
            "input_ids": np.asarray([t.ids for t in tokens], dtype=np.int64),
            "attention_mask": np.asarray(
                [t.attention_mask for t in tokens], dtype=np.int64
            ),
            "token_type_ids": np.asarray([t.type_ids for t in tokens], dtype=np.int64),
        }
        states = session.run(
            None, {i.name: inputs[i.name] for i in session.get_inputs()}
        )[0]
        if states.ndim != 3 or states.shape[-1] != POLICY["dimensions"]:
            raise ValueError("Unsupported ONNX output contract")
        mask = inputs["attention_mask"][..., None]
        pooled = (states * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        pooled = pooled / np.maximum(
            np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12
        )
        if not np.isfinite(pooled).all():
            raise ValueError("Non-finite embeddings")
        vectors.extend(pooled.astype(np.float32).tolist())
    return {
        "vectors": vectors,
        "model": POLICY["model_id"],
        "revision": POLICY["revision"],
        "provider": "onnxruntime-" + version,
        "execution_providers": session.get_providers(),
        "inference_seconds": time.perf_counter() - began,
        "truncated_inputs": truncated,
        "pooling": "attention-masked mean then L2 normalization",
        "resources": usage(),
    }


def main() -> None:
    """Serve original one-shot execution or bounded owned JSON-file descriptors."""
    engine = None
    native_import_seconds = 0.0
    if "--resident" in sys.argv:
        # Windows native DLL initialization can wait on CRT stdin locks. Complete
        # imports before the pipe-watcher thread starts blocking on stdin.
        importing = time.perf_counter()
        sys.path.insert(0, str(ROOT / POLICY["dependencies"]))
        for dependency in ["numpy", "onnxruntime", "tokenizers"]:
            importlib.import_module(dependency)

        native_import_seconds = time.perf_counter() - importing

    def execute(payload: dict) -> dict:
        nonlocal engine
        began = time.perf_counter()
        cpu = usage()["cpu_seconds"]
        reused = engine is not None
        if engine is None:
            engine = create_engine()
        loaded = time.perf_counter()
        result = embed(payload["texts"], engine)
        result["model_load_seconds"] = loaded - began
        result["model_reused"] = reused
        result["native_import_seconds"] = 0.0 if reused else native_import_seconds
        result["resources"]["request_cpu_seconds"] = usage()["cpu_seconds"] - cpu
        result["resources"][
            "scope"
        ] = "Observed process lifetime peak RSS/CPU plus request CPU delta; retained peak is not per-query peak."
        return result

    if "--resident" in sys.argv:
        from app.core.worker_pool import serve

        serve(execute)
    else:
        print(json.dumps(execute(json.load(sys.stdin)), allow_nan=False))


if __name__ == "__main__":
    main()
