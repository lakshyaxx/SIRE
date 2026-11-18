"""Offline ONNX mean-pooling worker; no remote model code or hub loading."""

import json
import sys
import time
from app.core.config import ROOT
from app.knowledge.embeddings import POLICY, model_files
from app.core.process_metrics import usage


def main() -> None:
    """Embed bounded actual text using pinned tokenizer/ONNX bytes and CPU only."""
    sys.path.insert(0, str(ROOT / POLICY["dependencies"]))
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    ort.disable_telemetry_events()

    texts = json.load(sys.stdin)["texts"]
    paths = model_files()
    start = time.perf_counter()
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
    loaded = time.perf_counter()
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
    print(
        json.dumps(
            {
                "vectors": vectors,
                "model": POLICY["model_id"],
                "revision": POLICY["revision"],
                "provider": "onnxruntime-" + ort.__version__,
                "execution_providers": session.get_providers(),
                "model_load_seconds": loaded - start,
                "inference_seconds": time.perf_counter() - loaded,
                "truncated_inputs": truncated,
                "pooling": "attention-masked mean then L2 normalization",
                "resources": usage(),
            },
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
