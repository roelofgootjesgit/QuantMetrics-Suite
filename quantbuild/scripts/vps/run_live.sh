#!/usr/bin/env bash
# Run QuantBuild CLI with the same env as QuantOS (quantmetrics_os/orchestrator .env).
# Use this on the VPS when you normally keep CTRADER_* in orchestrator/.env but
# start manually from quantbuild — plain `python -m ...` does NOT load that file.
#
# Usage (from anywhere):
#   /root/dev/quant/quantbuild/scripts/vps/run_live.sh --config configs/demo_strict_ctrader.yaml live --dry-run
#
# Env:
#   QUANTBUILD_ROOT       — override checkout (default: repo root containing this script)
#   QUANTBUILD_ORCHESTRATOR_ENV — explicit path to orchestrator/.env
#   PYTHON                — override interpreter (default: $ROOT/.venv/bin/python)
#
# Issue #104 B1: gate keys must not be minted by sourcing checkout env files.
# Defense: snapshot set/unset + values of the three gate keys BEFORE source;
# if any presence/value changes, restore snapshot and exit 2 BEFORE exec.
# Residual risk: sourcing is not a sandbox — arbitrary commands in the file are
# not prevented; only gate-key mutations are detected. Prefer trusted external
# EnvironmentFiles outside the repo for authorization.
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_ROOT="${QUANTBUILD_ROOT:-$(cd "$_SCRIPT_DIR/../.." && pwd)}"
cd "$_ROOT"

_ORCH_EXPLICIT="${QUANTBUILD_ORCHESTRATOR_ENV:-}"
_ORCH_CANDIDATES=(
  "$_ORCH_EXPLICIT"
  "$_ROOT/../quantmetrics_os/orchestrator/.env"
  "/root/dev/quant/quantmetrics_os/orchestrator/.env"
)

_gate_keys=(
  QUANTMETRICS_EXECUTION_AUTHORIZED
  QUANTMETRICS_ALLOWED_ACCOUNT_IDS
  QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS
)

# Snapshot: for each key, record whether it was set and its value.
_snap_set=()
_snap_val=()
_snapshot_gate_keys() {
  local _k
  _snap_set=()
  _snap_val=()
  for _k in "${_gate_keys[@]}"; do
    if [[ -n "${!_k+x}" ]]; then
      _snap_set+=("1")
      _snap_val+=("${!_k}")
    else
      _snap_set+=("0")
      _snap_val+=("")
    fi
  done
}

_restore_gate_keys() {
  local _i _k
  for _i in "${!_gate_keys[@]}"; do
    _k="${_gate_keys[$_i]}"
    if [[ "${_snap_set[$_i]}" == "1" ]]; then
      printf -v "$_k" '%s' "${_snap_val[$_i]}"
      export "$_k"
    else
      unset "$_k" || true
    fi
  done
}

_gate_keys_changed() {
  local _i _k
  for _i in "${!_gate_keys[@]}"; do
    _k="${_gate_keys[$_i]}"
    if [[ "${_snap_set[$_i]}" == "1" ]]; then
      if [[ -z "${!_k+x}" || "${!_k}" != "${_snap_val[$_i]}" ]]; then
        return 0
      fi
    else
      if [[ -n "${!_k+x}" ]]; then
        return 0
      fi
    fi
  done
  return 1
}

_sourced=""
for _c in "${_ORCH_CANDIDATES[@]}"; do
  [[ -z "$_c" ]] && continue
  if [[ -f "$_c" ]]; then
    _snapshot_gate_keys
    set -a
    # shellcheck source=/dev/null
    source "$_c"
    set +a
    if _gate_keys_changed; then
      echo "run_live: refuse env file that mutated gate keys: ${_c}" >&2
      echo "run_live: residual risk — sourced files are not sandboxed; use external EnvironmentFile for auth." >&2
      _restore_gate_keys
      exit 2
    fi
    _sourced="$_c"
    break
  fi
done

if [[ -n "$_sourced" ]]; then
  echo "run_live: loaded environment from $_sourced" >&2
else
  echo "run_live: no orchestrator .env found; using shell + quantbuild/.env only (python-dotenv)." >&2
  echo "run_live: set QUANTBUILD_ORCHESTRATOR_ENV or create ../quantmetrics_os/orchestrator/.env (QuantOS)" >&2
fi

_PY="${PYTHON:-${_ROOT}/.venv/bin/python}"
export PYTHONPATH="${_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
exec "$_PY" -m src.quantbuild.app "$@"
