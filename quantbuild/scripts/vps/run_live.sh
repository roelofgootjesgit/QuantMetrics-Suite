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

# Issue #104: refuse env files that mint live-gate keys (N10c). Auth must be
# process/systemd-only, never developer/orchestrator dotenv inside a checkout.
_gate_keys=(
  QUANTMETRICS_EXECUTION_AUTHORIZED
  QUANTMETRICS_ALLOWED_ACCOUNT_IDS
  QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS
)
_refuse_env_with_gate_keys() {
  local _file="$1"
  local _key
  local _line
  while IFS= read -r _line || [[ -n "$_line" ]]; do
    _line="${_line#"${_line%%[![:space:]]*}"}"
    [[ -z "$_line" || "$_line" == \#* ]] && continue
    for _key in "${_gate_keys[@]}"; do
      if [[ "$_line" == "$_key="* || "$_line" == "$_key ="* ]]; then
        echo "run_live: refuse env file with gate key ${_key}: ${_file}" >&2
        return 1
      fi
    done
  done < "$_file"
  return 0
}

_sourced=""
for _c in "${_ORCH_CANDIDATES[@]}"; do
  [[ -z "$_c" ]] && continue
  if [[ -f "$_c" ]]; then
    if ! _refuse_env_with_gate_keys "$_c"; then
      exit 2
    fi
    set -a
    # shellcheck source=/dev/null
    source "$_c"
    set +a
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
