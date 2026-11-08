"""
uncertainty.py -- Monte Carlo (Latin hypercube) on the India model. Depends on: system.py, settings.py, analysis.py.

Method = the paper's (BioSTEAM Model, LHS, Spearman), with the paper-notebook bugs fixed:
  * every price setter writes `s[...]` then calls apply_prices() -> change really reaches the streams
  * naphtha setter writes RN (paper wrote RD); catalyst-LIFETIME setter writes lifetime (paper wrote the price)
  * only distributions that are NOT backed by data are flagged: 'PLACEHOLDER' ranges must be replaced by cited ranges
kind='coupled' = changes the process -> flowsheet re-simulated; kind='isolated' = economics only -> cheap.
"""
import numpy as np, pandas as pd
import chaospy as shape
import biosteam as bst
try:
    from .system import apply_prices
    from . import settings as cfg
except ImportError:  # support running the repository as a flat script folder
    from system import apply_prices
    import settings as cfg

def build_model(sys, tea, F, s, MJSP_stream='SAF'):
    model = bst.Model(sys)
    st, U = F.stream, F.unit
    P = model.parameter

    def add(name, setter, element, dist, kind, units=''):
        P(setter, element=element, name=name, distribution=dist, kind=kind, units=units)

    # ---------- process (coupled) ----------
    add('Oligomerization T', lambda v: setattr(U.R202, 'T', v), U.R202, shape.Triangle(373.15, 393.15, 413.15), 'coupled', 'K')    # Heveling 1998 +-20 K (PLACEHOLDER range)
    add('Oligomerization P', lambda v: setattr(U.R202, 'P', v), U.R202, shape.Triangle(30e5, 35e5, 40e5), 'coupled', 'Pa')
    add('ASF dE (Eterm-Eprop)', lambda v: setattr(U.R202, 'dE', v), U.R202, shape.Uniform(5e3, 30e3), 'coupled', 'J/mol')       # PLACEHOLDER: fit to data
    add('Olig. conversion X0', lambda v: setattr(U.R202, 'X0', v), U.R202, shape.Triangle(0.90, 0.993, 0.999), 'coupled')
    add('Olig. deactivation kd', lambda v: setattr(U.R202, 'kd', v), U.R202, shape.Uniform(5e-4, 1e-2), 'coupled', '1/day')    # PLACEHOLDER
    add('Olig. cycle length', lambda v: setattr(U.R202, 'cycle_days', v), U.R202, shape.Uniform(30, 120), 'coupled', 'day')
    add('Olig. WHSV', lambda v: setattr(U.R202, 'whsv', v), U.R202, shape.Uniform(1.0, 2.0), 'coupled')
    add('Dehydration conversion', lambda v: setattr(U.R201, 'X', v), U.R201, shape.Triangle(0.97, 0.995, 0.999), 'coupled')
    add('Dehydration WHSV', lambda v: setattr(U.R201, 'whsv', v), U.R201, shape.Uniform(0.24, 0.36), 'coupled')              # +-20% blanket, as in paper
    add('Olig. catalyst life', lambda v: setattr(U.R202, 'cat_life_yr', v), U.R202, shape.Uniform(0.5, 2.0), 'coupled', 'yr')   # CORRECTION: sets lifetime, not price
    add('Hydrogenation catalyst life', lambda v: setattr(U.R203, 'cat_life_yr', v), U.R203, shape.Uniform(2.0, 5.0), 'coupled', 'yr')  # paper: 3-5 yr
    # ---------- economics (isolated) ----------
    def sset(key, sub=None):
        def f(v):
            (s[key].__setitem__(sub, v) if sub else s.__setitem__(key, v)); apply_prices(F, s)
        return f
    route = s['ethanol_route']; base = s['ethanol_exmill_INR_L'][route]
    add('Ethanol ex-mill price', sset('ethanol_exmill_INR_L', route), st.Ethanol_In, shape.Triangle(0.9 * base, base, 1.15 * base), 'isolated', 'INR/L')
    h2 = s['h2_INR_kg'][s['h2_route']]
    add('Hydrogen delivered price', sset('h2_INR_kg', s['h2_route']), st.Hydrogen_In, shape.Triangle(0.77 * h2, h2, 1.27 * h2), 'isolated', 'INR/kg')   # 279-363-461 Rs/kg: Numaligarh bid 279, Emkay 363, IOCL bid 397 + delivery allowance (the +delivery part is a judgement)
    add('Naphtha (RN) price', sset('rn_USD_kg'), st.RN, shape.Uniform(0.60, 1.17), 'isolated', 'USD/kg')   # India naphtha 2026 range 0.62 (Q1) to 1.17 (May), procurementresource.com / expertmarketresearch.com
    add('Diesel (RD) price', sset('rd_USD_kg'), st.RD, shape.Uniform(0.60, 1.10), 'isolated', 'USD/kg')   # India HSD pre-tax ~0.72 USD/kg (HPCL price build-up); range is a judgement for oil-price swings
    add('Electricity tariff', sset('elec_INR_kWh'), st.Ethanol_In, shape.Uniform(5.5, 8.5), 'isolated', 'INR/kWh')   # HT industrial 5.5-7.5 (qbitsenergy) widened for state variation (CEA/SERC)
    add('INR/USD', sset('fx'), st.Ethanol_In, shape.Triangle(90, 95.5, 102), 'isolated')
    add('Location factor', sset('location_factor'), st.Ethanol_In, shape.Uniform(0.8, 1.1), 'isolated')
    add('Loan interest', sset('finance_interest'), st.Ethanol_In, shape.Triangle(0.09, 0.10, 0.115), 'isolated')   # SBI MCLR 8.85-8.95% + spread (spread assumed)
    add('Natural gas price', sset('ng_INR_kg'), st.Ethanol_In, shape.Triangle(35, 50, 79), 'isolated', 'INR/kg')   # APM USD7 -> Rs35 ; LNG USD15.8 -> Rs79 (PPAC / FIPI Jun 2026)
    add('Labor cost', sset('labor_USD_yr'), st.Ethanol_In, shape.Uniform(0.8e6, 2.5e6), 'isolated', 'USD/yr')
    for k in ('dehyd', 'olig', 'hydgn'):
        base_c = s['cat_price_USD_kg'][k]
        add(f'{k} catalyst price', sset('cat_price_USD_kg', k), st['Cat_' + k], shape.Uniform(0.5 * base_c, 1.5 * base_c), 'isolated', 'USD/kg')   # paper: 50% variation

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