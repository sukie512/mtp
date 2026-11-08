"""
units.py -- custom BioSTEAM unit classes.  Depends on: asf_model.py, chemicals.py.  Used by: system.py.

 CatalystReactor      generic catalytic fixed bed: catalyst mass = feed/WHSV, pressure-vessel cost, catalyst makeup stream
   DehydrationReactor ethanol -> ethylene + water (adiabatic, fixed 99.5% conversion)
   ASFOligomerizer    ethylene -> C4..C18+ olefins, selectivity from ASF chain-growth model, deactivation-averaged conversion
   Hydrogenator       olefins + H2 -> paraffins (adiabatic, 100%)
 StorageTank          generic power-law tank/vessel cost (ethanol, H2, products)
"""
import warnings

import numpy as np
import biosteam as bst

try:
    from .asf_model import oligomer_weight_fractions, alpha_from_T_P, calibrate_beta0, conversion
    from .atj_chemicals import OLEFINS, PARAFFINS
except ImportError:
    from asf_model import oligomer_weight_fractions, alpha_from_T_P, calibrate_beta0, conversion
    from atj_chemicals import OLEFINS, PARAFFINS

def vessel_purchase_cost(V_m3, P_Pa, LD=3.0, sigma=15000., E=0.85):
    """Vertical carbon-steel pressure vessel, Seider et al. 'Product & Process Design Principles' 4th ed. (Wiley 2017)
    correlations (CE=500 basis) -- coefficients typed from memory: VERIFY against the book before publishing."""
    warnings.warn(
        "Custom pressure-vessel cost correlation in units.py is not yet verified against its cited source; "
        "treat reactor vessel purchase costs and derived FCI as preliminary.",
        RuntimeWarning,
        stacklevel=2,
    )
    D = (4 * V_m3 / (np.pi * LD)) ** (1 / 3); L = LD * D
    Dft, Lft = D * 3.28084, L * 3.28084
    Pg = max(P_Pa / 6894.76 - 14.7, 15.)
    tp = max(Pg * Dft * 12 / (2 * sigma * E - 1.2 * Pg), 0.25) + 0.125            # wall thickness [in]
    W = np.pi * (Dft + tp / 12) * (Lft + 0.8 * Dft) * (tp / 12) * 490.             # shell weight [lb]
    Cv = np.exp(7.0132 + 0.18255 * np.log(W) + 0.02297 * np.log(W) ** 2)
    Cpl = 410 * Dft ** 0.7396 * Lft ** 0.70684
    return (Cv + Cpl) * bst.CE / 500.

class CatalystReactor(bst.Unit):
    """ins = (feed, catalyst_makeup).  catalyst makeup is a purchased feed stream whose flow is
    inventory / lifetime / 8760 (this is the 'replacement cost' line of the TEA)."""
    _N_ins, _N_outs = 2, 1
    _F_BM_default = {'Reactor': 4.16, 'Initial catalyst': 1.0}
    _units = {'Catalyst mass': 'kg', 'Reactor volume': 'm3'}
    cat_id = None

    def __init__(self, ID='', ins=None, outs=(), thermo=None, T=None, P=None, whsv=1., cat_life_yr=1.,
                 bed_density=700., isothermal=False):
        super().__init__(ID, ins, outs, thermo)
        self.T, self.P, self.whsv, self.cat_life_yr = T, P, whsv, cat_life_yr
        self.bed_density, self.isothermal = bed_density, isothermal

    def _react(self, feed, out):  raise NotImplementedError

    def _run(self):
        feed, cat = self.ins; out, = self.outs
        out.mol[:] = 0; out.mol[:] = feed.mol            # aggregate moles of all phases
        out.phase = 'g'
        self._react(feed, out)
        out.T = self.T if (self.isothermal or self.T) else feed.T
        out.P = self.P
        m_cat = feed.F_mass / self.whsv
        cat.empty(); cat.imass[self.cat_id] = m_cat / self.cat_life_yr / 8760.   # kg/hr of makeup
        self.m_cat = m_cat

    def _design(self):
        feed = self.ins[0]
        self.design_results['Catalyst mass'] = self.m_cat
        self.design_results['Reactor volume'] = self.m_cat / self.bed_density / 0.5   # bed fraction 0.5
        duty = self.outs[0].H - feed.H
        self.add_heat_utility(duty, self.T or feed.T)

    def _cost(self):
        self.baseline_purchase_costs['Reactor'] = vessel_purchase_cost(
            self.design_results['Reactor volume'], self.P)
        # initial catalyst charge is capital
        price = self.ins[1].price or 0.
        self.baseline_purchase_costs['Initial catalyst'] = price * self.m_cat

class DehydrationReactor(CatalystReactor):
    cat_id = 'Syndol'
    def __init__(self, *a, X=0.995, **k):
        super().__init__(*a, **k); self.X = X
    def _react(self, feed, out):
        n = feed.imol['Ethanol'] * self.X
        out.imol['Ethanol'] -= n; out.imol['Ethylene'] += n; out.imol['Water'] += n

class ASFOligomerizer(CatalystReactor):
    """mode='asf' (default): chain-growth selectivity computed from T, P via alpha (the model developed in this
    thesis). mode='fixed_literature': reproduces the PAPER's own assumed split (20% C4 / 15% C6 / 62% C10 / 3%
    C18, from its repo's etj_settings.py) regardless of T, P -- use this for validation against the paper
    (see validate_paper.py) or as the literature baseline scenario an external review (Oct 2026) recommended
    keeping alongside the ASF model, rather than treating 63% SAF as a fixed truth. NOTE (same review, verified
    independently -- see asf_model.max_c8_c16_share): no chain-growth model, single- or multi-population, can
    reach the paper's 63% C8-C16 assumption; the two selectivity pictures are structurally different, not just
    numerically different, and that gap IS the reported finding, not a bug to be fitted away."""
    cat_id = 'Nickel_SiAl'
    FIXED_SPLIT = {2: 0.20, 3: 0.15, 5: 0.62, 9: 0.03}    # k: weight fraction (paper's repo: C4 .20, C6 .15, C10 .62, C18 .03)
    def __init__(self, *a, X0=0.993, c8plus_ref=0.63, dE=15e3, kd=0.002, cycle_days=60., mode='asf', **k):
        super().__init__(*a, isothermal=True, **k)
        self.X0, self.dE, self.kd, self.cycle_days, self.c8plus_ref, self.mode = X0, dE, kd, cycle_days, c8plus_ref, mode
        self.beta0 = calibrate_beta0(c8plus_ref)[1]      # calibrates alpha to the Heveling 63 wt% C8+ point (used only in mode='asf')
    @property
    def alpha(self): return float(alpha_from_T_P(self.T, self.P / 1e5, self.beta0, self.dE))
    def _react(self, feed, out):
        X = conversion(self.X0, self.kd, self.cycle_days)    # cycle-average conversion after deactivation
        if self.mode == 'fixed_literature':
            w = np.zeros(9)
            for k, frac in self.FIXED_SPLIT.items(): w[k - 1] = frac
        else:
            w = oligomer_weight_fractions(self.alpha); w = np.r_[w[:8], w[8:].sum()]   # lump k>=9 into C18
        n0 = feed.imol['Ethylene']
        self.X_avg, self.w = X, w
        for k in range(2, 10):
            nc = n0 * X * w[k - 1]                      # total converted ethylene is distributed over k >= 2 products
            out.imol['Ethylene'] -= nc
            out.imol[OLEFINS[k]] += nc / k

class Hydrogenator(CatalystReactor):
    cat_id = 'CobaltMolybdenum'
    def _react(self, feed, out):
        for k in range(2, 10):
            n = feed.imol[OLEFINS[k]] * 1.0
            out.imol[OLEFINS[k]] -= n; out.imol[PARAFFINS[k]] += n; out.imol['Hydrogen'] -= n

class StorageTank(bst.Unit):
    """Power-law cost  C = C0 * (CE/CE0) * (capacity/cap0)**exp  * n_units.  Capacity in gal (liquids) or kg (H2).
    Sources (carried from the paper's repo atj_bst_units.py -- VERIFY the originals):
      ethanol : Humbird et al. 2011 NREL/TP-5100-47764 (C0=1.7*1.34e6 USD, 750,000 gal, CE0=521.9, exp 0.7)
      product : Dutta et al. 2015 PNNL-23823 (C0=1.5534e6 USD, 500,000 gal, CE0=567.3, exp 0.7)
      H2      : Amos 1998 NREL/TP-570-25106 (pressurised vessels; repo uses 600*500 USD at 500/2.2 kg, exp 0.75,
                max 1300 kg/vessel). CORRECTION: repo applied NO CEPCI update to H2 tanks; we scale from CE0=389.5 (1998) -- check value."""
    _N_ins, _N_outs = 1, 1
    _F_BM_default = {'Tank': 1.0}
    _units = {'Capacity': 'gal or kg'}
    def __init__(self, ID='', ins=None, outs=(), thermo=None, kind='liquid', days=7, C0=1.5534e6,
                 cap0=500000., CE0=567.3, exp=0.7, max_unit=None):
        super().__init__(ID, ins, outs, thermo)
        self.kind, self.days, self.C0, self.cap0, self.CE0, self.exp, self.max_unit = kind, days, C0, cap0, CE0, exp, max_unit
    def _run(self): self.outs[0].copy_like(self.ins[0])
    def _design(self):
        f = self.ins[0]
        cap = f.F_mass * self.days * 24 if self.kind == 'mass' else f.F_vol * 264.172 * self.days * 24
        self.design_results['Capacity'] = cap
        self.n = int(np.ceil(cap / self.max_unit)) if self.max_unit else 1
    def _cost(self):
        cap = self.design_results['Capacity'] / self.n
        one = self.C0 * (bst.CE / self.CE0) * (cap / self.cap0) ** self.exp
        self.baseline_purchase_costs['Tank'] = one * self.n