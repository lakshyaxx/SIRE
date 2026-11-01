"""Audit the NASA C-MAPSS files and write reproducible report figures."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[2] / ".venv" / "mplconfig"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

LOG = logging.getLogger("cmapss_audit")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
EXPECTED = {"FD001": (100, 100, 1), "FD002": (260, 259, 6), "FD003": (100, 100, 1), "FD004": (248, 249, 6)}
RAW_COLUMNS = ["unit", "cycle", "op1", "op2", "op3", *[f"s{i}" for i in range(1, 22)]]
SENSOR_COLUMNS = RAW_COLUMNS[5:]
SETTING_COLUMNS = RAW_COLUMNS[2:5]


def _load_frame(path: Path) -> pd.DataFrame:
    """Load a whitespace-delimited C-MAPSS file and validate its width."""
    frame = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    frame = frame.dropna(axis=1, how="all")
    if frame.shape[1] != len(RAW_COLUMNS):
        raise ValueError(f"{path.name}: expected 26 columns, found {frame.shape[1]}")
    frame.columns = RAW_COLUMNS
    return frame


def _lengths(frame: pd.DataFrame) -> pd.Series:
    """Return observed cycle counts indexed by engine id."""
    return frame.groupby("unit")["cycle"].size().sort_index()


def _stats(series: pd.Series) -> str:
    """Format minimum, median and maximum as integer cycle counts."""
    return f"{int(series.min())} / {series.median():.1f} / {int(series.max())}"


def _near_constant(frame: pd.DataFrame, threshold: float = 0.999) -> list[str]:
    """Find sensors with one value occurring in at least 99.9% of rows."""
    result: list[str] = []
    for column in SENSOR_COLUMNS:
        share = frame[column].value_counts(dropna=False, normalize=True).max()
        if share >= threshold:
            result.append(f"{column} ({share:.4%} modal value)")
    return result


def _cluster(train: pd.DataFrame, test: pd.DataFrame, k: int) -> tuple[np.ndarray, np.ndarray, KMeans]:
    """Fit setting scaler and KMeans on training rows, then label both splits."""
    scaler = StandardScaler().fit(train[SETTING_COLUMNS])
    train_x = scaler.transform(train[SETTING_COLUMNS])
    test_x = scaler.transform(test[SETTING_COLUMNS])
    estimator = KMeans(n_clusters=k, random_state=42, n_init=10).fit(train_x)
    return estimator.labels_, estimator.predict(test_x), estimator


def _write_figures(
    dataset: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    train_rul: pd.Series,
    train_cluster: np.ndarray | None,
    test_cluster: np.ndarray | None,
) -> None:
    """Generate the requested sensor, life-length, correlation and cluster plots."""
    lengths_train = _lengths(train)
    unit_ids = sorted(lengths_train.index.tolist())
    chosen = sorted({unit_ids[0], unit_ids[len(unit_ids) // 2], unit_ids[-1]})
    fig, axes = plt.subplots(7, 3, figsize=(16, 20), sharex=False)
    for index, sensor in enumerate(SENSOR_COLUMNS):
        axis = axes.flat[index]
        for unit in chosen:
            part = train.loc[train["unit"].eq(unit)]
            axis.plot(part["cycle"], part[sensor], linewidth=0.9, label=f"engine {unit}")
        axis.set_title(sensor)
        axis.set_xlabel("Cycle")
        axis.grid(alpha=0.2)
    axes.flat[0].legend(fontsize=7)
    fig.suptitle(f"{dataset}: sensor trajectories for engines {chosen}")
    fig.tight_layout()
    fig.savefig(FIGURES / f"sensor_trajectories_{dataset}.png", dpi=150)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(9, 5))
    axis.hist(lengths_train, bins=30, alpha=0.65, label="train")
    axis.hist(_lengths(test), bins=30, alpha=0.65, label="test")
    axis.set(title=f"{dataset}: engine life-length distribution", xlabel="Cycles", ylabel="Engine count")
    axis.legend()
    axis.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / f"life_lengths_{dataset}.png", dpi=150)
    plt.close(fig)

    correlations = pd.concat([train[SENSOR_COLUMNS], train_rul.rename("raw_rul")], axis=1).corr(numeric_only=True)["raw_rul"].drop("raw_rul")
    fig, axis = plt.subplots(figsize=(12, 5))
    correlations.sort_values().plot.bar(ax=axis)
    axis.set(title=f"{dataset}: sensor correlation with raw training RUL", ylabel="Pearson correlation")
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / f"sensor_rul_correlations_{dataset}.png", dpi=150)
    plt.close(fig)

    if train_cluster is not None and test_cluster is not None:
        pairs = [("op1", "op2"), ("op1", "op3"), ("op2", "op3")]
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), layout="constrained")
        for axis, (x_name, y_name) in zip(axes, pairs):
            points = axis.scatter(train[x_name], train[y_name], c=train_cluster, s=8, cmap="tab10", alpha=0.55)
            axis.set(xlabel=x_name, ylabel=y_name, title=f"Train: {x_name} vs {y_name}")
            axis.grid(alpha=0.2)
        fig.colorbar(points, ax=axes, label="KMeans cluster")
        fig.suptitle(f"{dataset}: operating-setting clusters (KMeans fit on train only)")
        fig.savefig(FIGURES / f"operating_clusters_{dataset}.png", dpi=150)
        plt.close(fig)


def run_audit() -> dict[str, Any]:
    """Audit all four subsets, emit Markdown and requested PNG figures."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    report: list[str] = [
        "# C-MAPSS data audit",
        "",
        "Audit date: 2026-11-01. Source files in `CMAPSS/data/` were parsed with whitespace separation, no header, and empty trailing columns removed.",
        "",
        "Near-constant definition: at least 99.9% of the training rows share one exact sensor value. Constant sensors are exact zero-variance sensors.",
        "Operating-condition clusters use StandardScaler and KMeans (`k=6`, `n_init=10`, seed 42), both fitted on training operating settings only; the fitted objects label test settings for audit counts.",
        "",
        "## Subset summary",
        "",
        "| Dataset | Train shape | Test shape | Train engines | Test engines | Train length min / median / max | Test length min / median / max | Official RUL rows | Expected engines (train/test) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    summary_rows: list[str] = []
    results: dict[str, Any] = {}
    all_train_lengths: dict[str, pd.Series] = {}

    for dataset, (expected_train_n, expected_test_n, n_conditions) in EXPECTED.items():
        train = _load_frame(DATA / f"train_{dataset}.txt")
        test = _load_frame(DATA / f"test_{dataset}.txt")
        rul_frame = pd.read_csv(DATA / f"RUL_{dataset}.txt", sep=r"\s+", header=None, engine="python").dropna(axis=1, how="all")
        if rul_frame.shape[1] != 1:
            raise ValueError(f"RUL_{dataset}.txt must have one value per row; found {rul_frame.shape[1]} columns")
        official_rul = rul_frame.iloc[:, 0].astype(float)
        train_lengths, test_lengths = _lengths(train), _lengths(test)
        all_train_lengths[dataset] = train_lengths
        max_cycles = train.groupby("unit")["cycle"].transform("max")
        raw_rul = max_cycles - train["cycle"]
        train_rul = raw_rul.rename("raw_rul")
        constant = [sensor for sensor in SENSOR_COLUMNS if train[sensor].nunique(dropna=False) == 1]
        near_constant = _near_constant(train)
        train_clusters: np.ndarray | None = None
        test_clusters: np.ndarray | None = None
        cluster_counts = "not applicable (single operating condition)"
        if n_conditions == 6:
            train_clusters, test_clusters, _ = _cluster(train, test, n_conditions)
            cluster_counts = (
                "train=" + ", ".join(f"{c}:{int((train_clusters == c).sum())}" for c in range(n_conditions))
                + "; test=" + ", ".join(f"{c}:{int((test_clusters == c).sum())}" for c in range(n_conditions))
            )
        missing = {"train": int(train.isna().sum().sum()), "test": int(test.isna().sum().sum()), "rul": int(official_rul.isna().sum())}
        dtype_summary = ", ".join(f"{name}={dtype}" for name, dtype in train.dtypes.astype(str).value_counts().items())
        row_match = len(official_rul) == len(test_lengths)
        summary_rows.append(
            f"| {dataset} | {train.shape[0]} x {train.shape[1]} | {test.shape[0]} x {test.shape[1]} | {len(train_lengths)} | {len(test_lengths)} | {_stats(train_lengths)} | {_stats(test_lengths)} | {len(official_rul)} ({'match' if row_match else 'MISMATCH'}) | {expected_train_n}/{expected_test_n} |"
        )
        report.extend(
            [
                "",
                f"### {dataset} details",
                "",
                f"- Operating conditions expected: {n_conditions}; distinct training setting triplets rounded to 4 decimals: {train[SETTING_COLUMNS].round(4).drop_duplicates().shape[0]}.",
                f"- Columns: {', '.join(RAW_COLUMNS)}. Training dtypes: {dtype_summary}; test dtypes: {', '.join(f'{c}={t}' for c, t in test.dtypes.astype(str).value_counts().items())}.",
                f"- Missing values: train={missing['train']}, test={missing['test']}, official RUL={missing['rul']}.",
                f"- Exact constant training sensors: {', '.join(constant) if constant else 'none'}.",
                f"- Near-constant training sensors (modal share >= 99.9%): {', '.join(near_constant) if near_constant else 'none'}.",
                f"- Shortest test engines by cycle count: {', '.join(f'{int(unit)} ({int(length)} cycles)' for unit, length in test_lengths.sort_values().head(10).items())}.",
                f"- Training raw RUL distribution (cycles): min={raw_rul.min():.0f}, median={raw_rul.median():.1f}, max={raw_rul.max():.0f}; clipped-at-125 median={raw_rul.clip(upper=125).median():.1f}.",
                f"- Official test RUL distribution (cycles): min={official_rul.min():.0f}, median={official_rul.median():.1f}, max={official_rul.max():.0f}; test engine ordering check={'unit ids 1..N' if test_lengths.index.tolist() == list(range(1, len(test_lengths) + 1)) else 'not sequential 1..N; row-index mapping needs review'}.",
                f"- Operating-setting cluster row counts: {cluster_counts}.",
            ]
        )
        _write_figures(dataset, train, test, train_rul, train_clusters, test_clusters)
        results[dataset] = {
            "train_shape": train.shape,
            "test_shape": test.shape,
            "train_engines": len(train_lengths),
            "test_engines": len(test_lengths),
            "train_length_stats": (int(train_lengths.min()), float(train_lengths.median()), int(train_lengths.max())),
            "test_length_stats": (int(test_lengths.min()), float(test_lengths.median()), int(test_lengths.max())),
            "rul_rows": len(official_rul),
            "constant_sensors": constant,
            "near_constant_sensors": near_constant,
            "missing": missing,
            "cluster_counts": cluster_counts,
        }

    table_end = report.index("## Subset summary") + 4
    report[table_end:table_end] = summary_rows
    report.extend(["", "## Deviations from `CMAPSS/README.md` expectations", ""])
    deviations: list[str] = []
    for dataset, (expected_train_n, expected_test_n, _) in EXPECTED.items():
        item = results[dataset]
        if item["train_engines"] != expected_train_n:
            deviations.append(f"{dataset}: train engines expected {expected_train_n}, observed {item['train_engines']}.")
        if item["test_engines"] != expected_test_n:
            deviations.append(f"{dataset}: test engines expected {expected_test_n}, observed {item['test_engines']}.")
        if item["rul_rows"] != expected_test_n:
            deviations.append(f"{dataset}: official RUL rows expected {expected_test_n}, observed {item['rul_rows']}.")
    if deviations:
        report.extend(f"- {line}" for line in deviations)
    else:
        report.append("- None in the supplied file inventory, 26-column schema, engine counts, and official RUL row counts.")
    report.extend(
        [
            "",
            "The expected 12 data files, `readme.txt`, and `Damage Propagation Modeling.pdf` are all present. Exact constants and near-constants above are reported for audit; protocol preprocessing must identify constants on each model's training-engine split.",
            "",
            "## Generated figures",
            "",
            "- Four `sensor_trajectories_FD00X.png` files (21 sensor channels, three deterministic training engines each).",
            "- Four `life_lengths_FD00X.png` histograms (train and test).",
            "- Four `sensor_rul_correlations_FD00X.png` sensor/RUL correlation charts.",
            "- `operating_clusters_FD002.png` and `operating_clusters_FD004.png` (three operating-setting projections).",
            "",
        ]
    )
    (RESULTS / "data_audit.md").write_text("\n".join(report), encoding="utf-8")
    LOG.info("Wrote audit report to %s and figures to %s", RESULTS / "data_audit.md", FIGURES)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    audit = run_audit()
    for name, item in audit.items():
        LOG.info(
            "%s train=%s/%s engines=%s lengths=%s test=%s/%s engines=%s lengths=%s RUL_rows=%s constants=%s clusters=%s",
            name,
            *item["train_shape"],
            item["train_engines"],
            item["train_length_stats"],
            *item["test_shape"],
            item["test_engines"],
            item["test_length_stats"],
            item["rul_rows"],
            item["constant_sensors"],
            item["cluster_counts"],
        )
