# MTP model review and presentation guide

## Model architecture

The repository implements an India-focused alcohol-to-jet (ATJ) techno-economic model for producing sustainable aviation fuel (SAF) from ethanol. The main computational path is:

`settings.py` → `atj_chemicals.py` → `units.py` → `system.py` → `tea.py` → `analysis.py` → `uncertainty.py` → `run_all.py`

The `.xlsm` literature/input workbook is not read or modified by the plotting changes in this branch.

## What each source file does

| File | Responsibility | How to think about it |
|---|---|---|
| `settings.py` | Central assumptions: plant capacity, feedstock prices, utilities, finance, catalysts, reactor conditions and exchange rate | The model's input sheet. Each value should have a source or be clearly identified as an assumption. |
| `atj_chemicals.py` | Defines the chemical species and chemical groups used by BioSTEAM | The model's chemical dictionary: ethanol, water, ethylene, olefins, paraffins and product cuts. |
| `asf_model.py` | Implements Anderson–Schulz–Flory (ASF) chain-growth fractions, the temperature/pressure relation for alpha, calibration and cycle-average deactivation | The mathematical selectivity and catalyst-activity model. |
| `units.py` | Defines custom BioSTEAM unit operations: catalytic reactors, dehydration, oligomerization, hydrogenation and storage tanks | The individual process equipment models and their mass/energy/cost calculations. |
| `system.py` | Connects all units and streams into the complete flowsheet; assigns stream and utility prices | The process flowsheet: feed preparation, dehydration, purification, oligomerization, hydrogenation, separation and storage. |
| `tea.py` | Defines the India-specific discounted-cash-flow TEA and capital/operating-cost factors | Converts the simulated plant into project cash flows and a minimum selling price. |
| `analysis.py` | Runs a fresh flowsheet, calculates headline metrics and performs deterministic parameter sweeps | The analysis API used by the runner and uncertainty model. |
| `uncertainty.py` | Defines uncertain parameters, Latin-hypercube sampling, model evaluation and metrics | Propagates uncertain technical/economic inputs into MJSP and SAF-yield distributions. |
| `selectivity_scenarios.py` | Compares the fixed literature split with ASF-based product distribution | A focused comparison of two different selectivity representations. |
| `validate_paper.py` | Reconstructs the reference paper's assumptions and checks how closely the repository model reproduces them | A validation exercise; it is not the India base case. |
| `run_all.py` | Runs the baseline, cost breakdown, deterministic sweeps and Monte Carlo analysis; exports tables and figures | The end-to-end analysis and plotting entry point. |
| `units.py` / `system.py` | Contain the process/equipment implementation and flowsheet wiring respectively | Keep physical transformations in units and process connectivity/pricing in the flowsheet. |
| `india_atj_colab.ipynb` | Notebook-based packaging/execution workflow | Treat as a second execution route; reconcile it with the root-level Python modules before presenting it as the canonical model. |

## Changes made on this branch

### 1. Presentation-ready plots

- Standardized the plotting font to DejaVu Sans and increased axis, tick, legend and title sizes.
- Set 300 dpi PNG export and added PDF export for vector-quality slides.
- Replaced informal/placeholder chart titles and labels with descriptive titles and physical units.
- Renamed chart files with ordered, descriptive names.
- Added clearer labels for MJSP, SAF production, plant capacity, hydrogen price, reactor temperature/pressure and catalyst deactivation.
- Removed the plot annotation that explicitly called an ethanol price a placeholder. This does **not** validate the input; unresolved assumptions remain documented in the model.
- Kept figures open for interactive display unless `--no-show` is selected.

### 2. Runner robustness

- Removed global warning suppression so important BioSTEAM, numerical and thermodynamic warnings remain visible.
- Corrected the fallback sweep logic so it does not re-run the baseline simulation for every failed sweep point merely to discover the output columns.
- Replaced runtime source-code rewriting for importing `uncertainty.py` with normal imports; the uncertainty module now supports both package and flat-folder execution.

### 3. ASF distribution tail

`weight_fractions()` previously truncated the ASF distribution at `kmax` and renormalized the retained terms. At high alpha this can bias the distribution because a non-negligible amount of mass can lie beyond the cutoff. The last returned bin now represents the complete `k >= kmax` tail, preserving the infinite-series mass balance without artificial renormalization.

### 4. Scenario isolation

`analysis.run(s=...)` previously modified a caller-supplied settings dictionary in place. It now deep-copies supplied settings so one scenario cannot silently contaminate a later scenario.

## Important scientific/model issues still requiring a decision

These are not cosmetic issues. They can change the reported MJSP, selectivity or engineering interpretation. They have deliberately not been silently changed.

1. **ASF monomer basis (corrected in this branch):** the raw ASF distribution includes `k=1` C2/ethylene, but the oligomerizer produces only `k=2...9` oligomers. The new `oligomer_weight_fractions()` helper removes the monomer term and renormalizes the product distribution over `k >= 2`. The reactor now applies its nominal conversion `X` across this product-only distribution, so the omitted monomer fraction no longer silently reduces realised conversion. The raw `weight_fractions()` helper remains available for the full ASF distribution.
2. **63% reference selectivity:** calibration now interprets the Heveling 63 wt% C8+ reference on the oligomer-product basis (`k >= 2`). It is still not 63 wt% C8–C16 SAF: the C8+ category includes products heavier than C16. The paper's fixed 20/15/62/3 split is a different product-distribution assumption. The ASF model's C8–C16 fraction is structurally bounded well below 63%; compare the two assumptions explicitly.
3. **Temperature sensitivity parameter:** `dE = 15 kJ/mol` is currently an unresolved assumption. A single reference selectivity point can calibrate the intercept (`beta0`) but cannot identify the temperature slope (`dE`). T–P sweep trends are exploratory until a second or multiple temperature-selectivity data points support a fit.
4. **Catalyst deactivation:** `kd` and cycle length affect cycle-average activity, while catalyst lifetime affects replacement cost. They are separate inputs and need separate evidence; one must not be used as a proxy for the other.
5. **Depreciation:** `tea.py` creates an unnormalized declining-balance WDV-shaped schedule, retaining the residual book fraction after the model horizon. That is a modelling proxy, not automatically the Indian statutory WDV tax schedule. Confirm asset-block treatment, terminal book value and disposal/tax-recapture treatment before using the tax shield in a final result.
6. **Green hydrogen boundary:** the H2 route sweep now compares only green off-site and grey refinery hydrogen. Green on-site and blue hydrogen are excluded because the model does not yet include the electrolyser/renewable-system or CCS cost structures. Off-site delivery from the refinery gate to the ATJ plant remains unresolved.
7. **Equipment cost correlations:** the pressure-vessel correlation in `units.py` is explicitly marked as requiring verification against the cited source. Verify vessel sizing, design pressure, wall thickness, material, CEPCI basis and purchase/installed-cost treatment before treating FCI as final.
8. **Capacity basis:** KLPD is treated as total ethanol-water feed volume. The mass-flow helper now estimates mixture density from ethanol/water mass fractions using additive specific volumes. This is an approximation; validate it against a rigorous mixture-density calculation before treating capacity as final.
9. **Uncertainty distributions and convergence:** several bounds are judgement-based or marked unresolved in the source comments. Keep them as scenario ranges, not empirical confidence intervals, until supported by traceable data. The runner now saves a prefix-based percentile stability diagnostic from the same LHS design; this is useful as a quick stability check but is not a substitute for independent replicated LHS runs at increasing sample counts.
10. **Monte Carlo pressure coupling (corrected):** a sampled oligomerization pressure updates K202 compressor discharge, D202 ethylene-purification column pressure, and R202 reactor pressure together. The earlier review statement that only K202/R202 moved is stale; the current setter and unit test cover all three.
11. **Independent LHS replicates:** `run_mc_replicates.py` runs fresh models with distinct seeds and compares MJSP quantiles and failure fractions across independent designs. This is stronger than the prefix diagnostic in `run_all.py`, which reuses one design. It still does not validate the chosen distributions or the underlying process model.
12. **Catalyst balance boundary:** catalyst make-up streams are costed as external feeds, but spent catalyst discharge is not modelled. `analysis.py` excludes `Cat_dehyd`, `Cat_olig` and `Cat_hydgn` from process-only mass and C/H/O balances, and reports their combined flow as `catalyst_makeup_kg_hr_excluded`. This avoids counting catalyst replacement as an unexplained process loss, but it is not a complete plant-wide material balance. Add spent-catalyst outlets and disposal/regeneration treatment before claiming whole-plant closure.
13. **Independent validation:** `analysis.results()` reports process-only C/H/O and mass-balance diagnostics. `run_all.py` also exports each unit's net heat duty and power demand to `unit_energy_diagnostics.csv`. These are diagnostics, not proof of unit-level correctness. Still inspect unit-level reaction balances, energy duties, equipment sizing and selected hand calculations/literature comparisons. A successful BioSTEAM simulation alone does not validate the process model.
14. **Run reproducibility:** `run_all.py` accepts an explicit `--seed` and writes `run_manifest.json` with the command, seed, Git revision (when available), Python/platform details, package versions and baseline inputs/results. `requirements.txt` centralizes dependencies; GitHub Actions runs the unit tests on the thesis branch.

## Running the updated analysis

From the repository folder, with the required Python packages installed:

```bash
python run_all.py --quick --no-show
```

This runs the deterministic cases and saves the figures/tables without opening plot windows.

For the full uncertainty run:

```bash
python run_all.py --n 3000 --seed 1234 --no-show
```

The figures are written to `prefinal_results/` by default as high-resolution PNG and PDF files; tables are exported as CSV. Use `--out another_folder` to select a different output directory. The full Monte Carlo runtime depends on the machine and convergence behaviour.

## Validation status

This branch contains static code changes only. The BioSTEAM flowsheet and full Monte Carlo run have not been executed in this review environment. Therefore no new numerical result, MJSP, selectivity value or plot is represented as runtime-verified. Run the commands above locally and inspect solver warnings, convergence counts and mass/element balances before using the figures in a defence or presentation.


## Supplementary sensitivity and policy screens

The script `additional_sensitivities.py` adds two small analyses outside the main Monte Carlo runner:

- **Hydrogen storage duration:** rebuilds and simulates the plant at 1, 3, 7, 14 and 30 days of H2 inventory. It reports the H2 tank installed cost, total installed equipment cost, FCI and MJSP. In the present flowsheet, storage days change the tank sizing/capital correlation; they do not model dynamic inventory, delivery outages, truck scheduling or reliability.
- **SAF/fossil ATF price parity:** reports the arithmetic difference and ratio between deterministic SAF MJSP and the configured fossil ATF benchmark. This is a screening calculation only, not a subsidy estimate or full policy model. The benchmark's tax, delivery, date and location basis must be reconciled with the plant-gate SAF MJSP before drawing conclusions.

Run from the repository root:

```powershell
python additional_sensitivities.py --out prefinal_results
```

The pressure-coupling test already exists and confirms that K202, D202 and R202 move together. It should not be re-implemented.

Catalyst deactivation rate/cycle length and catalyst replacement lifetime remain distinct: the current model applies cycle-average activity decay over a run interval while catalyst lifetime determines make-up/replacement cost. This can represent repeated operating/regeneration cycles before eventual replacement, but regeneration recovery, regeneration cost and catalyst-life evidence are not currently modelled. Do not force equality between cycle length and catalyst life without catalyst-specific operating evidence.

The hydrogen-price uncertainty input is explicitly labelled refinery-gate price with delivery excluded. The 77–127% distribution is a scenario range around that gate price; it is not a sourced transport-cost model.
