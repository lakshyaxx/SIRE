"""Actual endpoint rejection for explicit test-only unrelated schema, without model substitution."""

from scripts.stress_lab.supplemental import domain_boundary


def test_generic_industrial_csv_cannot_run_a_nasa_model_even_when_declared_compatible(
    v2client,
):
    proof = domain_boundary(
        v2client,
        b"asset_id,timestamp_utc,oil_pressure_bar\nTEST-ONLY,2026-01-01T00:00:00Z,2.0\n",
        "test-only-unrelated.csv",
    )
    assert proof["passed"] and proof["prediction_eligible"] is False
    assert proof["prediction_rows_before"] == proof["prediction_rows_after"] == 0
