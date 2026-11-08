import numpy as np
import pytest

from tea import wdv_depreciation_fractions


def test_wdv_schedule_matches_declining_balance_formula():
    schedule = wdv_depreciation_fractions(0.15, 3)
    expected = np.array([0.15, 0.15 * 0.85, 0.15 * 0.85**2])
    assert np.allclose(schedule, expected)


def test_wdv_schedule_preserves_residual_book_fraction():
    rate, years = 0.15, 30
    schedule = wdv_depreciation_fractions(rate, years)
    residual = (1.0 - rate) ** years
    assert np.isclose(schedule.sum() + residual, 1.0)


@pytest.mark.parametrize("rate, years", [(0.0, 10), (1.0, 10), (0.15, 0), (0.15, -1)])
def test_wdv_schedule_rejects_invalid_inputs(rate, years):
    with pytest.raises(ValueError):
        wdv_depreciation_fractions(rate, years)
