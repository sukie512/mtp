"""
validate_paper.py -- VALIDATION: run YOUR model with the PAPER's US inputs and compare with the paper's reported numbers.
Run in the same folder as your model files:   python validate_paper.py   (about 1 minute)

Paper = Wadgama & Shi 2026, Sustain. Sci. Technol. 3, 034002 (text + Fig. 2). Paper values used for comparison:
  MJSP 8.89 USD/gal ; ethanol contributes 6.41 USD/gal ; TIC 58.85 MM USD ; TOC 71.08 MM USD
  TOC shares: ethanol 75.5 %, hydrogen 11.2 %, fixed 10.5 %, utilities 2.8 %
  TIC shares: storage 39.5 %, boiler/turbogen 33.6 %, catalytic upgrading 17.6 %, wastewater 6.6 %, fractionation 2.7 %
  Inputs (Sec 2.1-2.2): 9 MM gal/yr SAF, ethanol 2.67 USD/gal, tax 21 %, loan 8 % / 10 yr / 60 % debt, MACRS-7, 30 yr, IRR 10 %,
  H2 (green, delivered) from the NREL/liftoff-based tool, RN/RD prices from the repo (0.71 / 1.888 USD/kg).
Three runs are compared so you can see WHICH modelling choice causes each gap:
  A  = your India-built model, but with US inputs, ASF selectivity (your new model)
  B  = same, but with the paper's FIXED product split (C4 20 / C6 15 / C10 62 / C18 3 wt%, from the repo's etj_settings.py)
"""
import argparse, os, sys, warnings
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import settings as cfg, analysis as A, units, system as SYS

parser = argparse.ArgumentParser(description='Compare the model against the Wadgama & Shi (2026) reference case.')
parser.add_argument('--out', default='final_results', help='Directory for validation CSV and figures (default: final_results)')
args = parser.parse_args()
OUT = os.path.abspath(args.out if os.path.isabs(args.out) else os.path.join(HERE, args.out))
os.makedirs(OUT, exist_ok=True)

PAPER = dict(MJSP=8.89, TIC=58.85, TOC=71.08, eth_share=75.5, h2_share=11.2, fixed_share=10.5, util_share=2.8,
             storage=39.5, bt=33.6, upgrading=17.6, wwt=6.6, fract=2.7)

def us_settings():
    """Paper's US basis written into the same settings dictionary your model already reads."""
    s = cfg.get()
    s['fx'] = 1.0                                           # money inputs are now USD (INR field == USD)
    kg_hr = 9e6 / 264.172 * 776 / (0.56 * 0.8) / (0.9 * 8760)          # repo etj_utils.calculate_ethanol_flow(9) -> ~7486 kg/hr
    s['ethanol_KLPD'] = kg_hr * 24 / s['ethanol_density']
    s['ethanol_exmill_INR_L'] = {'B_heavy': 2.67 / 3.78541}            # 2.67 USD/gal ethanol (paper Sec 2.2)
    s['ethanol_route'] = 'B_heavy'; s['ethanol_transport_INR_L'] = 0.0
    s['h2_INR_kg'] = {'green_offsite': 8.46}; s['h2_route'] = 'green_offsite'   # repo etj_settings price_data['hydrogen'] (USD/kg)
    s['rn_USD_kg'], s['rd_USD_kg'] = 0.71, 1.888                        # repo prices
    s['elec_INR_kWh'] = 0.0782; s['ng_INR_kg'] = 0.218                   # paper/repo electricity; BioSTEAM default natural gas USD/kg
    s['income_tax'] = 0.21; s['finance_interest'] = 0.08; s['location_factor'] = 1.0
    s['labor_USD_yr'] = 2.5e6                                           # paper-style US labour (my earlier note; check repo etj labor cells)
    return s

def paper_split(alpha, kmax=60):
    """Fixed split of the paper's repo, mapped onto our chain lengths: C4 .20, C6 .15, C10 .62, C18 .03."""
    w = np.zeros(kmax); w[1], w[2], w[4], w[8] = 0.20, 0.15, 0.62, 0.03
    return w

def groups(F):
    g = {'storage': ['T101', 'T102', 'T501', 'T502', 'T503'],
         'upgrading': ['P201','H201','M201','H202','R201','S201','T201','K201','D201','K202','D202','H203','M202','R202','S202',
                       'S204','M203','H204','R203','H205','T202','S203'],
         'fract': ['D301', 'D302', 'H301', 'H302', 'H303']}
    return {k: sum(getattr(F.unit, u).installed_cost for u in v if hasattr(F.unit, u)) for k, v in g.items()}

def run_case(label, fixed_split):
    orig = units.oligomer_weight_fractions
    units.oligomer_weight_fractions = paper_split if fixed_split else orig
    try:
        s = us_settings()
        sys_, tea, F = SYS.build(s, ID='val_' + label[0])      # build, then relax the column check (trace ethanol with the fixed split)
        for u in ('D201', 'D202', 'D301', 'D302'):
            getattr(F.unit, u).check_LHK = False
        if fixed_split:                                          # paper's slate has no C8/C12-C16: cut between the lumps it actually has
            F.unit.D301.LHK = ('Hexane', 'Decane'); F.unit.D302.LHK = ('Decane', 'Octadecane')
        sys_.simulate()
        tea.depreciation = 'MACRS7'                                     # paper: MACRS 7-yr, not Indian WDV
        r = A.results(sys_, tea, F, s)
        hrs = tea.operating_hours; st = F.stream
        toc = (tea.VOC + tea.FOC) / 1e6; tic = tea.installed_equipment_cost / 1e6; gp = groups(F); gsum = sum(gp.values())
        row = dict(case=label, MJSP=r['MJSP_USD_gal'], SAF_MMgal=r['SAF_MMgal_yr'], TIC=tic, TOC=toc,
                   eth_share=st.Ethanol_In.cost * hrs / 1e6 / toc * 100, h2_share=st.Hydrogen_In.cost * hrs / 1e6 / toc * 100,
                   fixed_share=tea.FOC / 1e6 / toc * 100, util_share=sys_.utility_cost / 1e6 / toc * 100,
                   storage=gp['storage'] / (tic * 1e6) * 100, upgrading=gp['upgrading'] / (tic * 1e6) * 100,
                   fract=gp['fract'] / (tic * 1e6) * 100, bt=0.0, wwt=0.0,
                   eth_per_gal=st.Ethanol_In.cost * hrs / (st.SAF.F_vol * 264.172 * hrs),
                   RN_rev_per_gal=st.RN.cost * hrs / (st.SAF.F_vol * 264.172 * hrs), RD_rev_per_gal=st.RD.cost * hrs / (st.SAF.F_vol * 264.172 * hrs))
        return row
    finally:
        units.oligomer_weight_fractions = orig

rows = [run_case('A: US inputs + ASF selectivity', False), run_case('B: US inputs + paper split', True)]
df = pd.DataFrame(rows).set_index('case').T
df['PAPER'] = [PAPER['MJSP'], 9.0, PAPER['TIC'], PAPER['TOC'], PAPER['eth_share'], PAPER['h2_share'], PAPER['fixed_share'], PAPER['util_share'],
               PAPER['storage'], PAPER['upgrading'], PAPER['fract'], PAPER['bt'], PAPER['wwt'], 6.41, 1.01, 0.16][:len(df)] if len(df) <= 16 else None
pd.set_option('display.width', 200); print('\n' + '=' * 90 + '\nVALIDATION vs Wadgama & Shi (2026): your model with the paper\'s US inputs\n' + '=' * 90)
print(df.round(2).to_string())
for c in df.columns[:2]:
    gap = (df.loc['MJSP', c] - PAPER['MJSP']) / PAPER['MJSP'] * 100
    print(f"\n>>> {c}: MJSP {df.loc['MJSP', c]:.2f} vs paper 8.89 USD/gal  ->  gap {gap:+.1f} %")
print('\nHow to read: gap < ~10 %  = model reproduces the paper; larger gaps are explained by what your flowsheet omits')
print('(boiler/turbogenerator = 33.6 % of paper capex and a 0.36 USD/gal electricity credit; wastewater plant = 6.6 %)')
df.round(3).to_csv(os.path.join(OUT, 'validation_vs_paper.csv'))
fig, ax = plt.subplots(1, 3, figsize=(16, 4.6)); cs = ['#2a9d8f', '#457b9d', '#e76f51']
cols = list(df.columns)
ax[0].bar(range(3), [df.loc['MJSP', c] for c in cols], color=cs); ax[0].set_xticks(range(3)); ax[0].set_xticklabels(['A: ASF', 'B: paper split', 'PAPER'], rotation=10)
for i, c in enumerate(cols): ax[0].text(i, df.loc['MJSP', c] + .1, f"{df.loc['MJSP', c]:.2f}", ha='center')
ax[0].set_ylabel('MJSP [USD/gal]'); ax[0].set_title('Does the model reproduce 8.89 USD/gal?')
for j, (key, lab) in enumerate([('storage', 'Storage'), ('upgrading', 'Catalytic upgrading'), ('fract', 'Fractionation'), ('bt', 'Boiler/turbogen'), ('wwt', 'Wastewater')]):
    for i, c in enumerate(cols): ax[1].bar(j + (i - 1) * 0.27, df.loc[key, c], 0.27, color=cs[i], label=['A: ASF', 'B: paper split', 'PAPER'][i] if j == 0 else None)
ax[1].set_xticks(range(5)); ax[1].set_xticklabels(['Storage', 'Upgrading', 'Fract.', 'Boiler', 'WWT'], rotation=15); ax[1].set_ylabel('% of installed capital'); ax[1].set_title('Capital split (BT, WWT not modelled)'); ax[1].legend()
for j, (key, lab) in enumerate([('eth_share', 'Ethanol'), ('h2_share', 'Hydrogen'), ('fixed_share', 'Fixed op.'), ('util_share', 'Utilities')]):
    for i, c in enumerate(cols): ax[2].bar(j + (i - 1) * 0.27, df.loc[key, c], 0.27, color=cs[i])
ax[2].set_xticks(range(4)); ax[2].set_xticklabels(['Ethanol', 'Hydrogen', 'Fixed', 'Utilities']); ax[2].set_ylabel('% of operating cost'); ax[2].set_title('Operating-cost split')
plt.tight_layout(); fig.savefig(os.path.join(OUT, 'validation_vs_paper.png'), bbox_inches='tight', dpi=300); fig.savefig(os.path.join(OUT, 'validation_vs_paper.pdf'), bbox_inches='tight')
print(f'\n[saved {os.path.join(OUT, "validation_vs_paper.csv")}, validation_vs_paper.png and validation_vs_paper.pdf]')
