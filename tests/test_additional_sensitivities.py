import pytest

from additional_sensitivities import price_parity_screen


def test_price_parity_screen_reports_positive_gap():
    result = price_parity_screen(150.0, 120.0)
    assert result["SAF_minus_ATF_INR_L"] == 30.0
    assert result["SAF_to_ATF_price_ratio"] == 1.25
    assert result["parity_status"] == "above_benchmark"


def test_price_parity_screen_reports_parity_or_lower():
    result = price_parity_screen(110.0, 120.0)
    assert result["SAF_minus_ATF_INR_L"] == -10.0
    assert result["parity_status"] == "at_or_below_benchmark"


@pytest.mark.parametrize(
    "mjsp, benchmark",
    [(-1.0, 100.0), (100.0, 0.0), (100.0, -1.0)],
)
def test_price_parity_screen_rejects_invalid_prices(mjsp, benchmark):
    with pytest.raises(ValueError):
        price_parity_screen(mjsp, benchmark)
