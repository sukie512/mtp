# India Alcohol-to-Jet (ATJ) techno-economic model

A BioSTEAM-based process and techno-economic model for converting ethanol to sustainable aviation fuel (SAF), with an India-focused economic case, ASF-based oligomerization selectivity, deterministic scenario analysis, and Latin-hypercube Monte Carlo uncertainty analysis.

> **Model status:** this repository is a research model, not a validated engineering design or investment estimate. Some inputs and equipment-cost correlations remain assumptions or unresolved items. Numerical outputs must be interpreted with the limitations in [Model review and plot guide](MODEL_REVIEW_AND_PLOT_GUIDE.md).

## Current thesis baseline

The default settings are configured for:

- **Ethanol route:** 2G_cellulosic (lignocellulosic / second-generation ethanol)
- **Plant capacity:** 200 KLPD on the model's stated total ethanol-plus-water feed-volume basis (mass flow uses an additive-specific-volume density approximation)
- **Hydrogen route:** green_offsite
- **Finance:** India-specific settings in settings.py
- **Oligomerization:** temperature- and pressure-dependent ASF chain-growth model

The 2G ethanol input of INR 160/L is a quoted production-cost proxy, not an administered ex-mill price. The conventional-route transport proxy is not applied to 2G; 2G delivery/logistics remains excluded and unresolved. The conventional-route transport proxy is not applied to 2G; the 2G delivery/logistics cost remains excluded and unresolved. The green off-site hydrogen price is a refinery-gate anchor; delivery to the plant is not fully costed. The route-comparison sweep therefore includes only green off-site and grey refinery hydrogen. Green on-site and blue hydrogen are excluded until electrolyser/renewable-system and CCS costs are represented. These caveats are printed by the runner and must accompany any reported baseline MJSP.

Conventional routes (B-heavy molasses, C-heavy molasses, cane juice, maize, rice and damaged grain) remain in the ethanol-route comparison sweep. They are not the thesis's 2G baseline.

## Repository map

| File | Purpose |
|---|---|
| settings.py | Central process, price, utility, catalyst, finance and operating assumptions |
| atj_chemicals.py | Chemical species and carbon-number product cuts |
| asf_model.py | ASF chain-growth distribution, oligomer-product basis, alpha(T,P), calibration and deactivation |
| units.py | Custom dehydration, oligomerization, hydrogenation and storage unit operations |
| system.py | BioSTEAM flowsheet construction and stream/utility price application |
| tea.py | India-specific discounted-cash-flow TEA |
| analysis.py | Baseline simulation, headline metrics and deterministic sweeps |
| uncertainty.py | Latin-hypercube sampling, coupled process inputs, economic inputs and MJSP metrics |
| run_all.py | End-to-end runner, terminal tables, CSV exports, PNG/PDF figures and run manifest |
| run_mc_replicates.py | Independent Latin-hypercube replicates for Monte Carlo stability checks |
| selectivity_scenarios.py | ASF versus fixed-literature selectivity comparison |
| validate_paper.py | Reference-paper comparison workflow |
| MODEL_REVIEW_AND_PLOT_GUIDE.md | Detailed model architecture, changes, scientific caveats and validation checklist |
| tests/ | Unit tests for ASF, TEA, uncertainty setters, balances, feed basis and energy diagnostics |

## Get the thesis branch

If you already cloned the repository, update the working copy with:

```bash
git checkout mtp-presentation-cleanup
git pull origin mtp-presentation-cleanup
```

Run the commands below from the repository root. The original literature/input `.xlsm` workbook is not modified by these code and documentation changes.

## Installation

Use a clean virtual environment. The repository does not currently include a fully pinned lockfile, so record the actual package versions used for any final thesis run.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks environment activation, use the Python executable inside .venv\Scripts\python.exe directly or activate the environment using your approved local policy.

### macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run the model

Run commands from the repository root (the folder containing run_all.py). On Windows, `run_prefinal.ps1` performs syntax compilation, tests, the 3,000-sample run, supplementary screens and three independent LHS replicates in sequence.

### Full analysis — recommended for the thesis run

```bash
python run_all.py --n 3000 --seed 1234 --no-show
```

This runs the baseline, cost breakdown, ASF analysis, ethanol-route comparison, hydrogen-route comparison, plant-scale sweep, temperature-pressure sweep, catalyst-deactivation sweep, and Monte Carlo analysis with 3,000 Latin-hypercube samples. --no-show saves the figures without opening plot windows.

The default output directory is prefinal_results/. It is created automatically. Existing results/ files are not overwritten by the default run.

### Quick deterministic run

```bash
python run_all.py --quick --no-show
```

This skips Monte Carlo. It is useful for checking deterministic sections and plots, but it does not produce Monte Carlo percentiles, Monte Carlo samples, or Spearman sensitivity rankings.

### Choose a different sample count or output folder

```bash
python run_all.py --n 1000 --no-show
python run_all.py --n 3000 --no-show --out results_3000
```

Do not use --quick when the objective is to run the uncertainty analysis.

### Supplementary sensitivities

Run the hydrogen-storage capital sensitivity and an indicative SAF-vs-fossil-ATF price-parity screen:

```powershell
python additional_sensitivities.py --out prefinal_results
```

The storage sweep tests 1, 3, 7, 14 and 30 days and reports hydrogen tank installed cost, total installed equipment cost, FCI and MJSP. Storage duration changes tank sizing/capital in the current model; it does not simulate dynamic inventory operation or supply interruptions.

The price-parity screen compares the deterministic SAF MJSP with the configured fossil ATF benchmark. It is **not a subsidy estimate**: the SAF model price and fossil benchmark may differ in tax, delivery, date and location basis. Harmonize those bases before drawing a policy conclusion.

### Independent LHS replicate check

The prefix-based diagnostic above uses subsets of one LHS design. For a stronger check, run multiple independent designs with distinct seeds:

```bash
python run_mc_replicates.py --n 1000 --replicates 3 --seed 1234 --out prefinal_results/replicates
```

This performs three fresh 1,000-sample runs, saves each replicate's sample table, and writes `mc_replicate_summary.csv` with valid/failed counts, mean, standard deviation and P5/P50/P95 MJSP. Compare the replicate quantiles and failure fractions; large differences indicate that the uncertainty estimates are not yet stable. This is a diagnostic, not a guarantee of convergence.

## Outputs

The runner writes files under prefinal_results/ by default:

- PNG and PDF versions of the generated figures
- CSV tables for deterministic route, scale, temperature-pressure and deactivation sweeps, plus `sweep_failures.csv` with solver exceptions and non-finite points that were retried individually
- Monte Carlo sample table when the full uncertainty run is enabled
- `monte_carlo_failed_samples.csv` for failed or non-finite samples; the run manifest records requested, valid and failed counts plus MJSP percentiles
- Prefix-based percentile stability diagnostic at available checkpoints (250, 500, 1,000, 2,000 and the final valid sample count). This uses subsets of one LHS design, not independent replicated LHS convergence proof.
- Optional independent replicate outputs from `run_mc_replicates.py`, including each sample table and a cross-replicate quantile summary.

The runner reports the number of converged Monte Carlo samples and MJSP percentiles. The baseline balance metrics are process-only: catalyst make-up is reported separately because spent catalyst is not yet modelled as an outlet. Check that count before interpreting the distribution; failed samples are excluded from the reported percentile calculation. A `run_manifest.json` is also written with the command, seed, Git revision (when available), Python/platform details, dependency versions and baseline inputs/results. Preserve it with the CSVs and figures.

## ASF selectivity basis

The raw weight_fractions(alpha) function represents the full ASF chain distribution and includes k=1, which is ethylene monomer. The oligomerizer only forms products for k >= 2. The process model therefore uses oligomer_weight_fractions(alpha), which removes the monomer term and normalizes the distribution over actual oligomer products.

The 63 wt% Heveling reference used to calibrate the ASF intercept is treated as C8+ on the oligomer-product basis. It is not 63 wt% C8–C16 SAF. The fixed literature split (20/15/62/3) is a separate selectivity assumption and is retained as a comparison scenario. Do not conflate the C8+ calibration target with the C8–C16 SAF fraction.

The temperature-sensitivity parameter dE remains unresolved unless fitted from suitable temperature-selectivity data. Temperature-pressure trends depending on the assumed dE are exploratory, not experimentally validated predictions.

## Monte Carlo interpretation

- **Coupled parameters** change the process model and require flowsheet re-simulation. The oligomerization-pressure setter synchronizes the upstream compressor (K202), ethylene purification column (D202), and oligomerization reactor (R202); changing only two of these would leave an internally inconsistent sampled case.
- **Isolated parameters** change economics without changing material flows.
- Labour cost and loan interest setters update the live TEA object as well as the settings dictionary.
- The distributions and ranges in uncertainty.py are not all empirical probability distributions. Several are judgement-based ranges or placeholders and must be supported with citations or clearly presented as scenario assumptions.
- A 3,000-sample run is a starting point, not proof of convergence. The runner now reports a prefix-based percentile stability diagnostic; for a stronger convergence claim, also run independent LHS replicates at increasing sample counts and compare the resulting quantiles and rank correlations.

## Tests

GitHub Actions runs the unit-test suite on pushes and pull requests targeting `mtp-presentation-cleanup`. The workflow installs the model dependencies on Python 3.12 and runs `python -m pytest -q`; check the Actions result for the exact commit before treating the suite as passing.

Run the tests locally from the repository root:

```bash
pytest -q
```

These tests cover ASF distribution normalization, the oligomer-product basis, the C8+ calibration target, the C8–C16 bound check, WDV depreciation and residual value, Monte Carlo setter propagation, coupled reactor/heater/compressor settings, total feed-volume conversion, elemental-balance diagnostics, catalyst make-up exclusion from process-only balances, and unit-level energy diagnostics. They do not replace a full BioSTEAM integration test or validation against experimental plant data.

## Important limitations before using results in a thesis

1. **2G ethanol price:** INR 160/L is a production-cost proxy; the transport and delivered basis are unresolved.
2. **Hydrogen boundary:** green off-site delivery cost is not fully represented. Green on-site and blue hydrogen are excluded from the comparison sweep because green on-site requires electrolyser CAPEX, renewable electricity, water treatment, compression/storage, stack replacement and utilization assumptions, while blue hydrogen requires a sourced CCS cost.
3. **ASF selectivity:** C8+ calibration is not C8–C16 SAF selectivity. The fixed literature split and ASF model are structurally different representations.
4. **Temperature dependence:** dE is not fitted unless supported by multiple temperature-selectivity observations.
5. **Catalyst deactivation:** cycle-average activity decay and catalyst replacement lifetime are separate assumptions.
6. **Depreciation:** the TEA uses a simplified WDV-shaped proxy. It does not split tax asset blocks or model terminal disposal proceeds / tax recapture.
7. **Equipment costs:** the pressure-vessel cost correlation is explicitly marked in units.py as requiring verification against its source. Some equipment correlations may be outside their stated ranges.
8. **Capacity basis:** KLPD is treated as total ethanol-water feed volume. The mass conversion now estimates mixture density using additive specific volumes; validate this against a rigorous ethanol-water mixture property calculation before reporting capacity.
9. **Balance boundary:** catalyst make-up streams are costed as external feeds, but spent catalyst discharge is not represented. Process-only mass and C/H/O diagnostics exclude `Cat_dehyd`, `Cat_olig` and `Cat_hydgn`, and report their combined flow separately as `catalyst_makeup_kg_hr_excluded`. This avoids misreporting catalyst replacement as a process loss, but it is not a complete plant-wide waste balance. Add spent-catalyst outlets and disposal/regeneration handling before claiming overall plant closure.
10. **Independent validation:** complete carbon, hydrogen and oxygen balances, stream mass balances, energy-duty checks, unit checks and selected comparisons against literature or independently calculated values.
10. **Runtime status:** a successful BioSTEAM simulation is not, by itself, process validation. Do not report new numerical results as verified until the current branch has been run locally and its logs, warnings, convergence and balances have been reviewed.

For the complete issue-by-issue checklist, see [MODEL_REVIEW_AND_PLOT_GUIDE.md](MODEL_REVIEW_AND_PLOT_GUIDE.md) and [prefinal validation register](prefinal_results/VALIDATION_CHECKLIST.md).
