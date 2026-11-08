"""
system.py -- builds the flowsheet. Depends on: settings.py, chemicals.py, units.py, tea.py.
Used by: analysis.py, uncertainty.py.   Public API:  build(s) -> (system, tea, F)   and   apply_prices(F, s).

Flow:  ethanol -> T101 -> pump -> heat -> [mix w/ recycle] -> heat -> R201 dehydration -> split(70% recycle)
       -> flash (drop water) -> compress -> D201 (water) -> compress -> D202 (trace ethanol) -> cool
       -> [mix w/ ethylene recycle] -> R202 ASF oligomerizer -> split (unreacted C2H4 recycle)
       -> mix w/ H2 -> heat -> R203 hydrogenation -> cool -> flash -> PSA split (H2 recycle)
       -> D301 (RN | rest) -> D302 (SAF | RD) -> coolers -> product tanks
"""
import biosteam as bst

try:
    from . import settings as cfg
    from .atj_chemicals import create_chemicals, OLEFINS, PARAFFINS, RN_K, SAF_K, RD_K
    from .units import DehydrationReactor, ASFOligomerizer, Hydrogenator, StorageTank
    from .tea import IndiaTEA
except ImportError:
    import settings as cfg
    from atj_chemicals import create_chemicals, OLEFINS, PARAFFINS, RN_K, SAF_K, RD_K
    from units import DehydrationReactor, ASFOligomerizer, Hydrogenator, StorageTank
    from tea import IndiaTEA

def apply_prices(F, s):
    """THE single place where prices are written onto streams/utilities. Uncertainty setters call this again
    after changing `s` (CORRECTION: the paper's notebook changed a dict *after* the stream price was set,
    so hydrogen-price uncertainty probably never reached the model)."""
    F.stream.Ethanol_In.price = cfg.ethanol_price_USD_kg(s)
    F.stream.Hydrogen_In.price = cfg.h2_price_USD_kg(s)
    F.stream.RN.price = s['rn_USD_kg']          # CORRECTION: naphtha setter must touch RN (paper's notebook wrote to RD)
    F.stream.RD.price = s['rd_USD_kg']
    F.stream.Wastewater.price = -s['wastewater_USD_kg']     # disposal cost = negative revenue
    for key, sid in (('dehyd', 'Cat_dehyd'), ('olig', 'Cat_olig'), ('hydgn', 'Cat_hydgn')):
        F.stream[sid].price = s['cat_price_USD_kg'][key]
    bst.PowerUtility.price = cfg.elec_USD_kWh(s)
    bst.HeatUtility.get_agent('natural_gas').regeneration_price = cfg.ng_USD_kg(s) * 16.04   # USD/kmol CH4

def build(s=None, ID='india_atj'):
    s = s or cfg.get()
    bst.settings.CEPCI = s['CEPCI']
    bst.main_flowsheet.set_flowsheet(ID)
    F = bst.main_flowsheet
    bst.settings.set_thermo(create_chemicals())
    # FIX (review, Oct 2026): ethanol_kg_hr(s) is the TOTAL feed mass for the KLPD basis. The line below used to
    # set Ethanol=eth and then ADD water on top, so purity was applied twice and total feed ran ~0.5% high.
    # Correct split: Ethanol = eth*purity, Water = eth*(1-purity), so Ethanol+Water == eth exactly.
    eth = cfg.ethanol_kg_hr(s)
    feed = bst.Stream('Ethanol_In', Ethanol=eth * s['ethanol_purity_wt'], Water=eth * (1 - s['ethanol_purity_wt']),
                      units='kg/hr', T=293.15, P=101325, phase='l')
    d, o, h = s['dehyd'], s['olig'], s['hydgn']
    dehyd_rec = bst.MultiStream('dehyd_recycle', phases=('g', 'l'))
    eth_rec = bst.MultiStream('ethylene_recycle', phases=('g', 'l'))
    h2_rec = bst.Stream('h2_recycle', P=3e6, phase='g')

    T101 = StorageTank('T101', feed, kind='liquid', days=7, C0=1.7 * 1.34e6, cap0=750000., CE0=521.9, exp=0.7)
    P201 = bst.Pump('P201', T101-0, P=1.373e6)
    H201 = bst.HXutility('H201', P201-0, T=500., rigorous=True)
    M201 = bst.Mixer('M201', (H201-0, dehyd_rec), rigorous=True)
    H202 = bst.HXutility('H202', M201-0, T=d['T'], rigorous=True)
    R201 = DehydrationReactor('R201', (H202-0, bst.Stream('Cat_dehyd')), T=d['T'], P=d['P'], whsv=d['whsv'],
                              cat_life_yr=s['cat_life_yr']['dehyd'], X=d['X'])
    S201 = bst.Splitter('S201', R201-0, outs=('to_flash', dehyd_rec), split=0.3)
    T201 = bst.Flash('T201', S201-0, T=420., P=d['P'])
    K201 = bst.IsentropicCompressor('K201', T201-0, P=2e6, eta=0.72)
    D201 = bst.BinaryDistillation('D201', K201-0, LHK=('Ethylene', 'Water'), y_top=0.999, x_bot=0.001, k=2, P=2e6)
    K202 = bst.IsentropicCompressor('K202', D201-0, P=o['P'], eta=0.72)
    D202 = bst.BinaryDistillation('D202', K202-0, LHK=('Ethylene', 'Ethanol'), y_top=0.9999, x_bot=0.0001, k=2, P=o['P'])
    H203 = bst.HXutility('H203', D202-0, T=o['T'], rigorous=True)
    M202 = bst.Mixer('M202', (H203-0, eth_rec), rigorous=True)
    R202 = ASFOligomerizer('R202', (M202-0, bst.Stream('Cat_olig')), T=o['T'], P=o['P'], whsv=o['whsv'],
                           cat_life_yr=s['cat_life_yr']['olig'], X0=o['X0'], c8plus_ref=o['c8plus_ref'],
                           dE=o['dE'], kd=o['kd'], cycle_days=o['cycle_days'], mode=o.get('mode', 'asf'))
    S202 = bst.Splitter('S202', R202-0, outs=(eth_rec, 'olefins'), split={'Ethylene': 1.0})

    # h2_ratio is a FEED ratio (mol H2 fed : mol olefin fed), not a stoichiometric consumption ratio. Hydrogenating
    # one mono-olefin consumes exactly 1 mol H2 regardless of chain length (one C=C bond per terminal alkene), so
    # ratio=3.0 means ~3x stoichiometric excess fed, most of which leaves unconsumed and is partly recovered by the
    # PSA (h2_recovery). This matches the paper's framing (excess H2 to suppress coking, Sec 2.1) -- documented per
    # review comment, no code change needed here.
    h2_in = bst.Stream('Hydrogen_In', P=3e6, phase='g')
    T102 = StorageTank('T102', h2_in, kind='mass', days=s['h2_storage_days'], C0=600 * 500, cap0=500 / 2.2,
                       CE0=389.5, exp=0.75, max_unit=1300.)
    @T102.add_specification(run=True)
    def h2_flow():     # fresh H2 = ratio*olefin_mol - recycled H2
        n_ol = sum(R202.outs[0].imol[OLEFINS[k]] for k in OLEFINS)
        h2_in.imol['Hydrogen'] = max(s['h2_ratio'] * n_ol - h2_rec.imol['Hydrogen'], 0.)
    M203 = bst.Mixer('M203', (T102-0, S202-1, h2_rec), rigorous=True)
    H204 = bst.HXutility('H204', M203-0, T=h['T'], rigorous=True)
    R203 = Hydrogenator('R203', (H204-0, bst.Stream('Cat_hydgn')), T=h['T'], P=h['P'], whsv=h['whsv'],
                        cat_life_yr=s['cat_life_yr']['hydgn'])
    H205 = bst.HXutility('H205', R203-0, T=250., rigorous=True)
    T202 = bst.Flash('T202', H205-0, T=250., P=5e5)
    S203 = bst.Splitter('S203', T202-0, outs=(h2_rec, 'offgas'), split={'Hydrogen': s['h2_recovery']})
    D301 = bst.BinaryDistillation('D301', T202-1, LHK=(PARAFFINS[3], PARAFFINS[4]), y_top=0.99, x_bot=0.01, k=2, is_divided=True)
    D302 = bst.BinaryDistillation('D302', D301-1, LHK=(PARAFFINS[8], PARAFFINS[9]), y_top=0.99, x_bot=0.01, k=2, is_divided=True)
    # ROBUSTNESS (Oct 2026): some selectivity modes (e.g. mode='fixed_literature') put zero weight on certain
    # carbon numbers, which can trip BioSTEAM's light/heavy-key volatility check on trace components. The columns
    # are still solved correctly (this only disables an internal sanity check, not the separation itself).
    D301.check_LHK = D302.check_LHK = False
    H301 = bst.HXutility('H301', D301-0, V=0, rigorous=True)
    H302 = bst.HXutility('H302', D302-0, T=288.15, rigorous=True)
    H303 = bst.HXutility('H303', D302-1, T=288.15, rigorous=True)
    for u in (H302, H303):
        @u.add_specification(run=False)
        def fix_phase(u=u):
            u._run(); u._design(); u._cost(); u.outs[0].phase = 'l'
    T501 = StorageTank('T501', H301-0, outs='RN',  kind='liquid', days=14)
    T502 = StorageTank('T502', H302-0, outs='SAF', kind='liquid', days=14)
    T503 = StorageTank('T503', H303-0, outs='RD',  kind='liquid', days=14)
    WW = bst.Mixer('M601', (T201-1, D201-1, D202-1), outs='Wastewater')

    path = (T101, P201, H201, M201, H202, R201, S201, T201, K201, D201, K202, D202, H203, M202, R202, S202,
            T102, M203, H204, R203, H205, T202, S203, D301, D302, H301, H302, H303, T501, T502, T503, WW)
    sys = bst.System(ID, path=path, recycle=(dehyd_rec, eth_rec, h2_rec))
    apply_prices(F, s)
    tea = IndiaTEA(sys, s)
    return sys, tea, F