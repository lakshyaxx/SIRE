"""Verify immutable inputs and recorded, actually executed pre/post-cutover parity."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.prediction.hub import catalog, verify_integrity


def main() -> None:
    """Fail on changed bytes or missing/failed primary migration comparisons."""
    count = verify_integrity()
    models = catalog()
    assert all(row["status"] == "ready" for row in models)
    parity = [
        row["verification"]["parity"]
        for row in models
        if row["verification"].get("parity")
    ]
    assert len(parity) == 44
    assert all(row["absolute_difference"] <= row["tolerance"] for row in parity)
    cpu = json.loads((ROOT / "ml/registry/legacy_cpu_reference.json").read_text())
    assert cpu["absolute_difference"] == 0
    print(
        json.dumps(
            {
                "integrity_files": count,
                "inferred_routes": len(models),
                "recorded_primary_parity_passes": len(parity),
                "fresh_inference_this_command": False,
                "legacy_cpu_reference": cpu,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
