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
warnings.filterwarnings('ignore')
ap = argparse.ArgumentParser()
ap.add_argument('--n', type=int, default=100); ap.add_argument('--no-show', action='store_true'); ap.add_argument('--quick', action='store_true')
args = ap.parse_args()

import matplotlib
if args.no_show: matplotlib.use('Agg')
import numpy as np, pandas as pd, matplotlib.pyplot as plt
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)
plt.rcParams.update({'figure.dpi': 100, 'axes.grid': True, 'grid.alpha': .3, 'axes.spines.top': False, 'axes.spines.right': False})
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import settings as cfg, analysis as A
from asf_model import weight_fractions, alpha_from_T_P, calibrate_beta0

def load_uncertainty():
    """uncertainty.py uses package-style imports (from .system import ...), which fail when files sit in one flat
    folder. Instead of editing your file, load it here with those 3 import lines pointed at the flat modules."""
    import types
    src = open(os.path.join(HERE, 'uncertainty.py'), encoding='utf-8').read()
    src = (src.replace('from .system import', 'from system import').replace('from . import settings as cfg', 'import settings as cfg')
              .replace('from .analysis import', 'from analysis import'))
    mod = types.ModuleType('uncertainty'); mod.__file__ = os.path.join(HERE, 'uncertainty.py')
    exec(compile(src, mod.__file__, 'exec'), mod.__dict__); return mod
U = load_uncertainty()

def safe(sweep_fn, fallback_rows, label):
    """Call YOUR sweep function. If one operating point crashes the BioSTEAM column solver (e.g. 373 K / 45 bar in
    sweep_T_P), redo that sweep point-by-point with A.run + A.results and skip only the bad points."""
    try:
        return sweep_fn()
    except Exception as e:
        print(f'   note: {label} hit a solver failure ({str(e)[:70]}...); re-running point by point, bad points -> NaN', flush=True)
        rows = []
        for extra, kw in fallback_rows:
            try: rows.append(dict(extra, **A.results(*A.run(**kw))))
            except Exception: rows.append(dict(extra, **{k: np.nan for k in A.results(*A.run()).keys()}))
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
    base = name
    for i in range(10):
        p = _free_path(base if i == 0 else f'{name}_{i}', '.png')
        try:
            fig.savefig(p, bbox_inches='tight')
            print(f'   [chart saved: results/{os.path.basename(p)}]', flush=True)
            return
        except OSError as e:
            print(f'   !! could not save {os.path.basename(p)} ({e}); retrying with a fresh filename', flush=True)
            continue
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
ax[0].set_xlabel('Installed cost [MM USD]'); ax[0].set_title('Capital by area (total %.1f MM USD)' % sum(cap.values()))
vals = [v / saf_gal for _, v in items]; cum = np.cumsum([0] + vals[:-1])
ax[1].bar([n for n, _ in items], vals, bottom=cum, color=['#e76f51' if v > 0 else '#2a9d8f' for v in vals]); ax[1].axhline(sum(vals), color='k', ls='--', lw=1)
ax[1].set_ylim(0, max(np.maximum(cum, cum + np.array(vals)).max(), sum(vals)) * 1.08)
ax[1].set_ylabel('USD per gal SAF'); ax[1].set_title('MJSP build-up = %.2f USD/gal (Rs %.0f/L)' % (sum(vals), base['MJSP_INR_L']))
plt.setp(ax[1].get_xticklabels(), rotation=40, ha='right'); plt.tight_layout(); save(fig, '1_cost_breakdown')

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
ax[0].axvspan(3, 7, color='#e9c46a', alpha=.25); ax[0].axvspan(7, 17, color='#2a9d8f', alpha=.12); ax[0].axvspan(17, 25, color='#e76f51', alpha=.12)
ax[0].set_xlabel('Carbon number (shaded: RN | SAF C8-C16 | RD)'); ax[0].set_ylabel('wt % of converted ethylene'); ax[0].set_title('Product distribution at 35 bar'); ax[0].legend()
Tg = np.linspace(363, 423, 40)
for P in (25, 35, 45): ax[1].plot(Tg - 273.15, [weight_fractions(alpha_from_T_P(T, P, b0, dE))[3:8].sum() * 100 for T in Tg], label=f'{P} bar')
ax[1].set_xlabel('Temperature [C]'); ax[1].set_ylabel('SAF-range wt%'); ax[1].set_title('SAF selectivity as OUTPUT of T and P'); ax[1].legend()
plt.tight_layout(); save(fig, '2_asf_distribution')

# ------------------------------------------------------------------ 4 ethanol route
head('4. ETHANOL FEEDSTOCK ROUTE (administered ex-mill prices ESY 2025-26)')
er = safe(A.sweep_ethanol_route, [({'route': r}, {'ethanol_route': r}) for r in cfg.S['ethanol_exmill_INR_L']], 'sweep_ethanol_route'); table(er, 'ethanol_routes', ['route', 'MJSP_USD_gal', 'MJSP_INR_L', 'SAF_MMgal_yr'])
fig, ax = plt.subplots(figsize=(9, 4)); b = ax.bar(er.route, er.MJSP_INR_L, color=['#e9c46a' if r == '2G_cellulosic' else '#2a9d8f' for r in er.route])
ax.bar_label(b, fmt='%.0f'); ax.set_ylabel('MJSP [Rs/L]'); ax.set_title('MJSP by ethanol route (yellow = placeholder price)'); plt.xticks(rotation=25); plt.tight_layout(); save(fig, '3_ethanol_routes')

# ------------------------------------------------------------------ 5 hydrogen
head('5. HYDROGEN SOURCE (prices are PLACEHOLDERS - replace in settings.py)')
hr = safe(A.sweep_h2_route, [({'route': r}, {'h2_route': r}) for r in cfg.S['h2_INR_kg']], 'sweep_h2_route'); table(hr, 'h2_routes', ['route', 'MJSP_USD_gal', 'MJSP_INR_L', 'H2_kg_per_tonne_fuel'])
fig, ax = plt.subplots(1, 2, figsize=(12, 4)); b = ax[0].bar(hr.route, hr.MJSP_INR_L, color='#457b9d'); ax[0].bar_label(b, fmt='%.0f'); ax[0].set_ylabel('MJSP [Rs/L]'); ax[0].set_title('MJSP by H2 route')
ax[1].bar(hr.route, [cfg.S['h2_INR_kg'][r] for r in hr.route], color='#e76f51'); ax[1].set_ylabel('Assumed H2 price [Rs/kg]')
for a in ax: plt.setp(a.get_xticklabels(), rotation=25, ha='right')
plt.tight_layout(); save(fig, '4_h2_routes')

# ------------------------------------------------------------------ 6 scale
head('6. PLANT SCALE')
sc = safe(A.sweep_scale, [({'KLPD': k}, {'ethanol_KLPD': k}) for k in (50, 100, 150, 200, 300, 400)], 'sweep_scale'); table(sc, 'scale', ['KLPD', 'MJSP_USD_gal', 'MJSP_INR_L', 'SAF_MMgal_yr', 'FCI_MM_USD'])
fig, ax = plt.subplots(1, 2, figsize=(12, 4)); ax[0].plot(sc.KLPD, sc.MJSP_INR_L, 'o-', color='#2a9d8f'); ax[0].set_xlabel('Ethanol feed [KLPD]'); ax[0].set_ylabel('MJSP [Rs/L]')
ax[1].plot(sc.KLPD, sc.SAF_MMgal_yr, 'o-', color='#e76f51'); ax[1].set_xlabel('Ethanol feed [KLPD]'); ax[1].set_ylabel('SAF [MM gal/yr]'); plt.tight_layout(); save(fig, '5_scale')

# ------------------------------------------------------------------ 7 T-P
head('7. REACTOR T AND P  ->  selectivity  ->  price (new result vs the paper)')
tp = safe(A.sweep_T_P, [({'T_K': T, 'P_bar': P / 1e5}, {'olig.T': T, 'olig.P': P}) for T in (373.15, 383.15, 393.15, 403.15, 413.15) for P in (25e5, 35e5, 45e5)], 'sweep_T_P'); table(tp, 'T_P', ['T_K', 'P_bar', 'alpha', 'SAF_frac_of_fuel', 'MJSP_INR_L'])
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
for P, g in tp.groupby('P_bar'):
    for a, col in zip(ax, ['alpha', 'SAF_frac_of_fuel', 'MJSP_INR_L']): a.plot(g.T_K - 273.15, g[col], 'o-', label=f'{P:.0f} bar')
for a, yl in zip(ax, ['alpha', 'SAF share of fuel', 'MJSP [Rs/L]']): a.set_xlabel('Temperature [C]'); a.set_ylabel(yl); a.legend()
plt.tight_layout(); save(fig, '6_temperature_pressure')

# ------------------------------------------------------------------ 8 deactivation
head('8. CATALYST DEACTIVATION (kd and cycle length are PLACEHOLDERS)')
dk = safe(A.sweep_deactivation, [({'kd': kd, 'cycle_days': c}, {'olig.kd': kd, 'olig.cycle_days': c}) for kd in (0.0005, 0.001, 0.002, 0.005, 0.01) for c in (30, 60, 120)], 'sweep_deactivation'); table(dk, 'deactivation', ['kd', 'cycle_days', 'olig_X_avg', 'MJSP_INR_L'])
pv = dk.pivot(index='kd', columns='cycle_days', values='MJSP_INR_L'); fig, ax = plt.subplots(figsize=(6.5, 4.2))
im = ax.imshow(pv.values, aspect='auto', cmap='YlOrRd', origin='lower'); ax.set_xticks(range(pv.shape[1])); ax.set_xticklabels(pv.columns); ax.set_yticks(range(pv.shape[0])); ax.set_yticklabels(pv.index)
for i in range(pv.shape[0]):
    for j in range(pv.shape[1]): ax.text(j, i, f'{pv.values[i, j]:.0f}', ha='center', va='center', fontsize=9)
ax.set_xlabel('Run length [days]'); ax.set_ylabel('kd [1/day]'); ax.set_title('MJSP [Rs/L]'); ax.grid(False); plt.colorbar(im); plt.tight_layout(); save(fig, '7_deactivation')

# ------------------------------------------------------------------ 9 Monte Carlo
if not args.quick:
    head(f'9. MONTE CARLO: {args.n} Latin-hypercube samples (about 2-4 s each; please wait)')
    m = U.run_mc(N=args.n); tbl = m.table
    col = [c for c in tbl.columns if 'MJSP' in str(c) and 'INR' in str(c)][0]
    tbl = tbl.dropna(subset=[col]); y = tbl[col].astype(float); print(f'{len(y)} of {args.n} samples converged')
    q = y.quantile([.05, .25, .5, .75, .95]); print('MJSP percentiles [Rs/L]:'); print(q.round(1).to_string()); print('Baseline:', round(base['MJSP_INR_L'], 1))
    _p = _free_path('monte_carlo_samples', '.csv'); tbl.to_csv(_p); print('   [samples saved:', os.path.basename(_p) + ']', flush=True)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2)); ax[0].hist(y, bins=20, color='#2a9d8f', alpha=.85); ax[0].axvline(base['MJSP_INR_L'], color='k', ls='--', label='baseline')
    for k, c in zip([.05, .5, .95], ['#457b9d', '#e9c46a', '#e76f51']): ax[0].axvline(q[k], color=c, label=f'P{int(k * 100)}')
    ax[0].set_xlabel('MJSP [Rs/L]'); ax[0].set_ylabel('count'); ax[0].legend(); ys = np.sort(y.values); ax[1].plot(ys, np.arange(1, len(ys) + 1) / len(ys) * 100, color='#2a9d8f')
    ax[1].set_xlabel('MJSP [Rs/L]'); ax[1].set_ylabel('P(MJSP <= x) [%]'); plt.tight_layout(); save(fig, '8_mc_distribution')
    mc = [c for c in tbl.columns if 'MJSP' in str(c) or 'SAF yield' in str(c)]
    r = tbl.drop(columns=mc).astype(float).corrwith(y, method='spearman'); r.index = [i[1] if isinstance(i, tuple) else str(i) for i in r.index]
    r = r.dropna(); r = r.reindex(r.abs().sort_values(ascending=False).index).head(14)
    print('\nSpearman rank correlation with MJSP (top 14):'); print(r.round(3).to_string())
    fig, ax = plt.subplots(figsize=(8, 5.5)); rr = r[::-1]; ax.barh(rr.index, rr.values, color=['#e76f51' if v > 0 else '#2a9d8f' for v in rr.values]); ax.axvline(0, color='k', lw=.8)
    ax.set_xlabel('Spearman rho vs MJSP'); ax.set_title('What drives the uncertainty'); plt.tight_layout(); save(fig, '9_sensitivity')
    ecol = [c for c in tbl.columns if 'Ethanol ex-mill' in str(c)][0]
    fig, ax = plt.subplots(figsize=(6, 4)); ax.scatter(tbl[ecol].astype(float), y, s=14, color='#2a9d8f'); ax.set_xlabel('Ethanol ex-mill price [Rs/L]'); ax.set_ylabel('MJSP [Rs/L]'); plt.tight_layout(); save(fig, '10_ethanol_vs_mjsp')

head(f'DONE in {(time.time() - T0) / 60:.1f} min. Tables (csv) and charts (png) are in: {OUT}')
if not args.no_show:
    try:
        plt.show()
    except KeyboardInterrupt:
        print('\nPlot display interrupted. PNG files were already saved in results/.')
        pass