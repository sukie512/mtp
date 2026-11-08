# Prefinal analysis outputs

This directory is the designated destination for the pre-defence model run. At repository setup time it contains instructions and the validation checklist only; numerical CSVs, plots and Monte Carlo outputs are generated when the run scripts execute.

Generated files are local run artifacts and are not committed automatically. Keep the accompanying `run_manifest.json`, CSV diagnostics, Monte Carlo samples, plots and replicate summaries together. Do not mix these with historical `results/` folders.

On Windows, the full sequence is bundled in `run_prefinal.ps1` (run it from a Python 3.12 virtual environment). Alternatively, use the individual commands below.

Recommended sequence from the repository root:

```powershell
python -m py_compile run_all.py additional_sensitivities.py run_mc_replicates.py
pytest -q
python run_all.py --n 3000 --seed 1234 --no-show --out prefinal_results
python additional_sensitivities.py --out prefinal_results
python run_mc_replicates.py --n 1000 --replicates 3 --seed 1234 --out prefinal_results/replicates
```

Only label outputs as final after reviewing the test result, solver failures, Monte Carlo valid-sample count, independent replicate stability, material/element balances, energy diagnostics and unresolved-input register. The original literature workbook is not modified by these scripts.
