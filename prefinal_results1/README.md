# New prefinal analysis outputs

This is the dedicated destination for the next complete India ATJ model run. The existing `results/`, `results_old_100samples/` and `prefinal_results/` folders are retained unchanged.

## Run

From the repository root, using the Python 3.12 environment:

```powershell
.\run_prefinal.ps1
```

Or run the main analysis and supplementary stages individually:

```powershell
python run_all.py --n 3000 --seed 1234 --no-show --out prefinal_results1
python additional_sensitivities.py --out prefinal_results1
python ethanol_price_basis_audit.py --out prefinal_results1/ethanol_price_basis_audit.csv
python run_mc_replicates.py --n 1000 --replicates 3 --seed 1234 --out prefinal_results1/replicates
```

The main runner's default output is now `prefinal_results1/`; the supplementary sensitivity and replicate scripts use that folder by default as well. The PowerShell workflow explicitly directs every stage there.

## Expected contents

The run generates baseline and deterministic-sweep CSVs, Monte Carlo samples and failed samples, convergence and sensitivity diagnostics, sweep failure logs, run manifest, PNG/PDF figures, supplementary hydrogen-storage and price-parity screens, ethanol price-basis audit, and independent LHS replicate outputs under `replicates/`.

The folder is created automatically when the scripts run. Generated numerical outputs are not committed by this code change; they will appear locally after the workflow is executed.

## Validation before reporting

Do not treat a successful run as scientific validation. Review the run manifest, valid/failed Monte Carlo counts, sweep failures, convergence diagnostics, replicate stability, material/element balances, energy diagnostics, and the unresolved-input register before using numerical results in the thesis.
