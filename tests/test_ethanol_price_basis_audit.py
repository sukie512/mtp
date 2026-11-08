import ethanol_price_basis_audit as audit
import settings as cfg


def test_price_case_uses_a_copy_and_sets_the_requested_ethanol_basis(monkeypatch):
    captured = {}

    def fake_run(s):
        captured["settings"] = s
        return "system", "tea", "flowsheet", s

    def fake_results(system, tea, flowsheet, settings):
        return {"MJSP_INR_L": 250.0, "ethanol_feed_cost_INR_L_SAF": 190.0}

    monkeypatch.setattr(audit.A, "run", fake_run)
    monkeypatch.setattr(audit.A, "results", fake_results)

    original_price = cfg.S["ethanol_exmill_INR_L"]["2G_cellulosic"]
    row = audit.run_price_case(
        "2G test", "2G_cellulosic", 120.0, "test basis"
    )

    assert row["ethanol_input_INR_L"] == 120.0
    assert row["ethanol_route"] == "2G_cellulosic"
    assert captured["settings"]["ethanol_exmill_INR_L"]["2G_cellulosic"] == 120.0
    assert cfg.S["ethanol_exmill_INR_L"]["2G_cellulosic"] == original_price
    assert row["MJSP_INR_L"] == 250.0


def test_price_cases_keep_1g_and_2g_bases_explicitly_distinct():
    cases = {label: (route, price) for label, route, price, _ in audit.DEFAULT_CASES}

    assert cases["1G cane-juice reference"] == ("cane_juice", 65.61)
    assert cases["2G indicative 2026 estimate"] == ("2G_cellulosic", 120.0)
    assert cases["2G high-cost 2024 quote"] == ("2G_cellulosic", 160.0)
