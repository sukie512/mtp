"""
analysis.py -- everything you RUN. Depends on: settings.py, system.py (and asf_model.py indirectly).
Each function builds a fresh flowsheet from a (possibly modified) copy of settings, simulates, and returns numbers.
"""
import copy
import itertools
import warnings

import numpy as np
import pandas as pd
import biosteam as bst

try:
    from . import settings as cfg
    from .system import build
except ImportError:
    import settings as cfg
    from system import build

_n = itertools.count(1)
GAL = 264.172        # gal per m3


def run(s=None, **overrides):
    """Build + simulate. overrides use dotted keys, e.g. run(**{'olig.T': 403.15, 'ethanol_route': 'maize'})."""
    s = copy.deepcopy(s) if s is not None else cfg.get()
    for k, v in overrides.items():
        if '.' in k:
            a, b = k.split('.', 1)
            s[a][b] = v
        else:
            s[k] = v
    sys, tea, F = build(s, ID=f'run{next(_n)}')
    sys.simulate()
    return sys, tea, F, s


CATALYST_MAKEUP_IDS = {'Cat_dehyd', 'Cat_olig', 'Cat_hydgn'}


def process_material_feeds(sys):
    """External process feeds, excluding catalyst make-up inventory streams.

    Catalyst make-up is currently costed as a feed stream but spent catalyst is
    not represented as a product stream. Including it in a process balance
    would therefore report a false mass/element loss. The excluded catalyst
    flow is reported separately by process_mass_balance_diagnostics().
    """
    return tuple(stream for stream in sys.feeds if getattr(stream, 'ID', None) not in CATALYST_MAKEUP_IDS)


def process_mass_balance_diagnostics(sys):
    """Return process-only mass closure and the separately excluded catalyst make-up rate."""
    feeds = process_material_feeds(sys)
    products = tuple(sys.products)
    inlet = sum(stream.F_mass for stream in feeds)
    outlet = sum(stream.F_mass for stream in products)
    catalyst_makeup = sum(
        stream.F_mass for stream in sys.feeds if getattr(stream, 'ID', None) in CATALYST_MAKEUP_IDS
    )
    return {
        'process_mass_balance_error_pct': (
            (outlet - inlet) / inlet * 100.0 if inlet else np.nan
        ),
        # Backward-compatible sign convention: positive means apparent mass loss.
        'mass_balance_pct': (
            (inlet - outlet) / inlet * 100.0 if inlet else np.nan
        ),
        'catalyst_makeup_kg_hr_excluded': catalyst_makeup,
    }


def elemental_balance_errors(sys, elements=('C', 'H', 'O')):
    """Return process-only elemental imbalance percentages across feeds and products.

    Catalyst make-up streams are excluded because the current flowsheet costs
    their replacement but does not model spent-catalyst discharge. Positive
    values mean net accumulation at the outputs; negative values mean an
    apparent loss. This is a diagnostic, not a substitute for unit balances.
    """
    feeds = process_material_feeds(sys)
    products = tuple(sys.products)
    errors = {}
    for element in elements:
        inlet = sum(stream.get_atomic_flow(element) for stream in feeds)
        outlet = sum(stream.get_atomic_flow(element) for stream in products)
        errors[f'{element}_balance_error_pct'] = (
            (outlet - inlet) / inlet * 100.0 if inlet else np.nan
        )
    return errors


def unit_energy_diagnostics(sys):
    """Return unit-level net heat duty and power demand for independent review."""
    rows = []
    for unit in sys.units:
        try:
            duty = float(unit.net_duty)
        except Exception:
            duty = np.nan
        try:
            power = float(unit.net_power)
        except Exception:
            power = np.nan
        rows.append({
            'unit_ID': unit.ID,
            'unit_type': type(unit).__name__,
            'net_duty_kJ_hr': duty,
            'net_power_kW': power,
        })
    return pd.DataFrame(rows)


def results(sys, tea, F, s):
    """One-row TEA summary plus an annualized, plant-gate operating-cost audit per litre of SAF."""
    st = F.stream
    hrs = tea.operating_hours
    p = tea.solve_price(st.SAF)                                    # USD/kg  (NPV = 0)
    saf_gal = st.SAF.F_vol * GAL * hrs
    saf_litres_yr = st.SAF.F_vol * 1000.0 * hrs
    saf_litres_hr = st.SAF.F_vol * 1000.0
    fuel_kg = st.SAF.F_mass + st.RN.F_mass + st.RD.F_mass
    ol = F.unit.R202

    # Annualized operating-cost contributions. Stream costs are USD/hr; TEA VOC/FOC are USD/yr.
    # These explain the operating economics but do not allocate capital recovery, tax, or target IRR.
    def stream_cost_INR_L(stream):
        return stream.cost * hrs * s['fx'] / saf_litres_yr if saf_litres_yr else np.nan

    ethanol_feed_cost_INR_L = stream_cost_INR_L(st.Ethanol_In)
    hydrogen_feed_cost_INR_L = stream_cost_INR_L(st.Hydrogen_In)
    rn_credit_INR_L = stream_cost_INR_L(st.RN)
    rd_credit_INR_L = stream_cost_INR_L(st.RD)
    mjsp_inr_l = p * st.SAF.rho / 1000 * s['fx']
    annual_voc_inr_l = tea.VOC * s['fx'] / saf_litres_yr if saf_litres_yr else np.nan
    annual_foc_inr_l = tea.FOC * s['fx'] / saf_litres_yr if saf_litres_yr else np.nan

    return dict(MJSP_USD_gal=p * st.SAF.rho / GAL, MJSP_INR_L=mjsp_inr_l,
                SAF_MMgal_yr=saf_gal / 1e6, SAF_frac_of_fuel=st.SAF.F_mass / fuel_kg,
                RN_MMgal_yr=st.RN.F_vol * GAL * hrs / 1e6, RD_MMgal_yr=st.RD.F_vol * GAL * hrs / 1e6,
                alpha=ol.alpha, olig_X_avg=ol.X_avg,
                H2_kg_hr=st.Hydrogen_In.F_mass, H2_kg_per_tonne_fuel=st.Hydrogen_In.F_mass / fuel_kg * 1000,
                installed_MM_USD=tea.installed_equipment_cost / 1e6, FCI_MM_USD=tea.FCI / 1e6,
                FOC_MM_USD_yr=tea.FOC / 1e6, VOC_MM_USD_yr=tea.VOC / 1e6, sales_MM_USD_yr=tea.sales / 1e6,
                ethanol_cost_share=st.Ethanol_In.cost * hrs / (tea.VOC + tea.FOC),
                # New audit columns: all values are INR per litre of SAF at the model battery limit.
                ethanol_feed_cost_INR_L_SAF=ethanol_feed_cost_INR_L,
                hydrogen_feed_cost_INR_L_SAF=hydrogen_feed_cost_INR_L,
                naphtha_credit_INR_L_SAF=rn_credit_INR_L,
                diesel_credit_INR_L_SAF=rd_credit_INR_L,
                total_coproduct_credit_INR_L_SAF=rn_credit_INR_L + rd_credit_INR_L,
                annual_VOC_INR_L_SAF=annual_voc_inr_l,
                annual_FOC_INR_L_SAF=annual_foc_inr_l,
                capital_tax_finance_return_residual_INR_L_SAF=(
                    mjsp_inr_l - annual_voc_inr_l - annual_foc_inr_l
                    if np.isfinite(annual_voc_inr_l) and np.isfinite(annual_foc_inr_l) else np.nan
                ),
                ethanol_to_SAF_volume_ratio=st.Ethanol_In.F_vol / st.SAF.F_vol if st.SAF.F_vol else np.nan,
                SAF_volume_yield_per_feed=st.SAF.F_vol / st.Ethanol_In.F_vol if st.Ethanol_In.F_vol else np.nan,
                **process_mass_balance_diagnostics(sys),
                **elemental_balance_errors(sys))


def baseline():
    return pd.Series(results(*run()))


def sweep_ethanol_route():
    rows = []
    for r in cfg.S['ethanol_exmill_INR_L']:
        rows.append(dict(route=r, **results(*run(ethanol_route=r))))
    return pd.DataFrame(rows)


def sweep_h2_route():
    rows = []
    for r in cfg.S.get('h2_comparison_routes', tuple(cfg.S['h2_INR_kg'])):
        rows.append(dict(route=r, **results(*run(h2_route=r))))
    return pd.DataFrame(rows)


def sweep_scale(KLPD=(50, 100, 150, 200, 300, 400)):
    rows = []
    for k in KLPD:
        rows.append(dict(KLPD=k, **results(*run(ethanol_KLPD=k))))
    return pd.DataFrame(rows)


def sweep_T_P(Ts=(373.15, 383.15, 393.15, 403.15, 413.15), Ps=(25e5, 35e5, 45e5)):
    """Return selectivity and economics across oligomerization temperature and pressure."""
    rows = []
    for T, P in itertools.product(Ts, Ps):
        r = results(*run(**{'olig.T': T, 'olig.P': P}))
        rows.append(dict(T_K=T, P_bar=P / 1e5, **r))
    return pd.DataFrame(rows)


def sweep_deactivation(kds=(0.0005, 0.001, 0.002, 0.005, 0.01), cycles=(30, 60, 120)):
    rows = []
    for kd, c in itertools.product(kds, cycles):
        rows.append(dict(kd=kd, cycle_days=c, **results(*run(**{'olig.kd': kd, 'olig.cycle_days': c}))))
    return pd.DataFrame(rows)
