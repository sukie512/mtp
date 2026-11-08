import numpy as np

from settings import ethanol_feed_density, ethanol_kg_hr


def test_total_feed_density_uses_ethanol_and_water_mass_fractions():
    settings = {
        "ethanol_purity_wt": 0.995,
        "ethanol_density": 789.0,
        "ethanol_KLPD": 200.0,
    }
    expected = 1.0 / (0.995 / 789.0 + 0.005 / 998.2)
    assert np.isclose(ethanol_feed_density(settings), expected)


def test_klpd_mass_flow_uses_total_feed_density():
    settings = {
        "ethanol_purity_wt": 0.995,
        "ethanol_density": 789.0,
        "ethanol_KLPD": 200.0,
    }
    assert np.isclose(ethanol_kg_hr(settings), 200.0 * ethanol_feed_density(settings) / 24.0)
