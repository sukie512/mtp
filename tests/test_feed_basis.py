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


from settings import ethanol_price_USD_kg


def test_2g_cost_proxy_does_not_receive_conventional_transport_adder():
    settings = {
        "ethanol_route": "2G_cellulosic",
        "ethanol_exmill_INR_L": {"2G_cellulosic": 160.0},
        "ethanol_transport_INR_L_conventional": 1.2,
        "fx": 100.0,
        "ethanol_density": 800.0,
        "ethanol_purity_wt": 0.995,
    }
    expected = (160.0 / 100.0 / 0.8) * 0.995
    assert np.isclose(ethanol_price_USD_kg(settings), expected)


def test_conventional_ethanol_price_includes_transport_and_prices_total_feed_mass():
    settings = {
        "ethanol_route": "maize",
        "ethanol_exmill_INR_L": {"maize": 70.0},
        "ethanol_transport_INR_L_conventional": 1.2,
        "fx": 100.0,
        "ethanol_density": 800.0,
        "ethanol_purity_wt": 0.995,
    }
    expected = (71.2 / 100.0 / 0.8) * 0.995
    assert np.isclose(ethanol_price_USD_kg(settings), expected)
