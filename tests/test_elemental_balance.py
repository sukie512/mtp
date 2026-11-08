from types import SimpleNamespace

import numpy as np

from analysis import elemental_balance_errors, process_mass_balance_diagnostics


class FakeStream:
    def __init__(self, atoms):
        self.atoms = atoms

    def get_atomic_flow(self, element):
        return self.atoms.get(element, 0.0)


def test_elemental_balance_errors_are_zero_for_balanced_system():
    sys = SimpleNamespace(
        feeds=[FakeStream({"C": 10.0, "H": 20.0, "O": 5.0})],
        products=[FakeStream({"C": 10.0, "H": 20.0, "O": 5.0})],
    )
    result = elemental_balance_errors(sys)
    assert all(np.isclose(value, 0.0) for value in result.values())


def test_elemental_balance_errors_report_output_minus_input():
    sys = SimpleNamespace(
        feeds=[FakeStream({"C": 10.0, "H": 20.0, "O": 5.0})],
        products=[FakeStream({"C": 9.0, "H": 22.0, "O": 4.0})],
    )
    result = elemental_balance_errors(sys)
    assert np.isclose(result["C_balance_error_pct"], -10.0)
    assert np.isclose(result["H_balance_error_pct"], 10.0)
    assert np.isclose(result["O_balance_error_pct"], -20.0)



def test_catalyst_makeup_is_reported_separately_not_as_process_loss():
    catalyst = FakeStream({"C": 0.0, "H": 0.0, "O": 0.0})
    catalyst.ID = "Cat_olig"
    catalyst.F_mass = 2.5
    feed = FakeStream({"C": 10.0, "H": 20.0, "O": 5.0})
    feed.ID = "Ethanol_In"
    feed.F_mass = 100.0
    product = FakeStream({"C": 10.0, "H": 20.0, "O": 5.0})
    product.F_mass = 100.0
    sys = SimpleNamespace(feeds=[feed, catalyst], products=[product])

    mass = process_mass_balance_diagnostics(sys)
    elements = elemental_balance_errors(sys)

    assert np.isclose(mass["process_mass_balance_error_pct"], 0.0)
    assert np.isclose(mass["catalyst_makeup_kg_hr_excluded"], 2.5)
    assert all(np.isclose(value, 0.0) for value in elements.values())
