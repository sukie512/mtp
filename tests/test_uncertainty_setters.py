from types import SimpleNamespace

import uncertainty


def test_setting_setter_updates_settings_and_live_tea(monkeypatch):
    applied = []
    monkeypatch.setattr(uncertainty, "apply_prices", lambda flowsheet, settings: applied.append((flowsheet, settings)))

    settings = {"labor_USD_yr": 1_200_000.0}
    flowsheet = object()
    tea = SimpleNamespace(labor_cost=1_200_000.0)

    setter = uncertainty.make_setting_setter(
        settings, flowsheet, tea, "labor_USD_yr", tea_attribute="labor_cost"
    )
    setter(1_850_000.0)

    assert settings["labor_USD_yr"] == 1_850_000.0
    assert tea.labor_cost == 1_850_000.0
    assert applied == [(flowsheet, settings)]


def test_nested_setting_setter_updates_selected_route(monkeypatch):
    applied = []
    monkeypatch.setattr(uncertainty, "apply_prices", lambda flowsheet, settings: applied.append(settings))

    settings = {"h2_INR_kg": {"green_offsite": 363.0, "grey_smr_refinery": 200.0}}
    tea = SimpleNamespace()
    setter = uncertainty.make_setting_setter(
        settings, object(), tea, "h2_INR_kg", sub="green_offsite"
    )
    setter(410.0)

    assert settings["h2_INR_kg"]["green_offsite"] == 410.0
    assert settings["h2_INR_kg"]["grey_smr_refinery"] == 200.0
    assert len(applied) == 1
