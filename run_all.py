"""
run_all.py  --  RUN THIS FILE.  It calls the model files, prints every result table in the terminal,
saves every chart as a PNG in ./results/ and (unless --no-show) opens all charts at the end.

    python run_all.py              # 100 Monte Carlo samples (~5-8 min), charts pop up at the end
    python run_all.py --n 300      # more Monte Carlo samples
    python run_all.py --no-show    # only save PNGs (no windows)
    python run_all.py --quick      # skip Monte Carlo (about 3 min)

Works with YOUR original files, unchanged, in the SAME folder:
  settings.py asf_model.py atj_chemicals.py units.py tea.py system.py analysis.py uncertainty.py
It only calls functions that exist there: analysis.run / results / baseline / sweep_ethanol_route / sweep_h2_route /
sweep_scale / sweep_T_P / sweep_deactivation ; uncertainty.run_mc / summarize ; asf_model.* ; settings.S
Sources for every input are in the comments of settings.py (tags: VERIFIED-26 / REPO / PLACEHOLDER).
"""
import argparse, os, sys, time, warnings
# Keep scientific warnings visible; suppress only known noisy categories locally if needed.
ap = argparse.ArgumentParser()
ap.add_argument('--n', type=int, default=100); ap.add_argument('--no-show', action='store_true'); ap.add_argument('--quick', action='store_true')
args = ap.parse_args()

import matplotlib
if args.no_show: matplotlib.use('Agg')
import numpy as np, pandas as pd, matplotlib.pyplot as plt
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)
plt.rcParams.update({
    'figure.dpi': 150, 'savefig.dpi': 300, 'savefig.bbox': 'tight',
    'font.family': 'DejaVu Sans', 'font.size': 11,
    'axes.titlesize': 14, 'axes.titleweight': 'bold',
    'axes.labelsize': 12, 'xtick.labelsize': 10, 'ytick.labelsize': 10,
    'legend.fontsize': 10, 'axes.grid': True, 'grid.alpha': 0.22,
    'axes.spines.top': False, 'axes.spines.right': False,
    'lines.linewidth': 2.0, 'lines.markersize': 6,
})
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import settings as cfg, analysis as A
from asf_model import weight_fractions, alpha_from_T_P, calibrate_beta0

import uncertainty as U

def safe(sweep_fn, fallback_rows, label):
    """Call YOUR sweep function. If one operating point crashes the BioSTEAM column solver (e.g. 373 K / 45 bar in
    sweep_T_P), redo that sweep point-by-point with A.run + A.results and skip only the bad points."""
    try:
        return sweep_fn()
    except Exception as e:
        print(f'   note: {label} hit a solver failure ({str(e)[:70]}...); re-running point by point, bad points -> NaN', flush=True)
        rows = []
        result_columns = None
        for extra, kw in fallback_rows:
            try:
                row = A.results(*A.run(**kw))
                result_columns = list(row)
                rows.append(dict(extra, **row))
            except Exception:
                # Determine the output schema at most once; do not rerun the baseline for every failed point.
                if result_columns is None:
                    try: result_columns = list(A.results(*A.run()))
                    except Exception: result_columns = []
                rows.append(dict(extra, **{k: np.nan for k in result_columns}))
        return pd.DataFrame(rows)

T0 = time.time()
def head(t): print('\n' + '=' * 78 + f'\n{t}\n' + '=' * 78, flush=True)
def _free_path(name, ext):
    """Path in results/ for name+ext. If that file is locked (open in Excel / a VS Code tab on Windows),
    use name_<time>.ext instead so the run never crashes after a long computation."""
    p = os.path.join(OUT, name + ext)
    try:
        open(p, 'ab').close(); return p
    except PermissionError:
        p2 = os.path.join(OUT, f"{name}_{time.strftime('%H%M%S')}{ext}")
        print(f'   !! {name}{ext} is open in another program; saving as {os.path.basename(p2)} instead', flush=True); return p2
def save(fig, name):
    """Save slide-ready raster and vector versions of each figure."""
    for i in range(10):
        stem = name if i == 0 else f'{name}_{i}'
        png = _free_path(stem, '.png')
        pdf = os.path.join(OUT, stem + '.pdf')
        try:
            fig.savefig(png, dpi=300, facecolor='white', bbox_inches='tight')
            fig.savefig(pdf, format='pdf', facecolor='white', bbox_inches='tight')
            print(f'   [charts saved: results/{os.path.basename(png)} and {os.path.basename(pdf)}]', flush=True)
            plt.close(fig)
            return
        except OSError as e:
            print(f'   !! could not save {stem} ({e}); retrying with a fresh filename', flush=True)
    raise OSError(f'Failed to save chart {name!r} after multiple retries.')
def table(df, name, cols=None):
    d = df[cols] if cols else df
    print(d.round(4).to_string(index=False)); d.to_csv(_free_path(name, '.csv'), index=False)

# ------------------------------------------------------------------ 1 baseline
head('1. BASELINE: 200 KLPD ethanol (B-heavy molasses), green H2 off-site, Indian finance')
sys_, tea_, F_, s_ = A.run(); base = A.results(sys_, tea_, F_, s_)
print(pd.Series(base).round(3).to_string())
print(f"\n>>> MJSP = {base['MJSP_USD_gal']:.2f} USD/gal = Rs {base['MJSP_INR_L']:.0f}/L ; SAF = {base['SAF_MMgal_yr']:.2f} MM gal/yr")

# ------------------------------------------------------------------ 2 cost breakdown
head('2. WHERE THE MONEY GOES')
hrs = tea_.operating_hours; st = F_.stream
areas = {'Ethanol storage': ['T101'], 'Dehydration': ['P201','H201','M201','H202','R201','S201','T201'],
         'Ethylene purification': ['K201','D201','K202','D202','H203'], 'Oligomerization': ['M202','R202','S202'],
         'H2 storage + hydrogenation': ['T102','M203','H204','R203','H205','T202','S203'],
         'Fractionation': ['D301','D302','H301','H302','H303'], 'Product storage': ['T501','T502','T503']}
cap = {k: sum(getattr(F_.unit, u).installed_cost for u in v if hasattr(F_.unit, u)) / 1e6 for k, v in areas.items()}
saf_gal = st.SAF.F_vol * 264.172 * hrs
p = tea_.solve_price(st.SAF); total = p * st.SAF.F_mass * hrs
eth, h2 = st.Ethanol_In.cost * hrs, st.Hydrogen_In.cost * hrs
cat = sum(st[k].cost for k in ('Cat_dehyd', 'Cat_olig', 'Cat_hydgn')) * hrs
util, ww = sys_.utility_cost, -st.Wastewater.cost * hrs          # utility_cost is already USD/yr
fixed, rn, rd = tea_.FOC, st.RN.cost * hrs, st.RD.cost * hrs
resid = total - (eth + h2 + cat + util + ww + fixed - rn - rd)
items = [('Ethanol', eth), ('Hydrogen', h2), ('Catalysts', cat), ('Utilities', util), ('Wastewater', ww), ('Fixed op. cost', fixed),
         ('RN revenue', -rn), ('RD revenue', -rd), ('Capital+tax+return', resid)]
print('Installed capital by area [MM USD]:'); [print(f'   {k:28s}{v:7.2f}') for k, v in cap.items()]
print('\nMJSP build-up [USD per gal SAF]:'); [print(f'   {n:28s}{v / saf_gal:7.2f}') for n, v in items]
fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
ax[0].barh(list(cap), list(cap.values()), color='#2a9d8f'); ax[0].invert_yaxis()
ax[0].set_xlabel('Installed equipment cost (million USD)'); ax[0].set_title('Installed Capital by Process Area')
ax[0].set_ylabel('Installed capital (million USD)')
vals = [v / saf_gal for _, v in items]; cum = np.cumsum([0] + vals[:-1])
bottoms = [c if v >= 0 else c + v for c, v in zip(cum, vals)]
ax[1].bar([n for n, _ in items], np.abs(vals), bottom=bottoms,
          color=['#d97757' if v > 0 else '#3b8f83' for v in vals])
ax[1].axhline(sum(vals), color='#333333', ls='--', lw=1.2, label='Solved MJSP')
lo = min(0, min(bottoms)); hi = max(max(c + v for c, v in zip(cum, vals)), sum(vals))
ax[1].set_ylim(lo * 1.08 if lo < 0 else 0, hi * 1.12)
ax[1].set_ylabel('Contribution to MJSP (USD per US gallon of SAF)')
ax[1].set_title('Minimum Jet Selling Price Build-Up')
ax[1].legend(frameon=False)
plt.setp(ax[1].get_xticklabels(), rotation=35, ha='right'); fig.set_size_inches(14, 5.5); fig.tight_layout(); save(fig, '01_cost_breakdown')

# ------------------------------------------------------------------ 3 ASF
head('3. OLIGOMERIZATION MODEL: product distribution from Anderson-Schulz-Flory chain growth')
a_ref, b0 = calibrate_beta0(0.63); dE = s_['olig']['dE']
w0 = weight_fractions(a_ref)
print(f'alpha at 393 K / 35 bar = {a_ref:.3f} (calibrated so C8+ = 63 wt%, Heveling 1998)')
print('Model  C4-C6 / C8-C16 / C18+ [wt%]:', [round(x * 100, 1) for x in (w0[1:3].sum(), w0[3:8].sum(), w0[8:].sum())])
print('Paper  C4-C6 / C8-C16 / C18+ [wt%]: [34, 63, 3]  (paper hard-codes this; ASF cannot match it exactly)')
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2)); ks = np.arange(1, 13)
for T, c in [(373.15, '#457b9d'), (393.15, '#2a9d8f'), (413.15, '#e76f51')]:
    al = alpha_from_T_P(T, 35, b0, dE); ax[0].plot(2 * ks, weight_fractions(al)[:12] * 100, 'o-', color=c, label=f'{T - 273.15:.0f} C, alpha={al:.2f}')
ax[0].axvspan(3.5, 6.5, color='#e9c46a', alpha=.22, label='Renewable naphtha range')
ax[0].axvspan(7.5, 16.5, color='#2a9d8f', alpha=.12, label='SAF carbon-number range')
ax[0].axvspan(17.5, 25, color='#e76f51', alpha=.10, label='Diesel-range products')
ax[0].set_xlabel('Product carbon number (C-number)'); ax[0].set_ylabel('Mass fraction of converted ethylene (wt%)')
ax[0].set_title('ASF Product Distribution at 35 bar')
ax[0].legend(title='Temperature and product range', frameon=False, fontsize=8)
Tg = np.linspace(363, 423, 40)
for P in (25, 35, 45): ax[1].plot(Tg - 273.15, [weight_fractions(alpha_from_T_P(T, P, b0, dE))[3:8].sum() * 100 for T in Tg], label=f'{P} bar')
ax[1].set_xlabel('Oligomerization temperature (°C)'); ax[1].set_ylabel('C8–C16 selectivity (wt% of converted ethylene)')
ax[1].set_title('Modelled SAF-Range Selectivity vs Temperature')
ax[1].legend(title='Oligomerization pressure', frameon=False)
fig.text(0.01, 0.005, 'Exploratory model output: temperature sensitivity depends on the assumed activation-energy difference (dE).', fontsize=9, color='#555555')
fig.set_size_inches(14, 5.5); fig.tight_layout(rect=(0, 0.04, 1, 1)); save(fig, '02_asf_product_distribution')

# ------------------------------------------------------------------ 4 ethanol route
head('4. ETHANOL FEEDSTOCK ROUTE (administered ex-mill prices ESY 2025-26)')
er = safe(A.sweep_ethanol_route, [({'route': r}, {'ethanol_route': r}) for r in cfg.S['ethanol_exmill_INR_L']], 'sweep_ethanol_route'); table(er, 'ethanol_routes', ['route', 'MJSP_USD_gal', 'MJSP_INR_L', 'SAF_MMgal_yr'])
fig, ax = plt.subplots(figsize=(9, 5)); b = ax.bar(er.route, er.MJSP_INR_L, color='#4c8298')
ax.bar_label(b, fmt='%.0f', padding=4); ax.set_ylabel('Minimum jet selling price (INR/L)')
ax.set_title('Minimum Jet Selling Price by Ethanol Feedstock Route')
ax.set_xlabel('Ethanol feedstock route'); plt.xticks(rotation=20, ha='right'); fig.tight_layout(); save(fig, '03_ethanol_route_comparison')

# ------------------------------------------------------------------ 5 hydrogen
head('5. HYDROGEN SUPPLY ROUTE COMPARISON')
hr = safe(A.sweep_h2_route, [({'route': r}, {'h2_route': r}) for r in cfg.S['h2_INR_kg']], 'sweep_h2_route'); table(hr, 'h2_routes', ['route', 'MJSP_USD_gal', 'MJSP_INR_L', 'H2_kg_per_tonne_fuel'])
fig, ax = plt.subplots(1, 2, figsize=(13, 5)); b = ax[0].bar(hr.route, hr.MJSP_INR_L, color='#4c8298'); ax[0].bar_label(b, fmt='%.0f', padding=4)
ax[0].set_ylabel('Minimum jet selling price (INR/L)'); ax[0].set_title('Economic Impact of Hydrogen Supply Route')
ax[1].bar(hr.route, [cfg.S['h2_INR_kg'][r] for r in hr.route], color='#d97757')
ax[1].set_ylabel('Hydrogen purchase price (INR/kg)'); ax[1].set_title('Hydrogen Price Assumptions by Supply Route')
for a in ax: a.set_xlabel('Hydrogen supply route'); plt.setp(a.get_xticklabels(), rotation=20, ha='right')
fig.tight_layout(); save(fig, '04_hydrogen_route_comparison')

# ------------------------------------------------------------------ 6 scale
head('6. PLANT SCALE')
sc = safe(A.sweep_scale, [({'KLPD': k}, {'ethanol_KLPD': k}) for k in (50, 100, 150, 200, 300, 400)], 'sweep_scale'); table(sc, 'scale', ['KLPD', 'MJSP_USD_gal', 'MJSP_INR_L', 'SAF_MMgal_yr', 'FCI_MM_USD'])
fig, ax = plt.subplots(1, 2, figsize=(13, 5)); ax[0].plot(sc.KLPD, sc.MJSP_INR_L, 'o-', color='#3b8f83'); ax[0].set_xlabel('Ethanol feed capacity (KLPD)'); ax[0].set_ylabel('Minimum jet selling price (INR/L)')
ax[0].set_title('Selling Price vs Plant Capacity')
ax[1].plot(sc.KLPD, sc.SAF_MMgal_yr, 'o-', color='#d97757'); ax[1].set_xlabel('Ethanol feed capacity (KLPD)'); ax[1].set_ylabel('Annual SAF production (million US gal/year)')
ax[1].set_title('SAF Production vs Plant Capacity'); fig.tight_layout(); save(fig, '05_plant_scale_effect')

# ------------------------------------------------------------------ 7 T-P
head('7. REACTOR T AND P  ->  selectivity  ->  price (new result vs the paper)')
tp = safe(A.sweep_T_P, [({'T_K': T, 'P_bar': P / 1e5}, {'olig.T': T, 'olig.P': P}) for T in (373.15, 383.15, 393.15, 403.15, 413.15) for P in (25e5, 35e5, 45e5)], 'sweep_T_P'); table(tp, 'T_P', ['T_K', 'P_bar', 'alpha', 'SAF_frac_of_fuel', 'MJSP_INR_L'])
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
for P, g in tp.groupby('P_bar'):
    for a, col in zip(ax, ['alpha', 'SAF_frac_of_fuel', 'MJSP_INR_L']): a.plot(g.T_K - 273.15, g[col], 'o-', label=f'{P:.0f} bar')
for a, yl, title in zip(ax, ['ASF chain-growth parameter, α', 'SAF fraction of total liquid fuel (mass basis)', 'Minimum jet selling price (INR/L)'], ['Chain-Growth Parameter vs Temperature', 'SAF Yield Fraction vs Temperature', 'Selling Price vs Temperature']):
    a.set_xlabel('Oligomerization temperature (°C)'); a.set_ylabel(yl); a.set_title(title); a.legend(title='Pressure', frameon=False)
fig.suptitle('Effect of Oligomerization Temperature and Pressure', fontsize=16, fontweight='bold')
fig.set_size_inches(16, 5.5); fig.tight_layout(rect=(0, 0, 1, 0.93)); save(fig, '06_temperature_pressure_sensitivity')

# ------------------------------------------------------------------ 8 deactivation
head('8. CATALYST DEACTIVATION AND REGENERATION INTERVAL')
dk = safe(A.sweep_deactivation, [({'kd': kd, 'cycle_days': c}, {'olig.kd': kd, 'olig.cycle_days': c}) for kd in (0.0005, 0.001, 0.002, 0.005, 0.01) for c in (30, 60, 120)], 'sweep_deactivation'); table(dk, 'deactivation', ['kd', 'cycle_days', 'olig_X_avg', 'MJSP_INR_L'])
pv = dk.pivot(index='kd', columns='cycle_days', values='MJSP_INR_L'); fig, ax = plt.subplots(figsize=(6.5, 4.2))
im = ax.imshow(pv.values, aspect='auto', cmap='YlOrRd', origin='lower'); ax.set_xticks(range(pv.shape[1])); ax.set_xticklabels(pv.columns); ax.set_yticks(range(pv.shape[0])); ax.set_yticklabels(pv.index)
for i in range(pv.shape[0]):
    for j in range(pv.shape[1]): ax.text(j, i, f'{pv.values[i, j]:.0f}', ha='center', va='center', fontsize=9)
ax.set_xlabel('Catalyst operating cycle before replacement (days)'); ax.set_ylabel('Deactivation rate constant, kd (day⁻¹)')
ax.set_title('Minimum Jet Selling Price Across Deactivation Scenarios')
ax.grid(False); cb = plt.colorbar(im, ax=ax); cb.set_label('Minimum jet selling price (INR/L)')
fig.tight_layout(); save(fig, '07_catalyst_deactivation_sensitivity')

# ------------------------------------------------------------------ 9 Monte Carlo
if not args.quick:
    head(f'9. MONTE CARLO: {args.n} Latin-hypercube samples (about 2-4 s each; please wait)')
    m = U.run_mc(N=args.n); tbl = m.table
    col = [c for c in tbl.columns if 'MJSP' in str(c) and 'INR' in str(c)][0]
    tbl = tbl.dropna(subset=[col]); y = tbl[col].astype(float); print(f'{len(y)} of {args.n} samples converged')
    q = y.quantile([.05, .25, .5, .75, .95]); print('MJSP percentiles [Rs/L]:'); print(q.round(1).to_string()); print('Baseline:', round(base['MJSP_INR_L'], 1))
    _p = _free_path('monte_carlo_samples', '.csv'); tbl.to_csv(_p); print('   [samples saved:', os.path.basename(_p) + ']', flush=True)
    fig, ax = plt.subplots(1, 2, figsize=(13, 5)); ax[0].hist(y, bins=24, color='#3b8f83', alpha=.88, edgecolor='white'); ax[0].axvline(base['MJSP_INR_L'], color='#333333', ls='--', lw=1.8, label='Deterministic baseline')
    for k, c in zip([.05, .5, .95], ['#457b9d', '#e9c46a', '#e76f51']): ax[0].axvline(q[k], color=c, label=f'P{int(k * 100)}')
    ax[0].set_xlabel('Minimum jet selling price (INR/L)'); ax[0].set_ylabel('Number of Monte Carlo samples')
    ax[0].set_title('Monte Carlo Distribution of Minimum Jet Selling Price'); ax[0].legend(frameon=False)
    ys = np.sort(y.values); ax[1].plot(ys, np.arange(1, len(ys) + 1) / len(ys) * 100, color='#3b8f83')
    ax[1].set_xlabel('Minimum jet selling price (INR/L)'); ax[1].set_ylabel('Cumulative probability (%)')
    ax[1].set_title('Cumulative Distribution of Minimum Jet Selling Price'); fig.tight_layout(); save(fig, '08_monte_carlo_mjsp_distribution')
    mc = [c for c in tbl.columns if 'MJSP' in str(c) or 'SAF yield' in str(c)]
    r = tbl.drop(columns=mc).astype(float).corrwith(y, method='spearman'); r.index = [i[1] if isinstance(i, tuple) else str(i) for i in r.index]
    r = r.dropna(); r = r.reindex(r.abs().sort_values(ascending=False).index).head(14)
    print('\nSpearman rank correlation with MJSP (top 14):'); print(r.round(3).to_string())
    fig, ax = plt.subplots(figsize=(8, 5.5)); rr = r[::-1]; ax.barh(rr.index, rr.values, color=['#e76f51' if v > 0 else '#2a9d8f' for v in rr.values]); ax.axvline(0, color='k', lw=.8)
    ax.set_xlabel('Spearman rank correlation with minimum jet selling price')
    ax.set_title('Sensitivity of Minimum Jet Selling Price to Model Inputs')
    fig.tight_layout(); save(fig, '09_mjsp_sensitivity_ranking')
    ecol = [c for c in tbl.columns if 'Ethanol ex-mill' in str(c)][0]
    fig, ax = plt.subplots(figsize=(7, 5)); ax.scatter(tbl[ecol].astype(float), y, s=22, alpha=.65, color='#3b8f83', edgecolors='none')
    ax.set_xlabel('Ethanol ex-mill purchase price (INR/L)'); ax.set_ylabel('Minimum jet selling price (INR/L)')
    ax.set_title('Effect of Ethanol Purchase Price on Minimum Jet Selling Price')
    fig.tight_layout(); save(fig, '10_ethanol_price_vs_mjsp')

head(f'DONE in {(time.time() - T0) / 60:.1f} min. Tables (csv) and charts (png) are in: {OUT}')
if not args.no_show:
    try:
        plt.show()
    except KeyboardInterrupt:
        print('\nPlot display interrupted. PNG files were already saved in results/.')
        pass