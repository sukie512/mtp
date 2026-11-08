"""
uncertainty.py -- Monte Carlo (Latin hypercube) on the India model.

Process parameters marked 'coupled' trigger a flowsheet re-simulation; economic parameters marked
'isolated' update prices or TEA inputs without rebuilding material flows. Every sampled economic
input must be applied to the live stream, utility, or TEA object as well as the settings dictionary.
"""
import numpy as np
import pandas as pd
import chaospy as shape
import biosteam as bst

try:
    from .system import apply_prices
    from . import settings as cfg
except ImportError:  # support running the repository as a flat script folder
    from system import apply_prices
    import settings as cfg


def make_setting_setter(s, F, tea, key, sub=None, tea_attribute=None):
    """Create a Monte Carlo setter that updates settings and the live model.

    Price and utility values are propagated through apply_prices(); TEA-owned
    economic inputs (for example labour and debt interest) are also written to
    the corresponding live TEA attribute.
    """
    def setter(v):
        value = float(v)
        if sub is None:
            s[key] = value
        else:
            s[key][sub] = value
        apply_prices(F, s)
        if tea_attribute is not None:
            setattr(tea, tea_attribute, value)
    return setter


def set_oligomerization_temperature(units, value):
    """Keep oligomerization reactor and its upstream heater at the sampled temperature."""
    units.H203.T = float(value)
    units.R202.T = float(value)


def set_oligomerization_pressure(units, value):
    """Keep the ethylene compressor discharge and oligomerization reactor at sampled pressure."""
    units.K202.P = float(value)
    units.R202.P = float(value)


def build_model(sys, tea, F, s, MJSP_stream='SAF'):
    model = bst.Model(sys)
    st, U = F.stream, F.unit
    P = model.parameter

    def add(name, setter, element, dist, kind, units=''):
        P(setter, element=element, name=name, distribution=dist, kind=kind, units=units)

    # ---------- process (coupled) ----------
    add('Oligomerization T', lambda v: set_oligomerization_temperature(U, v), U.R202,
        shape.Triangle(373.15, 393.15, 413.15), 'coupled', 'K')  # scenario range around baseline; verify against Heveling operating data
    add('Oligomerization P', lambda v: set_oligomerization_pressure(U, v), U.R202,
        shape.Triangle(30e5, 35e5, 40e5), 'coupled', 'Pa')  # scenario range; not a measured probability distribution
    add('ASF dE (Eterm-Eprop)', lambda v: setattr(U.R202, 'dE', v), U.R202,
        shape.Uniform(5e3, 30e3), 'coupled', 'J/mol')  # UNRESOLVED: dE is not fitted to multi-temperature selectivity data
    add('Olig. conversion X0', lambda v: setattr(U.R202, 'X0', v), U.R202,
        shape.Triangle(0.90, 0.993, 0.999), 'coupled')  # judgement range pending catalyst-performance evidence
    add('Olig. deactivation kd', lambda v: setattr(U.R202, 'kd', v), U.R202,
        shape.Uniform(5e-4, 1e-2), 'coupled', '1/day')  # UNRESOLVED: obtain time-on-stream deactivation data
    add('Olig. cycle length', lambda v: setattr(U.R202, 'cycle_days', v), U.R202,
        shape.Uniform(30, 120), 'coupled', 'day')  # scenario range; replacement interval is not experimentally established
    add('Olig. WHSV', lambda v: setattr(U.R202, 'whsv', v), U.R202,
        shape.Uniform(1.0, 2.0), 'coupled')  # engineering scenario range around 1.5 h-1 reference
    add('Dehydration conversion', lambda v: setattr(U.R201, 'X', v), U.R201,
        shape.Triangle(0.97, 0.995, 0.999), 'coupled')  # judgement range around literature/base conversion
    add('Dehydration WHSV', lambda v: setattr(U.R201, 'whsv', v), U.R201,
        shape.Uniform(0.24, 0.36), 'coupled')  # +/-20% scenario range around 0.30 h-1
    add('Olig. catalyst life', lambda v: setattr(U.R202, 'cat_life_yr', v), U.R202,
        shape.Uniform(0.5, 2.0), 'coupled', 'yr')  # scenario range; source-specific catalyst life required
    add('Hydrogenation catalyst life', lambda v: setattr(U.R203, 'cat_life_yr', v), U.R203,
        shape.Uniform(2.0, 5.0), 'coupled', 'yr')  # literature-derived range; verify catalyst-specific basis

    # ---------- economics (isolated) ----------
    sset = lambda key, sub=None, tea_attribute=None: make_setting_setter(s, F, tea, key, sub, tea_attribute)

    route = s['ethanol_route']
    base = s['ethanol_exmill_INR_L'][route]
    add('Ethanol ex-mill price', sset('ethanol_exmill_INR_L', route),
        st.Ethanol_In, shape.Triangle(0.9 * base, base, 1.15 * base), 'isolated', 'INR/L')  # scenario uncertainty around route-specific input

    h2 = s['h2_INR_kg'][s['h2_route']]
    add('Hydrogen delivered price', sset('h2_INR_kg', s['h2_route']),
        st.Hydrogen_In, shape.Triangle(0.77 * h2, h2, 1.27 * h2), 'isolated', 'INR/kg')  # includes a judgement delivery allowance; not a plant-gate quote

    add('Naphtha (RN) price', sset('rn_USD_kg'), st.RN,
        shape.Uniform(0.60, 1.17), 'isolated', 'USD/kg')  # India 2026 price range; source references in settings.py
    add('Diesel (RD) price', sset('rd_USD_kg'), st.RD,
        shape.Uniform(0.60, 1.10), 'isolated', 'USD/kg')  # scenario range around an older India pre-tax price anchor
    add('Electricity tariff', sset('elec_INR_kWh'), st.Ethanol_In,
        shape.Uniform(5.5, 8.5), 'isolated', 'INR/kWh')  # widened state-tariff scenario range; replace with target-state SERC data
    add('INR/USD', sset('fx'), st.Ethanol_In,
        shape.Triangle(90, 95.5, 102), 'isolated')  # exchange-rate scenario range; refresh at analysis date
    add('Location factor', sset('location_factor'), st.Ethanol_In,
        shape.Uniform(0.8, 1.1), 'isolated')  # UNRESOLVED: India location factor needs EPC / cost-index evidence
    add('Loan interest', sset('finance_interest', tea_attribute='finance_interest'),
        st.Ethanol_In, shape.Triangle(0.09, 0.10, 0.115), 'isolated')  # assumed lending spread; replace with lender term sheet
    add('Natural gas price', sset('ng_INR_kg'), st.Ethanol_In,
        shape.Triangle(35, 50, 79), 'isolated', 'INR/kg')  # India gas-price anchors; verify GCV basis and delivered cost
    add('Labor cost', sset('labor_USD_yr', tea_attribute='labor_cost'),
        st.Ethanol_In, shape.Uniform(0.8e6, 2.5e6), 'isolated', 'USD/yr')  # UNRESOLVED: staff count and salary build-up required

    for k in ('dehyd', 'olig', 'hydgn'):
        base_c = s['cat_price_USD_kg'][k]
        add(f'{k} catalyst price', sset('cat_price_USD_kg', k),
            st['Cat_' + k], shape.Uniform(0.5 * base_c, 1.5 * base_c), 'isolated', 'USD/kg')  # +/-50% scenario range; verify catalyst-specific quotes

    @model.metric(name='MJSP', units='USD/gal')
    def mjsp():
        return tea.solve_price(st.SAF) * st.SAF.rho / 264.172

    @model.metric(name='MJSP', units='INR/L')
    def mjsp_inr():
        return tea.solve_price(st.SAF) * st.SAF.rho / 1000 * s['fx']

    @model.metric(name='SAF yield', units='MM gal/yr')
    def saf_yield():
        return st.SAF.F_vol * 264.172 * tea.operating_hours / 1e6

    return model


def run_mc(N=300, seed=1234, **override):
    try:
        from .analysis import run
    except ImportError:  # support flat-folder execution
        from analysis import run
    sys, tea, F, s = run(**override)
    model = build_model(sys, tea, F, s)
    samples = model.sample(N, rule='L', seed=seed)
    model.load_samples(samples)
    model.evaluate()
    return model


def summarize(model):
    """Percentiles of MJSP in INR/L."""
    col = [c for c in model.table.columns if 'MJSP' in str(c) and 'INR' in str(c)][0]
    y = model.table[col]
    return pd.Series({'P5': y.quantile(.05), 'P25': y.quantile(.25), 'P50': y.median(),
                      'P75': y.quantile(.75), 'P95': y.quantile(.95)})
