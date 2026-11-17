"""PR-B entrypoint preflight — thin wrapper around the canonical QuantBridge gate.

Does not duplicate policy. Import failure ⇒ deny (P3).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, Mapping, Optional, Sequence


def _ensure_quantbridge_on_path() -> None:
    root = Path(__file__).resolve().parents[2]  # quantbuild repo root
    bridge_src = (root.parent / "quantbridge" / "src").resolve()
    if bridge_src.is_dir() and str(bridge_src) not in sys.path:
        sys.path.insert(0, str(bridge_src))


def preflight_live_execution(
    *,
    provider: str,
    environment: str,
    account_id: str,
    intent: Literal["SESSION", "ORDERS"],
    environ: Mapping[str, str] | None = None,
    env_file_paths: Sequence[Path] | None = None,
) -> None:
    """Raise LiveExecutionDenied / RuntimeError unless the canonical gate allows."""
    _ensure_quantbridge_on_path()
    try:
        from quantbridge.safety.live_execution_gate import (
            LiveExecutionDenied,
            LiveExecutionRequest,
            assert_live_execution_allowed,
        )
    except ImportError as exc:
        raise RuntimeError(f"LiveExecutionDenied: gate_import_failed: {exc}") from exc

    kwargs: dict = {
        "environ": environ,
    }
    if env_file_paths is not None:
        kwargs["env_file_paths"] = env_file_paths
    try:
        assert_live_execution_allowed(
            LiveExecutionRequest(
                provider=provider,
                environment=environment,
                account_id=account_id,
                intent=intent,
            ),
            **kwargs,
        )
    except LiveExecutionDenied:
        raise


def broker_fields_from_cfg(cfg: Mapping) -> tuple[str, str, str]:
    """Return (provider, environment, account_id) from a QuantBuild config dict."""
    broker = cfg.get("broker") if isinstance(cfg.get("broker"), dict) else {}
    broker = broker or {}
    provider = str(broker.get("provider", "ctrader") or "ctrader").strip().lower()
    if provider == "oanda":
        default_env = "practice"
    else:
        default_env = "demo"
    environment = str(broker.get("environment", default_env) or default_env)
    account_id = str(broker.get("account_id", "") or "")
    return provider, environment, account_id
