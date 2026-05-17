# EXP-EXPANSION-MULTI-INSTRUMENT-2026 — fetch (optioneel) + parallel backtest USDJPY / GBPUSD
# Gebruik vanaf repo-root of quantbuild-root; zet QUANTBUILD_ROOT als dat afwijkt.

$ErrorActionPreference = "Stop"
# Repo layout: quantresearch/scripts -> ../.. = suite root -> quantbuild
$QB = if ($env:QUANTBUILD_ROOT) { $env:QUANTBUILD_ROOT } else { (Join-Path $PSScriptRoot "..\..\quantbuild" | Resolve-Path).Path }
Set-Location $QB

$days = if ($env:MULTI_INST_FETCH_DAYS) { [int]$env:MULTI_INST_FETCH_DAYS } else { 1900 }
Write-Host "[multi-inst] QUANTBUILD_ROOT=$QB"
Write-Host "[multi-inst] Prefetch ${days}d 15m+1h for USDJPY, GBPUSD (dukascopy/auto)..."

python -m src.quantbuild.app fetch --symbol USDJPY --days $days --timeframe 15m --source dukascopy
python -m src.quantbuild.app fetch --symbol USDJPY --days $days --timeframe 1h --source dukascopy
python -m src.quantbuild.app fetch --symbol GBPUSD --days $days --timeframe 15m --source dukascopy
python -m src.quantbuild.app fetch --symbol GBPUSD --days $days --timeframe 1h --source dukascopy

$cfgJ = "configs/experiments/exp_expansion_multi_instrument_2026/USDJPY_expansion_first.yaml"
$cfgG = "configs/experiments/exp_expansion_multi_instrument_2026/GBPUSD_expansion_first.yaml"

Write-Host "[multi-inst] Starting parallel backtests..."
$j1 = Start-Job -ScriptBlock {
    param($root, $c)
    Set-Location $root
    python -m src.quantbuild.app --config $c backtest 2>&1
} -ArgumentList $QB.Path, $cfgJ

$j2 = Start-Job -ScriptBlock {
    param($root, $c)
    Set-Location $root
    python -m src.quantbuild.app --config $c backtest 2>&1
} -ArgumentList $QB.Path, $cfgG

Wait-Job $j1, $j2 | Out-Null
Write-Host "`n========== USDJPY ==========`n"
Receive-Job $j1
Write-Host "`n========== GBPUSD ==========`n"
Receive-Job $j2
Remove-Job $j1, $j2

Write-Host "`n[multi-inst] Done. Artifacts under quantmetrics_os/runs/EXP-EXPANSION-MULTI-2026-{USDJPY,GBPUSD}/single/"
