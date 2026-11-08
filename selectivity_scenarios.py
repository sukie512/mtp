"""
selectivity_scenarios.py -- REAL (flowsheet-simulated, not proportionally-scaled) comparison of the paper's
fixed literature split (20/15/62/3 wt%, Heveling 1998 as used in the paper's own TEA) vs this thesis's ASF
chain-growth model, under the INDIA cost basis. Written in response to an external review (Oct 2026) that
recommended keeping both as explicit scenarios rather than treating 63% SAF as ground truth -- see settings.py
comments and asf_model.max_c8_c16_share for why no chain-growth model can reach the fixed split's 63% C8-C16.
Run: python selectivity_scenarios.py   (about 20 s)
"""
import os, sys, warnings
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd, matplotlib.pyplot as plt
import settings as cfg, analysis as A, system as SYS

def run_mode(mode):
    """Like analysis.run(), but re-cuts the fractionation columns for 'fixed_literature' (same fix as
    validate_paper.py): its split only populates C4, C6, C10, C18 -- zero flow on the column's normal heavy
    key (Octane, C8) makes BioSTEAM's McCabe-Thiele design divide by zero, so the cut points move to the
    carbon numbers that mode actually produces. This is a real structural consequence of a 4-point split not
    fitting the same column topology as a smooth ASF spread across every carbon number -- not a bug to hide."""
    s = cfg.get(); s['olig']['mode'] = mode
    sys_, tea, F = SYS.build(s)
    if mode == 'fixed_literature':
        F.unit.D301.LHK = ('Hexane', 'Decane'); F.unit.D302.LHK = ('Decane', 'Octadecane')
    sys_.simulate()
    return A.results(sys_, tea, F, s)

rows = []
for mode, label in [('fixed_literature', 'Fixed split\n(paper, 34/63/3-style)'), ('asf', 'ASF chain-growth\n(this thesis, alpha=0.688)')]:
    rows.append(dict(mode=label, **run_mode(mode)))
df = pd.DataFrame(rows).set_index('mode')
pd.set_option('display.width', 160)
print('\n' + '=' * 78 + '\nSELECTIVITY SCENARIO COMPARISON (India basis, real BioSTEAM simulation)\n' + '=' * 78)
d2 = df.copy(); d2.index = [i.replace(chr(10), ' ') for i in d2.index]
print(d2[['MJSP_USD_gal', 'MJSP_INR_L', 'SAF_frac_of_fuel', 'SAF_MMgal_yr', 'RN_MMgal_yr', 'RD_MMgal_yr']].round(3).to_string())
d_mjsp = df['MJSP_INR_L'].iloc[1] - df['MJSP_INR_L'].iloc[0]
pct = d_mjsp / df['MJSP_INR_L'].iloc[0] * 100
print(f"\n>>> Switching from the paper's assumed split to the ASF model changes MJSP by {d_mjsp:+.0f} Rs/L ({pct:+.1f}%)")
print(f">>> This is a REAL simulated number (full TEA re-solve, co-product credits included), not a proportional estimate.")
os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
df.to_csv(os.path.join(HERE, 'results', 'selectivity_scenarios.csv'))
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
ax[0].bar(df.index, df['MJSP_INR_L'], color=['#457b9d', '#e76f51'])
for i, v in enumerate(df['MJSP_INR_L']): ax[0].text(i, v + 2, f'{v:.0f}', ha='center')
ax[0].set_ylabel('MJSP [Rs/L]'); ax[0].set_title('Real simulated MJSP: fixed split vs ASF model')
width = 0.35; x = range(3); labels = ['RN', 'SAF', 'RD']
for i, m in enumerate(df.index):
    vals = [df.loc[m, 'RN_MMgal_yr'], df.loc[m, 'SAF_MMgal_yr'], df.loc[m, 'RD_MMgal_yr']]
    ax[1].bar([xi + (i - 0.5) * width for xi in x], vals, width, label=m.split(chr(10))[0], color=['#457b9d', '#e76f51'][i])
ax[1].set_xticks(x); ax[1].set_xticklabels(labels); ax[1].set_ylabel('MM gal/yr'); ax[1].set_title('Product slate shifts'); ax[1].legend(fontsize=8)
plt.tight_layout(); fig.savefig(os.path.join(HERE, 'results', 'selectivity_scenarios.png'), bbox_inches='tight', dpi=150)
print('[saved results/selectivity_scenarios.csv and .png]')
