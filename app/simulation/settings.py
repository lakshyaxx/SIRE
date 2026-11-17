"""Public simulator/analytics policy only; contains no hidden scenario assignments."""

import yaml
from app.core.config import ROOT

CONFIG = yaml.safe_load((ROOT / "config/simulation.yaml").read_text())
