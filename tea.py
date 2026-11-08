"""
tea.py -- discounted-cash-flow economics with Indian finance. Depends on: settings.py (numbers only).
Used by: system.py (builds it), analysis.py (solves MJSP).

Same method as the paper (BioSTEAM TEA, NPV=0 at IRR 10% -> minimum selling price) with India changes:
  * income tax, debt terms and depreciation assumptions are supplied by settings.py
  * depreciation uses a simplified 15%-WDV-shaped annual fraction; it is not a complete statutory tax model
  * location_factor scales calculated fixed capital investment (FCI)
Capital-cost build-up fractions are the Humbird et al. 2011 (NREL/TP-5100-47764) values the paper's TEA also uses.
"""
import numpy as np
import biosteam as bst

class IndiaTEA(bst.TEA):
    def __init__(self, system, s, **kw):
        n = s['duration'][1] - s['duration'][0]
        r = s['wdv_rate']
        dep = np.array([r * (1 - r) ** t for t in range(n)])
        # Do not normalize: WDV leaves a residual book fraction after the project horizon.
        # This is still a simplified tax proxy: the model does not split depreciable asset blocks
        # or model terminal disposal proceeds / tax recapture.
        self_depreciation_residual = (1 - r) ** n
        super().__init__(system, IRR=s['IRR'], duration=s['duration'], depreciation=dep,
                         income_tax=s['income_tax'], operating_days=s['operating_days'], lang_factor=None,
                         construction_schedule=s['construction_schedule'], startup_months=3,
                         startup_FOCfrac=1., startup_VOCfrac=0.75, startup_salesfrac=0.5,
                         WC_over_FCI=s['WC_over_FCI'], finance_interest=s['finance_interest'],
                         finance_years=s['finance_years'], finance_fraction=s['finance_fraction'])
        self.s = s
        self.depreciation_remaining_fraction = self_depreciation_residual
        self.labor_cost = s['labor_USD_yr']; self.labor_burden = 0.90
        self.property_insurance, self.maintenance = 0.007, 0.03        # Humbird 2011 / paper's cellulosic TEA

    def _DPI(self, installed_equipment_cost):   # + warehouse 4%, site development 9%, additional piping 4.5%
        return installed_equipment_cost * (1 + 0.04 + 0.09 + 0.045)
    def _TDC(self, DPI):                         # direct costs (no further adders)
        return DPI
    def _FCI(self, TDC):                         # indirect: prorateable 10, field 10, construction 20, contingency 10, other 10
        return TDC * (1 + 0.10 + 0.10 + 0.20 + 0.10 + 0.10) * self.s['location_factor']
    def _FOC(self, FCI):
        return FCI * (self.property_insurance + self.maintenance) + self.labor_cost * (1 + self.labor_burden)
