import numpy as np
import pandas as pd

from run_mc_replicates import finite_metric_mask, sensitivity_correlations


def test_finite_metric_mask_excludes_nan_and_both_infinities():
    table = pd.DataFrame({
        "MJSP INR/L": [500.0, np.nan, np.inf, -np.inf, 550.0],
    })

    values, mask = finite_metric_mask(table, "MJSP INR/L")

    assert mask.tolist() == [True, False, False, False, True]
    assert values.loc[mask].tolist() == [500.0, 550.0]


def test_sensitivity_correlations_use_only_finite_rows_and_rank_inputs():
    columns = pd.MultiIndex.from_tuples([
        ("Metric", "MJSP INR/L"),
        ("Metric", "SAF yield"),
        ("Input", "ethanol_cost"),
        ("Input", "fx"),
    ])
    table = pd.DataFrame(
        [
            [500.0, 5.0, 1.0, 5.0],
            [510.0, 5.1, 2.0, 4.0],
            [520.0, 5.2, 3.0, 3.0],
            [np.inf, 5.3, 4.0, 2.0],
            [540.0, 5.4, 5.0, 1.0],
        ],
        columns=columns,
    )
    _, valid_mask = finite_metric_mask(table, ("Metric", "MJSP INR/L"))

    correlations = sensitivity_correlations(
        table, ("Metric", "MJSP INR/L"), valid_mask
    )

    assert correlations["ethanol_cost"] > 0.99
    assert correlations["fx"] < -0.99
    assert "MJSP INR/L" not in correlations.index
    assert "SAF yield" not in correlations.index
