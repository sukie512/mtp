"""Supplementary India ATJ sensitivities not included in the main runner.

Runs an H2 storage-days capital sensitivity and a simple SAF-vs-fossil-ATF
price-parity screen. The latter is only an indicative benchmark: ensure both
prices use the same tax, delivery, date and location basis before interpreting
the gap as a policy support requirement.
"""
import argparse
import math
from pathlib import Path

import pandas as pd

try:
    from . import analysis as A
    from . import settings as cfg
except ImportError:
    import analysis as A
    import settings as cfg


def price_parity_screen(mjsp_inr_l, fossil_atf_inr_l):
    """Return a simple price gap; positive means SAF MJSP exceeds the ATF benchmark."""
    mjsp = float(mjsp_inr_l)
    benchmark = float(fossil_atf_inr_l)
    if not math.isfinite(mjsp) or not math.isfinite(benchmark) or mjsp < 0 or benchmark <= 0:
        raise ValueError("MJSP must be non-negative and fossil ATF benchmark must be positive")
    return {
        "SAF_MJSP_INR_L": mjsp,
        "fossil_ATF_benchmark_INR_L": benchmark,
        "SAF_minus_ATF_INR_L": mjsp - benchmark,
        "SAF_to_ATF_price_ratio": mjsp / benchmark,
        "parity_status": "at_or_below_benchmark" if mjsp <= benchmark else "above_benchmark",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="prefinal_results1", help="Output directory")
    parser.add_argument(
        "--storage-days", type=float, nargs="+",
        default=[1, 3, 7, 14, 30],
        help="Hydrogen storage inventory durations to test (days)",
    )
    args = parser.parse_args()
    if not args.storage_days or any(not math.isfinite(x) or x <= 0 for x in args.storage_days):
        parser.error("--storage-days must contain positive values")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for days in args.storage_days:
        print(f"Simulating hydrogen storage duration: {days:g} days", flush=True)
        sys, tea, flowsheet, settings = A.run(h2_storage_days=days)
        result = A.results(sys, tea, flowsheet, settings)
        rows.append({
            "H2_storage_days": days,
            "MJSP_INR_L": result["MJSP_INR_L"],
            "H2_storage_tank_installed_cost_USD": flowsheet.unit.T102.installed_cost,
            "installed_equipment_MM_USD": result["installed_MM_USD"],
            "FCI_MM_USD": result["FCI_MM_USD"],
            "SAF_MMgal_yr": result["SAF_MMgal_yr"],
        })

    storage = pd.DataFrame(rows)
    storage.to_csv(out / "h2_storage_days_sensitivity.csv", index=False)
    print("\nHydrogen storage-days sensitivity:")
    print(storage.round(3).to_string(index=False))

    baseline_result = A.results(*A.run())
    parity = price_parity_screen(
        baseline_result["MJSP_INR_L"], cfg.S["fossil_atf_INR_L"]
    )
    parity.update({
        "benchmark_basis_note": (
            "Indicative only: model MJSP is a plant-gate model output, while the "
            "configured fossil ATF benchmark is a Delhi market/retail reference. "
            "Tax, delivery, date and location bases are not harmonized."
        ),
        "benchmark_source_value_from_settings_INR_L": cfg.S["fossil_atf_INR_L"],
    })
    pd.DataFrame([parity]).to_csv(out / "policy_price_parity_screen.csv", index=False)
    print("\nIndicative price-parity screen (not a subsidy estimate):")
    print(pd.Series(parity).to_string())
    print(f"\nSaved outputs under: {out.resolve()}")


if __name__ == "__main__":
    main()
