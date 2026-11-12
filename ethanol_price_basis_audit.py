"""Reconcile the India ATJ SAF price benchmark with the ethanol feed-price basis.

This script does NOT force the 2G case to match a quoted 1G SAF selling-price target.
It runs the same ATJ flowsheet at explicitly labelled ethanol price cases so that
the feedstock contribution and full TEA MJSP can be compared on a consistent basis.

Examples:
    python ethanol_price_basis_audit.py
    python ethanol_price_basis_audit.py --out prefinal_results/price_basis_audit.csv
"""
import argparse
from pathlib import Path

import pandas as pd

try:
    from . import analysis as A
    from . import settings as cfg
except ImportError:
    import analysis as A
    import settings as cfg


DEFAULT_CASES = (
    # Comparison only: 1G cane-juice ethanol administered ex-mill price, not a 2G price.
    ("1G cane-juice reference", "cane_juice", 65.61,
     "1G administered ex-mill reference; not the lignocellulosic thesis baseline"),
    # Indicative 2G production-cost estimate reported in 2026 industry commentary.
    ("2G indicative 2026 estimate", "2G_cellulosic", 120.0,
     "Indicative 2G production-cost estimate; verify project/feedstock/battery-limit basis"),
    # Legacy high-cost 2G quote used by the current thesis settings.
    ("2G high-cost 2024 quote", "2G_cellulosic", 160.0,
     "Reported 2G production-cost quote from 2024; retained as high-cost case"),
)


def run_price_case(label, route, ethanol_price, basis_note):
    settings = cfg.get()
    settings["ethanol_route"] = route
    settings["ethanol_exmill_INR_L"][route] = float(ethanol_price)
    sys, tea, flowsheet, settings = A.run(s=settings)
    result = A.results(sys, tea, flowsheet, settings)
    return {
        "case": label,
        "ethanol_route": route,
        "ethanol_input_INR_L": float(ethanol_price),
        "ethanol_price_basis": basis_note,
        **result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="final_results/ethanol_price_basis_audit.csv")
    args = parser.parse_args()

    rows = []
    for label, route, price, note in DEFAULT_CASES:
        print(f"\nRunning {label}: ethanol = INR {price:.2f}/L", flush=True)
        row = run_price_case(label, route, price, note)
        rows.append(row)
        print(
            f"MJSP = INR {row['MJSP_INR_L']:.2f}/L SAF; "
            f"ethanol feed contribution = INR {row['ethanol_feed_cost_INR_L_SAF']:.2f}/L SAF; "
            f"ethanol/SAF volume ratio = {row['ethanol_to_SAF_volume_ratio']:.3f}",
            flush=True,
        )

    table = pd.DataFrame(rows)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    columns = [
        "case", "ethanol_input_INR_L", "MJSP_INR_L",
        "ethanol_feed_cost_INR_L_SAF", "hydrogen_feed_cost_INR_L_SAF",
        "total_coproduct_credit_INR_L_SAF", "annual_VOC_INR_L_SAF",
        "annual_FOC_INR_L_SAF", "capital_tax_finance_return_residual_INR_L_SAF",
        "ethanol_to_SAF_volume_ratio",
        "SAF_MMgal_yr", "FCI_MM_USD",
    ]
    print(f"\nSaved price-basis audit: {output.resolve()}")
    print(table[columns].round(3).to_string(index=False))
    print(
        "\nInterpretation: the 1G case is a feedstock-class comparison, not a 2G result. "
        "The 2G INR 120/L and INR 160/L cases are indicative cost assumptions, not "
        "verified offtake prices. Compare the calculated MJSP with SAF selling-price "
        "quotes only after aligning pathway, plant scale, integration, co-product "
        "credits, subsidy/VGF, tax, delivery and return assumptions."
    )


if __name__ == "__main__":
    main()
