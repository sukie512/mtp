import numpy as np

from asf_model import (
    calibrate_beta0,
    max_c8_c16_share,
    oligomer_weight_fractions,
    weight_fractions,
)


def test_raw_asf_distribution_is_normalized():
    w = weight_fractions(0.68)
    assert np.isclose(w.sum(), 1.0)
    assert np.all(w >= 0.0)


def test_oligomer_distribution_excludes_ethylene_and_is_normalized():
    w = oligomer_weight_fractions(0.68)
    assert w[0] == 0.0
    assert np.isclose(w[1:].sum(), 1.0)
    assert np.all(w >= 0.0)


def test_calibration_targets_c8_plus_on_oligomer_product_basis():
    alpha, beta0 = calibrate_beta0(0.63)
    w = oligomer_weight_fractions(alpha)
    assert 0.0 < alpha < 1.0
    assert beta0 > 0.0
    assert np.isclose(w[3:].sum(), 0.63, atol=1e-8)


def test_c8_c16_is_not_mislabeled_as_c8_plus():
    alpha, _ = calibrate_beta0(0.63)
    w = oligomer_weight_fractions(alpha)
    assert w[3:8].sum() < w[3:].sum()


def test_c8_c16_bound_is_below_paper_fixed_split():
    bound, alpha = max_c8_c16_share()
    assert 0.0 < alpha < 1.0
    assert 0.0 < bound < 0.63
