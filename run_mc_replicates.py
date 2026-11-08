"""Run independent Latin-hypercube replicates and compare uncertainty stability.

Example:
    python run_mc_replicates.py --n 1000 --replicates 3 --seed 1234 --out prefinal_results/replicates

Each replicate builds a fresh model and uses a distinct deterministic seed. This
is separate from run_all.py's prefix diagnostic: independent designs are the
appropriate check for Monte Carlo sampling variability.
"""
import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from . import uncertainty as U
except ImportError:
    import uncertainty as U


def finite_metric_mask(table, metric_column):
    """Return numeric metric values and a mask excluding NaN and +/- infinity."""
    values = pd.to_numeric(table[metric_column], errors="coerce").astype(float)
    mask = np.isfinite(values.to_numpy())
    return values, mask


def sensitivity_correlations(table, metric_column, valid_mask):
    """Spearman correlations between finite MJSP observations and sampled inputs."""
    valid = table.loc[valid_mask]
    metric = pd.to_numeric(valid[metric_column], errors="coerce").astype(float)
    excluded = [
        column for column in valid.columns
        if "MJSP" in str(column) or "SAF yield" in str(column)
    ]
    inputs = valid.drop(columns=excluded).apply(pd.to_numeric, errors="coerce")
    inputs = inputs.replace([np.inf, -np.inf], np.nan)
    correlations = inputs.corrwith(metric, method="spearman").dropna()
    labels = [column[1] if isinstance(column, tuple) and len(column) > 1 else str(column)
              for column in correlations.index]
    correlations.index = labels
    return correlations.sort_values(key=lambda values: values.abs(), ascending=False)


def _quantile_stability(summary, columns):
    rows = []
    for column in columns:
        values = summary[column].astype(float)
        mean_value = values.mean()
        spread = values.max() - values.min()
        rows.append({
            "statistic": column,
            "replicate_mean": mean_value,
            "replicate_min": values.min(),
            "replicate_max": values.max(),
            "absolute_spread": spread,
            "spread_pct_of_mean": (spread / abs(mean_value) * 100.0)
            if mean_value != 0 else np.nan,
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1000, help="LHS samples per independent replicate")
    parser.add_argument("--replicates", type=int, default=3, help="Number of independent LHS designs")
    parser.add_argument("--seed", type=int, default=1234, help="Seed for the first replicate")
    parser.add_argument("--out", default="prefinal_results/replicates", help="Directory for replicate summaries and samples")
    args = parser.parse_args()

    if args.n < 2:
        parser.error("--n must be at least 2")
    if args.replicates < 2:
        parser.error("--replicates must be at least 2 to compare independent designs")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    records = []
    sensitivity_by_replicate = {}

    for i in range(args.replicates):
        seed = args.seed + i
        print(f"\nReplicate {i + 1}/{args.replicates}: N={args.n}, seed={seed}", flush=True)
        model = U.run_mc(N=args.n, seed=seed)
        table = model.table.copy()
        columns = [column for column in table.columns
                   if "MJSP" in str(column) and "INR" in str(column)]
        if not columns:
            raise RuntimeError("Monte Carlo output has no MJSP (INR/L) metric column")
        metric = columns[0]
        metric_values, valid_mask = finite_metric_mask(table, metric)
        values = metric_values.loc[valid_mask]
        failed_table = table.loc[~valid_mask].copy()
        failed = len(failed_table)

        # Preserve both the complete table and failed rows for auditability.
        table.to_csv(out / f"mc_replicate_{i + 1:02d}_samples.csv", index=False)
        failed_table.to_csv(out / f"mc_replicate_{i + 1:02d}_failed_samples.csv", index=True)

        if len(values) < 2:
            raise RuntimeError(
                f"Replicate {i + 1} has only {len(values)} finite MJSP samples; "
                f"{failed} failed/non-finite rows were saved for inspection."
            )

        quantiles = values.quantile([0.05, 0.25, 0.50, 0.75, 0.95])
        records.append({
            "replicate": i + 1,
            "seed": seed,
            "requested_samples": args.n,
            "valid_samples": int(len(values)),
            "failed_or_nonfinite_samples": int(failed),
            "failure_fraction": float(failed / args.n),
            "mean_INR_L": float(values.mean()),
            "std_INR_L": float(values.std(ddof=1)),
            "P5_INR_L": float(quantiles.loc[0.05]),
            "P25_INR_L": float(quantiles.loc[0.25]),
            "P50_INR_L": float(quantiles.loc[0.50]),
            "P75_INR_L": float(quantiles.loc[0.75]),
            "P95_INR_L": float(quantiles.loc[0.95]),
        })

        sensitivity = sensitivity_correlations(table, metric, valid_mask)
        sensitivity_by_replicate[f"replicate_{i + 1:02d}"] = sensitivity
        sensitivity.rename("spearman_rho").rename_axis("parameter").reset_index().to_csv(
            out / f"mc_replicate_{i + 1:02d}_spearman.csv", index=False
        )

        print(
            f"Finite={len(values)}/{args.n}; non-finite={failed}; "
            f"mean={values.mean():.2f}; P5/P50/P95="
            f"{quantiles.loc[0.05]:.2f}/{quantiles.loc[0.50]:.2f}/"
            f"{quantiles.loc[0.95]:.2f} INR/L",
            flush=True,
        )

    summary = pd.DataFrame(records)
    summary.to_csv(out / "mc_replicate_summary.csv", index=False)

    quantile_columns = ["mean_INR_L", "P5_INR_L", "P25_INR_L", "P50_INR_L",
                        "P75_INR_L", "P95_INR_L"]
    stability = _quantile_stability(summary, quantile_columns)
    stability.to_csv(out / "mc_replicate_stability.csv", index=False)

    sensitivity_frame = pd.concat(sensitivity_by_replicate, axis=1).sort_index()
    sensitivity_frame["mean_rho"] = sensitivity_frame.mean(axis=1)
    sensitivity_frame["rho_sd"] = sensitivity_frame[
        [column for column in sensitivity_frame.columns if column.startswith("replicate_")]
    ].std(axis=1, ddof=1)
    sensitivity_frame["mean_abs_rho"] = sensitivity_frame[
        [column for column in sensitivity_frame.columns if column.startswith("replicate_")]
    ].abs().mean(axis=1)
    sensitivity_frame.sort_values("mean_abs_rho", ascending=False).to_csv(
        out / "mc_sensitivity_replicate_comparison.csv", index_label="parameter"
    )

    rank_rows = []
    rank_columns = {
        name: series.abs().rank(ascending=False, method="average")
        for name, series in sensitivity_by_replicate.items()
    }
    for left, right in combinations(rank_columns, 2):
        paired = pd.concat([rank_columns[left], rank_columns[right]], axis=1).dropna()
        rho = paired.iloc[:, 0].corr(paired.iloc[:, 1], method="spearman") if len(paired) >= 2 else np.nan
        rank_rows.append({"replicate_a": left, "replicate_b": right,
                          "spearman_rank_agreement": rho, "shared_parameters": len(paired)})
    pd.DataFrame(rank_rows).to_csv(out / "mc_sensitivity_rank_agreement.csv", index=False)

    print(f"\nIndependent-replicate summary saved under: {out.resolve()}")
    print(summary.round(3).to_string(index=False))
    print("\nAcross-replicate quantile stability (spread relative to replicate mean):")
    print(stability.round(3).to_string(index=False))
    print("\nSensitivity-rank agreement:")
    print(pd.DataFrame(rank_rows).round(3).to_string(index=False))
    print(
        "\nInterpretation: compare replicate quantiles and sensitivity ranks. "
        "These diagnostics measure sampling stability conditional on the chosen "
        "input distributions; they do not validate those distributions or model structure."
    )


if __name__ == "__main__":
    main()
