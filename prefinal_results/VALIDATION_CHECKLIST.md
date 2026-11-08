# Prefinal validation checklist

This register separates implemented corrections from unresolved evidence/model work. Do not silently replace unresolved inputs with invented values. The prefinal run can still be generated, but its outputs must be labelled with these limitations.

## Implemented in code

- [x] All primary and supplementary analysis scripts now write to `prefinal_results/` by default.
- [x] CI uses Python 3.12, matching the current ThermoSTEAM dependency's Python requirement.
- [x] Duplicate GitHub Actions workflow removed.
- [x] 2G cellulosic ethanol no longer receives the generic conventional-route transport adder. Its quoted INR 160/L input remains a production-cost proxy; 2G delivery/storage is excluded, not assumed free.
- [x] Ethanol purchase price is converted to a per-kg total ethanol-water feed price using the configured ethanol mass fraction, so the water fraction is not charged as pure ethanol.
- [x] New tests cover the 2G/conventional transport distinction and the total-feed pricing basis.
- [x] Main Monte Carlo runner now writes failed/non-finite samples to `monte_carlo_failed_samples.csv` and records requested/valid/failed counts and MJSP percentiles in `run_manifest.json`.

## High-priority unresolved items

| Item | Current treatment | Evidence/action needed before calling results final |
|---|---|---|
| India location factor (0.90) | Unresolved assumption; scales FCI | Obtain India-vs-US installed-cost factor from a traceable cost database or EPC estimate; document plant location, battery limits and year |
| Labour cost (USD 1.2M/y) | Unresolved placeholder | Obtain a defensible staffing plan for this plant; combine with NIC-20 chemical-industry ASI emoluments/person data and state/plant-specific allowances. Do not use an all-industry wage average |
| 2G ethanol cost (INR 160/L) | Production-cost proxy | Obtain a project-specific ex-plant/offtake quote and logistics/storage to the ATJ site. Current 2G delivery cost is excluded |
| Green off-site H2 (INR 363/kg) | Refinery-gate price anchor | Add transport, compression/loading, delivery, unloading and inventory losses/costs for the actual plant location |
| Green on-site H2 | Excluded from route comparison | Build electrolyser, renewable electricity/PPA, water treatment, compression/storage, stack replacement and utilization CAPEX/OPEX |
| Blue H2 | Excluded from route comparison | Build SMR + capture rate + CO2 conditioning/transport/storage + residual emissions and costs |
| ASF temperature slope dE = 15 kJ/mol | Placeholder; one-point intercept calibration only | Fit from multiple catalyst-specific temperature/selectivity observations. Until then T-P selectivity sweeps are exploratory |
| Catalyst deactivation kd and cycle length | Scenario assumptions | Obtain time-on-stream conversion/selectivity data and regeneration-cycle evidence for the relevant Ni catalyst |
| WHSV basis in all three reactors | Catalyst mass currently uses total reactor feed mass / WHSV | Verify each cited source's exact feed basis (fresh feed vs recycle-inclusive, ethanol vs aqueous feed, ethylene vs total gas) and align each reactor separately |
| X / X0 definitions | Reactant conversion parameters in code | Verify definitions, basis and operating conditions against each cited paper; do not assume the same symbol means identical basis |
| Pressure-vessel cost correlation | Code warns coefficients were typed from memory | Verify exact Seider equation, units, applicable size/pressure range, metallurgy, CEPCI basis and purchase-vs-installed cost |
| CEPCI and input-price year | CEPCI 2023 alongside 2026 India prices | Harmonize all capital and operating prices to a common base year with traceable escalation indices |
| Indian depreciation/tax | Simplified WDV-shaped proxy | Confirm asset-block rules, half-year/full-year convention, commissioning timing, tax losses, terminal book value and disposal/tax recapture with tax source/adviser |
| Heat integration and utilities | Simplified heat/power duties; no full integration network | Add heat recovery, steam/boiler-turbogenerator and cooling utility design; validate steam balance and net purchased electricity |
| Wastewater treatment | Per-kg wastewater cost proxy | Define wastewater composition, flow, treatment train, discharge standard, sludge and CAPEX/OPEX; reconcile with process utility boundary |
| Catalyst waste/regeneration | Catalyst makeup costed; spent catalyst outlet absent | Add spent-catalyst flow, regeneration/recovery, disposal and replacement logistics; current process balance is not whole-plant closure |
| FX conversion | Refreshed to ₹94.1402/USD using the RBI/FBIL reference rate for 6 Nov 2026 | Refresh to the reference rate on the actual run date; retain the dated value in the manifest/input record |
| Fossil ATF benchmark | Refreshed to about ₹138.50/L for Delhi, effective 1 Nov 2026 | Verify against the direct IOCL monthly notification and reconcile airport charges, tax and delivery basis with plant-gate SAF MJSP |
| Co-product prices | Naphtha/diesel anchors have different source dates and tax bases | Refresh plant-gate realizable netback prices, quality/specification, transport, tax and sales basis |
| Correlated prices | Most price distributions sampled independently | Add correlations only when supported by paired historical data or a defensible common-driver model; do not invent coefficients |

## Required prefinal run and review

1. Create/use a Python 3.12 environment and install `requirements.txt`.
2. Run syntax compilation and the full unit-test suite.
3. Run the deterministic + 3,000-sample analysis to `prefinal_results/`.
4. Run the hydrogen storage sensitivity and price-parity screen to the same folder.
5. Run at least three independent 1,000-sample LHS replicates into `prefinal_results/replicates/`; compare P5/P50/P95 and failure fractions. If they disagree materially, increase sample count and investigate.
6. Review `sweep_failures.csv`, `monte_carlo_failed_samples.csv`, `monte_carlo_convergence.csv`, `mc_replicate_summary.csv`, `unit_energy_diagnostics.csv`, and process/element balance diagnostics.
7. Check the run manifest's Git revision, Python/package versions, seed and valid sample count. Never mix outputs from different revisions.
8. Preserve this checklist with the figures and CSVs. A successful test suite or converged simulation does not validate unresolved process assumptions or cost correlations.

## Commands

```powershell
python -m py_compile run_all.py additional_sensitivities.py run_mc_replicates.py
pytest -q
python run_all.py --n 3000 --seed 1234 --no-show --out prefinal_results
python additional_sensitivities.py --out prefinal_results
python run_mc_replicates.py --n 1000 --replicates 3 --seed 1234 --out prefinal_results/replicates
```
