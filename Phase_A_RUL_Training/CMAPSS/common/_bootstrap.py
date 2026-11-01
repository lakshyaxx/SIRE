"""Make the CMAPSS `common` package importable from numeric model folders."""

from __future__ import annotations

import sys
from pathlib import Path

TRACK_ROOT = Path(__file__).resolve().parents[1]
if str(TRACK_ROOT) not in sys.path:
    sys.path.insert(0, str(TRACK_ROOT))
