"""
settings.py  --  ALL inputs of the India ATJ model live here (nothing is hard-coded elsewhere).

Convention: money inputs are in INR where Indian data exist; the BioSTEAM model itself works in USD,
so `fx` converts. Every number carries a source tag:
  [VERIFIED-26]  = checked by web search (19-28 Oct 2026); source given in the comment
  [REPO]         = carried over unchanged from Wadgama & Shi 2026 / github.com/H-Wadgama/belt (US basis)
  [DERIVED]      = computed from a [VERIFIED-26] number; the arithmetic is in the comment
  [UNRESOLVED]   = no reliable public source found; the comment says exactly what to look up. Do not quote results
                   that depend strongly on these as "India-verified".
"""
import copy

S = dict(
    # ------------------------------------------------------------------ macro / finance
    fx=94.1402,                   # INR per USD. [VERIFIED-26] FBIL/RBI reference rate, 6 Nov 2026 (RBI Current Rates page; latest published business-day observation before 9 Nov). Refresh for the actual run date.
    CEPCI=800.8,                  # [REPO] 2023 Chemical Engineering Plant Cost Index used by the paper (chemengonline.com/pci-home)
    location_factor=0.90,         # [UNRESOLVED] India vs US Gulf Coast installed-cost ratio. Only paywalled sources exist: S&P Global PEP Review RW2024-10 (India is among 34 locations, USGC=1.0) and Intratec India IL-factor. Get the India value from one of them (or an EPC quote)
    IRR=0.10,                     # [REPO] after-tax return used by the paper to define MJSP (NPV=0)
    income_tax=0.2517,            # [VERIFIED-26] 22% base x 1.10 surcharge x 1.04 cess = 25.168% (s.115BAA; s.200 of Income-tax Act 2025 from Tax Year 2026-27): setindiabiz.com/blog/corporate-tax-private-limited-company ; taxaj.com. NOTE: 15% s.115BAB (17.16% eff.) is closed to new plants
    finance_fraction=0.60,        # [REPO] 60% debt
    finance_interest=0.10,        # [DERIVED] SBI 3-yr MCLR 8.95%, 1-yr 8.85%, effective 15 Oct 2026 (bankingfinance.in/?p=18366; RBI repo 5.50% on 7 Oct 2026) + ASSUMED 1.0-1.5% project-credit spread (spread is NOT sourced; get a bank sanction letter/term sheet)
    finance_years=10,             # [REPO]
    duration=(2027, 2057),        # 30-yr life [REPO]; start year is my assumption
    operating_days=330,           # [REPO] (= 90.4% on-stream)
    construction_schedule=(0.08, 0.60, 0.32),   # [REPO]
    WC_over_FCI=0.05,             # [REPO]
    wdv_rate=0.15,                # [VERIFIED-26] general plant & machinery, WDV 15% (Income-tax Act 2025 s.34, Appendix I): taxguru.in/?p=1036553 ; patronaccounting.com/blog/depreciation-rules-2026-rates-block-assets. Replaces US MACRS-7
    # ------------------------------------------------------------------ plant size
    ethanol_KLPD=200.0,           # design basis, kilolitres/day of TOTAL ethanol+water feed stream. Typical large Indian distillery range 100-300 KLPD (ISMA/MoPNG). Your scale sweep varies this.
    # PATHWAY NOTE (review, Oct 2026): the paper's baseline is 2G/LIGNOCELLULOSIC ethanol (corn stover, biochemical
    # conversion), priced as an NREL-modelled minimum selling price, NOT a market/administered price. The ethanol
    # routes below (B-heavy, maize, etc.) are CONVENTIONAL (1G, molasses/grain) Indian routes -- a different
    # feedstock class with different capital/LCA implications. Run validate_paper.py (US inputs) for paper
    # comparison; use '2G_cellulosic' as the route when the thesis claim is specifically about the paper's pathway.
    ethanol_purity_wt=0.995,      # [REPO] feed_parameters['purity'] -- mass fraction of the TOTAL ethanol_KLPD stream (system.py splits it as Ethanol=eth*purity, Water=eth*(1-purity); FIXED Oct 2026, previously double-counted ~0.5% high)
    ethanol_density=789.0,        # kg/m3 pure ethanol, [REPO] (Humbird 2011); total-feed density is estimated by additive specific volumes below
    # ------------------------------------------------------------------ ethanol feedstock price
    # Administered ex-mill prices, Rs/litre, ESY 2025-26 (1 Nov 2025 - 31 Oct 2026). [VERIFIED-26]
    #  sources: dataful.in/datasets/21605 (MoPNG series); bioenergytimes.com (Jul 2026, MoS Petroleum written reply);
    #           iamrenew.com / bioenergytimes.com (FCI rice Rs 60.32).
    ethanol_route='2G_cellulosic',  # thesis baseline: lignocellulosic (2G) ethanol; 1G routes remain comparison cases
    ethanol_exmill_INR_L={'C_heavy': 57.97, 'B_heavy': 60.73, 'cane_juice': 65.61,
                          'FCI_rice': 60.32, 'damaged_grain': 64.00, 'maize': 71.86,
                          '2G_cellulosic': 120.0},  # 2G: provisional production-cost estimate from 2026 industry commentary (iamrenew.com, 2026: ~Rs 120/L vs ~Rs 70/L for 1G). NOT an administered price or verified project quote. Retain Rs 160/L as an explicit high-cost case in ethanol_price_basis_audit.py; older 2024 executive quote (Autocar Professional) reported ~Rs 160/L. OMC 2G procurement is case-specific.
    ethanol_transport_INR_L_conventional=1.2,  # DERIVED conventional-route proxy: delivered IOCL price less ex-mill + assumed creditable GST; not a 2G logistics estimate.
    #   2G_cellulosic is a provisional industry production-cost estimate, not an administered ex-mill price. Its separate
    #   delivery/storage cost is unknown, so the generic conventional-route adder is NOT applied to 2G.
    #   This avoids adding an unsupported Rs 1.2/L to the 2G cost, but does NOT mean 2G delivery is free:
    #   the current 2G feed-price boundary is production-cost proxy with logistics unresolved/excluded.
    # ------------------------------------------------------------------ hydrogen
    h2_route='green_offsite',
    # H2 price, INR/kg.
    #  green_offsite 358 = [DERIVED] Emkay Global (Jul 2026): ~USD 3.8/kg excl. GST from recent refinery/fertiliser bids x 94.1402 (6 Nov 2026 RBI/FBIL rate)
    #     (bioenergytimes.com, 25 Jul 2026). Anchors: Numaligarh refinery tender Rs 279/kg (solarquarter.com/2026/03/20; hydrogenfuelnews.com),
    #     IOCL Panipat/L&T tender Rs 397/kg incl. 18% GST (energyintel.com; jmkresearch.com). These are PRICES AT A REFINERY GATE: delivery
    #     to a distillery elsewhere is extra and is [UNRESOLVED] (the model separately costs the 7-day storage tanks).
    #  grey_smr_refinery 198 = [DERIVED] ~USD 2.1/kg average grey H2 (jmkresearch.com, IOCL tender article) x 94.1402 (6 Nov 2026 RBI/FBIL rate)
    #  green_onsite 363 and blue_smr_ccs 260 = [UNRESOLVED] no India source found; green_onsite needs an electrolyser capex + solar/wind PPA
    #     calculation (solar bids reach ~Rs 2/kWh per hydrogenfuelnews.com), blue needs a CCS cost; both are copies/placeholders, do not report them.
    h2_INR_kg={'green_offsite': 358.0, 'green_onsite': 358.0, 'grey_smr_refinery': 198.0, 'blue_smr_ccs': 260.0},
    h2_comparison_routes=('green_offsite', 'grey_smr_refinery'),  # exclude onsite/blue until full production and delivery costs are modelled
    h2_storage_days=7,            # [REPO]
    h2_ratio=3.0,                 # mol H2 : mol olefin at hydrogenator inlet [REPO]
    h2_recovery=0.85,             # PSA recovery [REPO]
    # ------------------------------------------------------------------ co-products & utilities
    # rn (naphtha) 0.80 USD/kg = [VERIFIED-26] India naphtha ~USD 796/t in Jul 2026 (procurementresource.com naphtha-price-trends); the 2026 range
    #     is wide: 0.62 (Q1 avg, expertmarketresearch.com) - 0.98 (Apr FOB) - 1.17 (May) because of the Hormuz disruption.
    # rd (diesel) 0.72 USD/kg = [DERIVED] HSD price to dealers before excise & VAT ~Rs 56.5/L (HPCL price build-up, 1 May 2024:
    #     hpcladmin.hindustanpetroleum.com ... 290e2fef...pdf; Rs 58.2 on 1 Dec 2022) / 0.83 kg/L (assumed density) / 95.5.
    #     This REPLACES the old US-basis 1.888 USD/kg, which was ~2.6x too high for India and inflated the co-product credit.
    #     Latest pre-tax HSD price (Oct 2026) NOT retrieved: retail Delhi is Rs 89.62/L (frozen since 6 Apr 2026, outlookbusiness.com).
    rn_USD_kg=0.80, rd_USD_kg=0.72,
    elec_INR_kWh=6.5,             # [DERIVED] HT industrial tariff Rs 5.5-7.5/kWh (qbitsenergy.com/glossary/tariff, Jul 2026); industrial range Rs 3.35-10.0 across states (Govt. reply, Rajya Sabha PQ 256, 2022); CEA tariff compendium Mar 2026 (cea.nic.in). Use YOUR state's SERC tariff order
    ng_INR_kg=50.0,               # [DERIVED] ~USD 10/MMBtu (GCV) x 0.0526 MMBtu/kg methane x 95.5 = Rs 50/kg. Anchors: APM gas ceiling USD 7.00 (PPAC, from 1 Apr 2026; fipi.org.in Jun-2026 report) = Rs 35/kg; Japan LNG import ~USD 15.8 (May 2026) = Rs 79/kg. Base within range is a judgement
    wastewater_USD_kg=1.85e-3,    # [REPO] Humbird-style WWT cost per kg wastewater
    labor_USD_yr=1.2e6,           # [UNRESOLVED] no usable public figure found. Method: staff count for a 200 KLPD plant x average annual emolument per person engaged for chemical manufacturing from MoSPI's Annual Survey of Industries summary tables (microdata.gov.in / mospi.gov.in), then add benefits
    # ------------------------------------------------------------------ catalysts ($/kg, global/imported)  [REPO]
    cat_price_USD_kg={'dehyd': 36.81, 'olig': 158.4, 'hydgn': 59.12},   # Zhang&Yu 2013 / Tao 2017 / Davis 2015 via repo's etj_settings.py
    cat_life_yr={'dehyd': 2.0, 'olig': 1.0, 'hydgn': 3.0},              # [REPO]
    # ------------------------------------------------------------------ reactors
    dehyd=dict(T=754.0, P=10.63e5, X=0.995, whsv=0.3),   # [REPO]; Syndol alumina catalyst, Zhang & Yu 2013 (Ind. Eng. Chem. Res. 52, 9505)
    olig=dict(T=393.15, P=35e5, X0=0.993, whsv=1.5,       # [REPO]; Heveling et al. 1998 Appl. Catal. A 173, 1-9
              mode='asf',                                   # 'asf' (default, this thesis's chain-growth model) or 'fixed_literature'
              #   (the paper's own 20/15/62/3 split, for a validation/comparison scenario -- see selectivity_scenarios.py).
              #   VERIFIED (Oct 2026, responding to an external review): no chain-growth mixture, single- or multi-
              #   population, can reach 63% C8-C16 -- the max for any such model is 45.57% (asf_model.max_c8_c16_share).
              #   This is a genuine structural gap between the paper's assumed catalyst behaviour and a chain-growth
              #   mechanism, not a fitting problem; report it as such rather than forcing a fit to 34/63/3.
              c8plus_ref=0.63,                              # Heveling: 63 wt% C8+ (k>=4) on oligomer-product basis at 393 K / 35 bar; calibrate_beta0(0.63) gives alpha≈0.6423
              dE=15e3,                                      # [UNRESOLVED] J/mol. MODEL STRUCTURE (review, Oct 2026): alpha(T,P) has TWO parameters, not one --
              #   beta0 is the INTERCEPT: calibrated in units.py so alpha AT (T_ref=393.15K, P_ref=35bar) reproduces
              #   the single Heveling 1998 data point (63 wt% C8+ of k>=2 oligomer products). This is the one observation available and it
              #   correctly identifies only beta0, as the review notes -- it does NOT and cannot also fix dE.
              #   dE is the SLOPE (how fast alpha changes with T): sign convention is beta = beta0*exp(-dE/R*(1/T-1/T_ref))*(P_ref/P),
              #   i.e. dE = E_term - E_prop > 0 means hotter -> more termination -> shorter chains (verified in asf_model.py).
              #   dE has NO data point behind it and is a genuine placeholder: fit it from a second (T, selectivity)
              #   pair if Heveling 1998 reports one, or from Eagan 2019 Nat Rev Chem 3:223; otherwise treat as a
              #   wide uncertain parameter (as uncertainty.py already does) and do not read T/P sweep results as
              #   more than illustrative of model STRUCTURE until dE is fitted.
              kd=0.002, cycle_days=60.0),                   # [UNRESOLVED] NOT the same as cat_life_yr['olig']=1.0 below. cat_life_yr sets catalyst REPLACEMENT
              #   cost (kg makeup/hr = bed_mass/life/8760, in units.py's CatalystReactor._run). kd/cycle_days instead
              #   sets a CONVERSION-averaging correction for decay BETWEEN replacements (cycle_average_activity in
              #   asf_model.py). These describe different things (replacement economics vs. in-cycle performance
              #   decay) and are currently independent, undocumented assumptions with no shared data source -- do
              #   not assume one implies or constrains the other. Needs Ni/SiO2-Al2O3 time-on-stream data.
    hydgn=dict(T=623.15, P=35e5, X=1.0, whsv=3.0),        # [REPO]; Tao et al. 2017 Green Chem 19:1082
    # ------------------------------------------------------------------ policy / benchmark (used only in analysis.py)
    fossil_atf_INR_L=138.50,      # [VERIFIED-26] Delhi ATF for domestic airlines, reported by OMCs at Rs 138.50/L effective 1 Nov 2026 (UNI, 1 Nov 2026; recheck the direct IOCL notification). This is an indicative price-parity benchmark, not automatically comparable with plant-gate SAF MJSP.
)

def get():
    """Return a fresh deep copy so scenario runs never contaminate each other."""
    return copy.deepcopy(S)

# ---- unit helpers --------------------------------------------------------
def ethanol_feed_density(s):
    """Approximate total feed density from ethanol/water mass fractions.

    Uses additive specific volumes (ideal-volume approximation); replace with
    a validated mixture density if the feed is materially more dilute.
    """
    w = s['ethanol_purity_wt']
    rho_ethanol = s['ethanol_density']
    rho_water = 998.2  # kg/m3, near ambient liquid water
    return 1.0 / (w / rho_ethanol + (1.0 - w) / rho_water)


def ethanol_kg_hr(s):
    # KLPD is total ethanol-water feed volume, not pure-ethanol-equivalent volume.
    return s['ethanol_KLPD'] * ethanol_feed_density(s) / 24.0

def ethanol_price_USD_kg(s):
    route = s['ethanol_route']
    transport = 0.0 if route == '2G_cellulosic' else s['ethanol_transport_INR_L_conventional']
    inr_l = s['ethanol_exmill_INR_L'][route] + transport
    # The priced stream is the TOTAL ethanol-water feed. Convert the ethanol-only Rs/L
    # quote to USD/kg of total feed by multiplying by the ethanol mass fraction.
    return (inr_l / s['fx'] / (s['ethanol_density'] / 1000.0)) * s['ethanol_purity_wt']

def h2_price_USD_kg(s):
    return s['h2_INR_kg'][s['h2_route']] / s['fx']

def elec_USD_kWh(s): return s['elec_INR_kWh'] / s['fx']
def ng_USD_kg(s):    return s['ng_INR_kg'] / s['fx']