from types import SimpleNamespace

from uncertainty import (
    set_oligomerization_pressure,
    set_oligomerization_temperature,
)


def test_temperature_parameter_updates_heater_and_reactor():
    units = SimpleNamespace(
        H203=SimpleNamespace(T=393.15),
        R202=SimpleNamespace(T=393.15),
    )
    set_oligomerization_temperature(units, 403.15)
    assert units.H203.T == 403.15
    assert units.R202.T == 403.15


def test_pressure_parameter_updates_compressor_and_reactor():
    units = SimpleNamespace(
        K202=SimpleNamespace(P=35e5),
        R202=SimpleNamespace(P=35e5),
    )
    set_oligomerization_pressure(units, 40e5)
    assert units.K202.P == 40e5
    assert units.R202.P == 40e5
