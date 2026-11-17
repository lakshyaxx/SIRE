"""Real legacy parity, artifact integrity and public model contract checks."""

import json
import os
import subprocess
import sys

import pytest

from app.core.config import ROOT
from app.core.errors import SireError
from app.prediction.hub import catalog, entry, predict, verify_integrity


def test_registry_catalog_and_integrity():
    items = catalog()
    assert len({m["model_id"] for m in items}) == len(items)
    assert {m["dataset"] for m in items} == {"FD001", "FD002", "FD003", "FD004"}
    assert {m["family"][:2] for m in items} >= {f"{i:02}" for i in range(1, 10)}
    assert verify_integrity() > 0


def test_native_parity(history):
    identifier = "fd001-01_lightgbm-s42"
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        CUDA_VISIBLE_DEVICES="",
        OMP_NUM_THREADS="2",
        MPLCONFIGDIR=str(ROOT / ".runtime/matplotlib"),
    )
    # Independent direct legacy call bypasses both the hub and its worker adapter.
    code = """
import importlib.util,json,pathlib,sys,pandas as pd
p=pathlib.Path.cwd()/'ml/artifacts/cmapss/models/01_lightgbm/predict.py'
s=importlib.util.spec_from_file_location('direct_parity',p)
m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
h=pd.DataFrame(json.load(sys.stdin)); print('DIRECT='+json.dumps(m.load_model('FD001',42).predict_rul(h)))
"""
    direct = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        input=history.to_json(orient="records"),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    legacy = json.loads(
        next(
            line[7:]
            for line in direct.stdout.splitlines()
            if line.startswith("DIRECT=")
        )
    )
    wrapped = predict(identifier, "FD001", history)
    assert wrapped["rul"] == pytest.approx(legacy["rul"], abs=1e-10, rel=0)
    assert wrapped["version"] == legacy["version"]
    assert wrapped["top_contributors"] == legacy["top_contributors"]


def test_mismatch_and_unknown(history):
    with pytest.raises(SireError):
        predict("fd001-01_lightgbm-s42", "FD002", history)
    with pytest.raises(SireError):
        entry("../../fake.py")
    with pytest.raises(SireError):
        predict("fd001-06_autoencoder-s42", "FD001", history)


def test_tamper_is_detected(tmp_path, monkeypatch):
    import app.prediction.hub as hub

    path = tmp_path / "model.txt"
    path.write_bytes(b"test-only corrupt artifact")
    monkeypatch.setattr(hub, "ROOT", tmp_path)
    monkeypatch.setattr(
        hub,
        "manifest",
        lambda: {"integrity_files": [{"path": "model.txt", "sha256": "wrong"}]},
    )
    with pytest.raises(SireError, match="bytes have changed"):
        verify_integrity()
