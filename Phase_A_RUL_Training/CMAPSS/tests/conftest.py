"""Ensure tests import the track-local common package, not another track's code."""

import sys
from pathlib import Path

TRACK_ROOT = Path(__file__).resolve().parents[1]
if str(TRACK_ROOT) not in sys.path:
    sys.path.insert(0, str(TRACK_ROOT))
