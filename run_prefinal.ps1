$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Checked {
    param([string]$Description, [string]$Command, [string[]]$Arguments)
    Write-Host "`n=== $Description ===" -ForegroundColor Cyan
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE. No later stages were run."
    }
}

# Run inside the repository's Python 3.12 virtual environment.
Invoke-Checked "Compile project scripts" "python" @("-m", "py_compile", "run_all.py", "validate_paper.py", "additional_sensitivities.py", "run_mc_replicates.py", "ethanol_price_basis_audit.py")
Invoke-Checked "Run unit tests" "python" @("-m", "pytest", "-q")
Invoke-Checked "Run deterministic analysis and 3,000-sample LHS Monte Carlo" "python" @("run_all.py", "--n", "3000", "--seed", "1234", "--no-show", "--out", "final_results")
Invoke-Checked "Run supplementary H2-storage and ATF price-parity screens" "python" @("additional_sensitivities.py", "--out", "final_results")
Invoke-Checked "Run ethanol-price basis audit (1G reference vs 2G cost cases)" "python" @("ethanol_price_basis_audit.py", "--out", "final_results/ethanol_price_basis_audit.csv")
Invoke-Checked "Run three independent 1,000-sample LHS replicates" "python" @("run_mc_replicates.py", "--n", "1000", "--replicates", "3", "--seed", "1234", "--out", "final_results/replicates")

Write-Host "`nFull workflow completed. Review prefinal_results1/VALIDATION_CHECKLIST.md and final_results failure/convergence diagnostics before using the outputs." -ForegroundColor Green
