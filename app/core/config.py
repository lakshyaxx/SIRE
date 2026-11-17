"""Relocatable application settings; no imports from archived research."""

import os
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = yaml.safe_load((ROOT / "config/app.yaml").read_text(encoding="utf-8"))
for key, env in {
    "ollama_base_url": "OLLAMA_BASE_URL",
    "text_model": "SIRE_TEXT_MODEL",
    "vision_model": "SIRE_VISION_MODEL",
}.items():
    if env in os.environ:
        SETTINGS[key] = os.environ[env]
TRACK = ROOT / "ml/artifacts/cmapss"
MANIFEST = ROOT / "ml/registry/catalog.json"
STATE = Path(os.environ.get("SIRE_STATE_DIR", str(ROOT / ".runtime/v2")))
_web_name = os.environ.get("SIRE_WEB_BUILD", "dist")
if _web_name not in {"dist", "dist-v3"}:
    raise ValueError("SIRE_WEB_BUILD must be dist or dist-v3")
WEB_DIST = ROOT / "web" / _web_name
