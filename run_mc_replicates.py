"""Run independent Latin-hypercube replicates for a more defensible MC stability check.

Example:
    python run_mc_replicates.py --n 1000 --replicates 3 --seed 1234 --out new_results/replicates

Each replicate builds a fresh model and uses a distinct deterministic seed. This
is intentionally separate from run_all.py's single-run prefix diagnostic.
"""
import argparse
from pathlib import Path

import pandas as pd

try:
    from . import uncertainty as U
except ImportError:
    import uncertainty as U


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1000, help="LHS samples per independent replicate")
    parser.add_argument("--replicates", type=int, default=3, help="Number of independent LHS designs")
    parser.add_argument("--seed", type=int, default=1234, help="Seed for the first replicate")
    parser.add_argument("--out", default="new_results/replicates", help="Directory for replicate summaries and samples")
    args = parser.parse_args()

    if args.n < 2:
        parser.error("--n must be at least 2")
    if args.replicates < 2:
        parser.error("--replicates must be at least 2 to compare independent designs")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    records = []

    for i in range(args.replicates):
        seed = args.seed + i
        print(f"\nReplicate {i + 1}/{args.replicates}: N={args.n}, seed={seed}", flush=True)
        model = U.run_mc(N=args.n, seed=seed)
        table = model.table.copy()
        columns = [c for c in table.columns if "MJSP" in str(c) and "INR" in str(c)]
        if not columns:
            raise RuntimeError("Monte Carlo output has no MJSP (INR/L) metric column")
        metric = columns[0]
        values = pd.to_numeric(table[metric], errors="coerce").dropna()
        failed = args.n - len(values)
        if len(values) < 2:
            raise RuntimeError(
                f"Replicate {i + 1} has only {len(values)} valid MJSP samples; inspect model failures."
            )

        records.append({
            "replicate": i + 1,
            "seed": seed,
            "requested_samples": args.n,
            "valid_samples": len(values),
            "failed_samples": failed,
            "failure_fraction": failed / args.n,
            "mean_INR_L": values.mean(),
            "std_INR_L": values.std(ddof=1),
            "P5_INR_L": values.quantile(0.05),
            "P50_INR_L": values.quantile(0.50),
            "P95_INR_L": values.quantile(0.95),
        })
        table.to_csv(out / f"mc_replicate_{i + 1:02d}_samples.csv", index=False)
        print(
            f"Valid={len(values)}/{args.n}; "
            f"mean={values.mean():.2f}; P5/P50/P95="
            f"{values.quantile(.05):.2f}/{values.quantile(.50):.2f}/{values.quantile(.95):.2f} INR/L",
            flush=True,
        )

    summary = pd.DataFrame(records)
    summary.to_csv(out / "mc_replicate_summary.csv", index=False)
    print(f"\nIndependent-replicate summary saved to: {out / 'mc_replicate_summary.csv'}")
    print(summary.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
