"""Audit threshold false alarms and post-cap onset detection quality."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT.parents[0] / ".venv" / "mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common.config import DATASET_IDS, cmapss_root

SEEDS = (42, 43, 44)
RUL_CAP = 125


def _onset_rows(dataset: str, seed: int) -> pd.DataFrame:
    """Join first-onset diagnostics with true endpoint and onset-cycle RUL."""
    root = cmapss_root()
    output = root / "models" / "06_autoencoder" / "outputs" / dataset / f"seed_{seed}"
    onset = pd.read_csv(output / "onset.csv")
    raw = pd.read_csv(root / "data" / f"test_{dataset}.txt", sep=r"\s+", header=None)
    raw.columns = ["unit", "cycle", "op1", "op2", "op3", *(f"s{i}" for i in range(1, 22))]
    truth = pd.read_csv(root / "data" / f"RUL_{dataset}.txt", sep=r"\s+", header=None, names=["rul_raw"])
    endpoints = raw.groupby("unit", as_index=False).cycle.max().rename(columns={"cycle": "last_observed_cycle"})
    endpoints["rul_raw"] = truth.rul_raw.to_numpy(dtype=float)
    endpoints["failure_cycle_check"] = endpoints.last_observed_cycle + endpoints.rul_raw
    frame = onset.merge(endpoints, on="unit", validate="one_to_one")
    if not np.allclose(frame.failure_cycle, frame.failure_cycle_check):
        raise ValueError(f"Saved failure cycle does not match official test truth for {dataset}/seed{seed}")
    frame["degrades_on_test_horizon"] = frame.rul_raw < RUL_CAP
    frame["true_rul_at_onset"] = frame.failure_cycle - frame.onset_step
    fired = frame.onset_step.notna()
    frame["false_alarm"] = fired & frame.true_rul_at_onset.ge(RUL_CAP)
    frame["detected_after_cap"] = fired & frame.true_rul_at_onset.lt(RUL_CAP)
    frame["lead_time_after_cap_cycles"] = frame.true_rul_at_onset.where(frame.detected_after_cap)
    frame["dataset"] = dataset
    frame["seed"] = seed
    frame["onset_threshold_hi"] = json.loads((output / "health_metrics.json").read_text(encoding="utf-8"))["test_onset"]["onset_threshold_hi"]
    return frame[[
        "dataset", "seed", "unit", "last_observed_cycle", "rul_raw", "degrades_on_test_horizon",
        "onset_step", "true_rul_at_onset", "false_alarm", "detected_after_cap",
        "lead_time_after_cap_cycles", "onset_threshold_hi",
    ]]


def _seed_summary(frame: pd.DataFrame) -> dict[str, float | int | str]:
    """Summarize one dataset/seed using only post-cap detections as hits."""
    degrading = frame.degrades_on_test_horizon
    leads = frame.loc[frame.detected_after_cap, "lead_time_after_cap_cycles"].dropna().to_numpy(dtype=float)
    return {
        "dataset": str(frame.dataset.iloc[0]),
        "seed": int(frame.seed.iloc[0]),
        "n_engines": int(len(frame)),
        "degrading_engines": int(degrading.sum()),
        "onset_fired_engines": int(frame.onset_step.notna().sum()),
        "false_alarm_engines": int(frame.false_alarm.sum()),
        "false_alarm_rate_all_engines": float(frame.false_alarm.mean()),
        "detected_after_cap_engines": int((frame.detected_after_cap & degrading).sum()),
        "detection_rate_degrading_engines": float((frame.detected_after_cap & degrading).sum() / degrading.sum()) if degrading.any() else float("nan"),
        "post_cap_onset_median_lead_cycles": float(np.median(leads)) if leads.size else float("nan"),
        "post_cap_onset_mean_lead_cycles": float(np.mean(leads)) if leads.size else float("nan"),
    }


def _plot_six(dataset: str, seed: int, engine_quality: pd.DataFrame) -> Path:
    """Plot six diagnostic engines, marking the saved first onset when present."""
    root = cmapss_root()
    output = root / "models" / "06_autoencoder" / "outputs" / dataset / f"seed_{seed}"
    health = pd.read_csv(output / "hi_test.csv")
    onset = pd.read_csv(output / "onset.csv").set_index("unit")
    quality = engine_quality.set_index("unit")
    positives = quality.loc[quality.detected_after_cap].index.tolist()[:3]
    non_positives = quality.loc[~quality.detected_after_cap].index.tolist()[:3]
    selected = list(dict.fromkeys(positives + non_positives))
    for unit in quality.index:
        if len(selected) >= 6:
            break
        if unit not in selected:
            selected.append(unit)
    selected = selected[:6]
    threshold = float(quality.onset_threshold_hi.iloc[0])
    fig, axes = plt.subplots(6, 1, figsize=(11, 14), squeeze=False)
    for axis, unit in zip(axes[:, 0], selected):
        series = health.loc[health.unit.eq(unit)].sort_values("step")
        axis.plot(series.step, series.hi, linewidth=1.0, color="tab:blue")
        axis.axhline(threshold, color="tab:red", linestyle="--", linewidth=0.8, label="healthy threshold")
        event = onset.loc[unit, "onset_step"]
        row = quality.loc[unit]
        if pd.notna(event):
            axis.axvline(float(event), color="tab:orange", linestyle=":", linewidth=1.2, label="onset")
            axis.scatter([float(event)], [float(series.loc[series.step.eq(event), "hi"].iloc[0])], color="tab:orange", s=18, zorder=3)
            suffix = f"onset RUL={row.true_rul_at_onset:.0f}; {'false alarm' if row.false_alarm else 'after cap'}"
        else:
            suffix = "no onset"
        axis.set_ylabel(f"Unit {unit}\nHI")
        axis.set_title(suffix, loc="right", fontsize=8)
    axes[-1, 0].set_xlabel("Cycle")
    fig.suptitle(f"{dataset} autoencoder HI and onset (seed {seed}; cap={RUL_CAP})")
    fig.tight_layout()
    plot_path = root / "results" / "figures" / "onset_quality" / f"{dataset}_seed_{seed}.png"
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)
    return plot_path


def main() -> None:
    """Write per-engine onset audit, seed aggregates, and six-engine plots."""
    root = cmapss_root()
    per_engine_frames: list[pd.DataFrame] = []
    seed_rows: list[dict[str, float | int | str]] = []
    plot_paths: list[Path] = []
    for dataset in DATASET_IDS:
        for seed in SEEDS:
            frame = _onset_rows(dataset, seed)
            per_engine_frames.append(frame)
            seed_rows.append(_seed_summary(frame))
            if seed == 42:
                plot_paths.append(_plot_six(dataset, seed, frame))
    per_engine = pd.concat(per_engine_frames, ignore_index=True)
    seed_summary = pd.DataFrame(seed_rows)
    per_engine.to_csv(root / "results" / "onset_quality_by_engine.csv", index=False)
    seed_summary.to_csv(root / "results" / "onset_quality_by_seed.csv", index=False)
    report = root / "results" / "REPORT.md"
    original = report.read_text(encoding="utf-8")
    marker = "\n## Autoencoder onset quality check\n"
    if marker in original:
        original = original.split(marker, 1)[0]
    lines = [
        "", "## Autoencoder onset quality check", "",
        f"The detection rule is unchanged (HI threshold with {5}-consecutive-step requirement); false alarms are first onsets at true RUL >= {RUL_CAP}. An engine is in the degrading denominator when its true RUL at the final observed test cycle is < {RUL_CAP}. Only first onsets after the cap count as detections and contribute lead time. Per-engine rows across all seeds are saved in `results/onset_quality_by_engine.csv`; seed summaries are in `results/onset_quality_by_seed.csv`.",
        "", "Per-seed metrics below are mean +/- sample SD over seeds 42, 43, 44.", "",
        "| Dataset | Engines with RUL < cap | False alarms / all engines | Degrading-engine detection rate | Median post-cap lead (cycles) | Mean post-cap lead (cycles) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for dataset in DATASET_IDS:
        sub = seed_summary.loc[seed_summary.dataset.eq(dataset)]
        def fmt(column: str, percent: bool = False) -> str:
            vals = sub[column].dropna().to_numpy(dtype=float)
            mean = float(np.mean(vals)) if vals.size else float("nan")
            std = float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0
            if percent:
                return f"{mean:.1%} +/- {std:.1%}"
            return f"{mean:.2f} +/- {std:.2f}"
        lines.append(
            f"| {dataset} | {fmt('degrading_engines')} | "
            f"{fmt('false_alarm_rate_all_engines', True)} | "
            f"{fmt('detection_rate_degrading_engines', True)} | "
            f"{fmt('post_cap_onset_median_lead_cycles')} | "
            f"{fmt('post_cap_onset_mean_lead_cycles')} |"
        )
    lines.extend(["", "False alarm counts are the number of first-onset fires before true RUL falls below the cap. Lead-time summaries exclude these false alarms and engines with no onset. The plots show six selected diagnostic engines for each subset using seed 42; dotted orange lines mark the saved first onset, and dashed red lines mark the threshold.", ""])
    for path in plot_paths:
        lines.append(f"![{path.stem}](figures/onset_quality/{path.name})")
    report.write_text(original.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(seed_summary.to_string(index=False))
    print("Plots:")
    for path in plot_paths:
        print(path.relative_to(root))


if __name__ == "__main__":
    main()
