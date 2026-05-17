# SQE XAUUSD deconstruct matrix — all configs (full suite: QuantBuild + QuantLog + QuantAnalytics + QuantOS collect).
# Prereq: from suite root, all sibling repos present. Set:
#   $env:QUANTMETRICS_SUITE_ROOT = "<path-to-quantmetrics-suite>"

$ErrorActionPreference = "Stop"
$SuiteRoot = if ($env:QUANTMETRICS_SUITE_ROOT) { $env:QUANTMETRICS_SUITE_ROOT } else {
  (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
$env:QUANTMETRICS_SUITE_ROOT = $SuiteRoot
$Qb = Join-Path $SuiteRoot "quantbuild"
$env:PYTHONPATH = (Join-Path $Qb "src")

$configs = @(
  "configs/experiments/sqe_xauusd_deconstruct_2026/BASE.yaml",
  "configs/experiments/sqe_xauusd_deconstruct_2026/V1_h1_gate_off.yaml",
  "configs/experiments/sqe_xauusd_deconstruct_2026/V2_combo_min_3.yaml",
  "configs/experiments/sqe_xauusd_deconstruct_2026/V3_expansion_only.yaml",
  "configs/experiments/sqe_xauusd_deconstruct_2026/V4_trend_only.yaml",
  "configs/experiments/sqe_xauusd_deconstruct_2026/V5_lookback_3.yaml"
)

Set-Location $Qb
foreach ($c in $configs) {
  Write-Host "=== BACKTEST $c ===" -ForegroundColor Cyan
  python -m src.quantbuild.app --config $c backtest
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Done. Artifacts under quantmetrics_os/runs/EXP-SQE-XAUUSD-DECON-2026-*" -ForegroundColor Green
