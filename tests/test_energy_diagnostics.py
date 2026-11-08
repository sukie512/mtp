from types import SimpleNamespace

import numpy as np

from analysis import unit_energy_diagnostics


class FakeUnit:
    def __init__(self, ID, duty, power):
        self.ID = ID
        self.net_duty = duty
        self.net_power = power


def test_unit_energy_diagnostics_reports_duty_and_power():
    sys = SimpleNamespace(units=[FakeUnit("R201", 1200.0, 0.0), FakeUnit("K201", 0.0, 55.0)])
    result = unit_energy_diagnostics(sys)
    assert list(result["unit_ID"]) == ["R201", "K201"]
    assert np.allclose(result["net_duty_kJ_hr"], [1200.0, 0.0])
    assert np.allclose(result["net_power_kW"], [0.0, 55.0])
