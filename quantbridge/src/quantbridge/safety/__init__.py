"""Fail-closed live execution safety (issue #104 PR-A)."""

from quantbridge.safety.live_execution_gate import (
    GATE_ENV_KEYS,
    LiveExecutionDenied,
    LiveExecutionRequest,
    assert_dotenv_path_has_no_gate_keys,
    assert_live_execution_allowed,
    canonicalize_ctrader_account_id,
    canonicalize_oanda_account_id,
    default_bridge_env_files,
    env_file_contains_gate_keys,
    gate_keys_changed,
    load_dotenv_refusing_gate_keys,
    resolve_ctrader_host,
    restore_gate_keys,
    snapshot_gate_keys,
)

__all__ = [
    "GATE_ENV_KEYS",
    "LiveExecutionDenied",
    "LiveExecutionRequest",
    "assert_dotenv_path_has_no_gate_keys",
    "assert_live_execution_allowed",
    "canonicalize_ctrader_account_id",
    "canonicalize_oanda_account_id",
    "default_bridge_env_files",
    "env_file_contains_gate_keys",
    "gate_keys_changed",
    "load_dotenv_refusing_gate_keys",
    "resolve_ctrader_host",
    "restore_gate_keys",
    "snapshot_gate_keys",
]
