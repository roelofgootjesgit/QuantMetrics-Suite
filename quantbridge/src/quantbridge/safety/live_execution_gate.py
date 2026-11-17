"""Canonical fail-closed live execution gate (issue #104 PR-A).

Process environment is the only trusted source for gate keys after env-file
hygiene checks. Dotenv / bridge local.env / orchestrator .env must not mint
authorization. Environment ``live`` stays frozen until an owner-only enablement
file outside the repo exists.

Gate-key detection uses parser-equivalent ``dotenv_values`` (not line regex),
so ``export KEY=1``, tabs, quotes, and spaced assignments are covered (B1).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, MutableMapping, Optional, Sequence

GATE_ENV_KEYS: tuple[str, ...] = (
    "QUANTMETRICS_EXECUTION_AUTHORIZED",
    "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
    "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS",
)

# Owner-only live-host enablement (outside all repo checkouts). Presence of a
# regular file is required before environment "live" may pass allowlist checks.
DEFAULT_LIVE_ENABLEMENT_PATH = Path("/etc/quantmetrics/execution_authorization")


class LiveExecutionDenied(RuntimeError):
    """Raised when live/session/order execution is not authorized."""


@dataclass(frozen=True)
class LiveExecutionRequest:
    provider: str  # "ctrader" | "oanda"
    environment: str
    account_id: str
    intent: Literal["SESSION", "ORDERS"]


def bridge_repo_root() -> Path:
    """QuantBridge checkout root (``.../quantbridge``), derived from this file."""
    return Path(__file__).resolve().parents[3]


def default_bridge_env_files(*, root: Optional[Path] = None) -> list[Path]:
    base = root if root is not None else bridge_repo_root()
    return [base / "local.env", base / ".env"]


def _dotenv_values(path: Path) -> Mapping[str, Optional[str]]:
    """Parse env file with python-dotenv (parser-equivalent to loaders)."""
    try:
        from dotenv import dotenv_values
    except ImportError as exc:
        raise LiveExecutionDenied(f"dotenv_unavailable:{exc}") from exc
    try:
        return dotenv_values(path)  # type: ignore[return-value]
    except OSError as exc:
        raise LiveExecutionDenied(f"gate_env_file_unreadable:{path}:{exc}") from exc


def env_file_contains_gate_keys(path: Path | str) -> bool:
    """True if dotenv parser sees any frozen gate key in the file (B1)."""
    p = Path(path)
    if not p.is_file():
        return False
    values = _dotenv_values(p)
    for key in GATE_ENV_KEYS:
        if key in values:
            return True
    return False


def assert_dotenv_path_has_no_gate_keys(path: Path | str) -> None:
    """Fail closed if the exact dotenv path contains any gate key (C2 / B1)."""
    p = Path(path)
    if env_file_contains_gate_keys(p):
        raise LiveExecutionDenied(f"gate_key_present_in_dotenv:{p.resolve()}")


def snapshot_gate_keys(
    environ: Mapping[str, str] | None = None,
) -> dict[str, tuple[bool, Optional[str]]]:
    """Capture presence + value of each gate key.

    ``(False, None)`` means unset; ``(True, value)`` means set (value may be empty).
    """
    env = os.environ if environ is None else environ
    out: dict[str, tuple[bool, Optional[str]]] = {}
    for key in GATE_ENV_KEYS:
        if key in env:
            out[key] = (True, env.get(key))
        else:
            out[key] = (False, None)
    return out


def restore_gate_keys(
    snapshot: Mapping[str, tuple[bool, Optional[str]]],
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Restore gate keys to a prior snapshot (undo dotenv/shell mutations)."""
    env: MutableMapping[str, str] = os.environ if environ is None else environ
    for key, (present, value) in snapshot.items():
        if present:
            env[key] = "" if value is None else str(value)
        else:
            env.pop(key, None)


def gate_keys_changed(
    before: Mapping[str, tuple[bool, Optional[str]]],
    after: Mapping[str, tuple[bool, Optional[str]]] | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return True if any gate key presence/value differs from snapshot."""
    current = after if after is not None else snapshot_gate_keys(environ)
    return dict(before) != dict(current)


def load_dotenv_refusing_gate_keys(path: Path | str, *, override: bool = True) -> None:
    """Load dotenv only if file has no gate keys; snapshot/restore on mutation (B1).

    Residual risk: this is not a sandbox for arbitrary code in env files — only
    gate-key presence and post-load process-env mutations are checked.
    """
    from dotenv import load_dotenv

    p = Path(path)
    assert_dotenv_path_has_no_gate_keys(p)
    before = snapshot_gate_keys()
    load_dotenv(p, override=override)
    if gate_keys_changed(before):
        restore_gate_keys(before)
        raise LiveExecutionDenied(f"gate_key_mutated_by_dotenv:{p.resolve()}")


def _scan_env_files(paths: Iterable[Path]) -> None:
    for path in paths:
        if env_file_contains_gate_keys(path):
            raise LiveExecutionDenied(f"gate_key_present_in_env_file:{path.resolve()}")


def _normalize_environment(raw: str) -> str:
    return str(raw or "").strip().lower()


def canonicalize_ctrader_account_id(account_id: str) -> str:
    """Strict numeric cTrader account id: digits only, no leading zeros (P6)."""
    text = str(account_id)
    if text != text.strip() or " " in text or "\t" in text:
        raise LiveExecutionDenied("ctrader_account_id_whitespace_rejected")
    if not text:
        raise LiveExecutionDenied("ctrader_account_id_empty")
    if not text.isdigit():
        raise LiveExecutionDenied("ctrader_account_id_non_numeric")
    if text.startswith("0"):
        raise LiveExecutionDenied("ctrader_account_id_leading_zero_rejected")
    return text


def canonicalize_oanda_account_id(account_id: str) -> str:
    """Oanda account id: strip only; empty rejected."""
    text = str(account_id).strip()
    if not text:
        raise LiveExecutionDenied("oanda_account_id_empty")
    return text


def _parse_csv_allowlist(raw: Optional[str]) -> list[str]:
    if raw is None:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _default_env_allowlist(provider: str) -> list[str]:
    p = provider.strip().lower()
    if p == "ctrader":
        return ["demo"]
    if p == "oanda":
        return ["practice"]
    raise LiveExecutionDenied(f"unsupported_provider:{provider}")


def _allowed_environments(provider: str, environ: Mapping[str, str]) -> list[str]:
    if "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS" not in environ:
        return _default_env_allowlist(provider)
    raw = environ.get("QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS")
    if raw is None or str(raw).strip() == "":
        return []
    return [e.lower() for e in _parse_csv_allowlist(str(raw))]


def live_host_enablement_satisfied(
    *,
    enablement_path: Optional[Path] = None,
) -> bool:
    """Return True only when the owner-only live enablement file exists."""
    path = enablement_path if enablement_path is not None else DEFAULT_LIVE_ENABLEMENT_PATH
    try:
        return path.is_file()
    except OSError:
        return False


def _assert_environment_allowed(
    provider: str,
    environment: str,
    *,
    environ: Mapping[str, str],
    enablement_path: Optional[Path] = None,
) -> str:
    env = _normalize_environment(environment)
    if not env:
        raise LiveExecutionDenied("environment_empty")
    # Hard reject cTrader "practice" even if mis-added to allowlist (B2).
    if provider.strip().lower() == "ctrader" and env == "practice":
        raise LiveExecutionDenied("ctrader_practice_environment_rejected")
    allowed = _allowed_environments(provider, environ)
    if env not in allowed:
        raise LiveExecutionDenied(f"environment_not_allowlisted:{env}")
    if env == "live" and not live_host_enablement_satisfied(enablement_path=enablement_path):
        raise LiveExecutionDenied("live_host_enablement_frozen")
    return env


def _assert_account_allowed(
    provider: str,
    account_id: str,
    *,
    environ: Mapping[str, str],
) -> str:
    if "QUANTMETRICS_ALLOWED_ACCOUNT_IDS" not in environ:
        raise LiveExecutionDenied("account_allowlist_missing")
    raw = environ.get("QUANTMETRICS_ALLOWED_ACCOUNT_IDS")
    entries = _parse_csv_allowlist(raw if raw is not None else "")
    if not entries:
        raise LiveExecutionDenied("account_allowlist_empty")

    prov = provider.strip().lower()
    if prov == "ctrader":
        canonical = canonicalize_ctrader_account_id(account_id)
        allowed_canon: list[str] = []
        for entry in entries:
            try:
                allowed_canon.append(canonicalize_ctrader_account_id(entry))
            except LiveExecutionDenied:
                continue
        if canonical not in allowed_canon:
            raise LiveExecutionDenied("account_not_allowlisted")
        return canonical

    if prov == "oanda":
        canonical = canonicalize_oanda_account_id(account_id)
        allowed = [canonicalize_oanda_account_id(e) for e in entries]
        if canonical not in allowed:
            raise LiveExecutionDenied("account_not_allowlisted")
        return canonical

    raise LiveExecutionDenied(f"unsupported_provider:{provider}")


def _assert_orders_authorized(environ: Mapping[str, str]) -> None:
    # Exact string "1" only (P7) — no strip, no truthy coercion.
    if environ.get("QUANTMETRICS_EXECUTION_AUTHORIZED") != "1":
        raise LiveExecutionDenied("execution_not_authorized")


def assert_live_execution_allowed(
    req: LiveExecutionRequest,
    *,
    environ: Mapping[str, str] | None = None,
    env_file_paths: Sequence[Path] | None = None,
    enablement_path: Optional[Path] = None,
) -> None:
    """Raise LiveExecutionDenied unless policy allows. No network I/O.

    Always scans QuantBridge ``local.env`` / ``.env`` (or ``env_file_paths``)
    for gate keys so direct bridge scripts cannot bypass (C1).
    """
    env_map: Mapping[str, str] = os.environ if environ is None else environ
    paths = (
        list(env_file_paths)
        if env_file_paths is not None
        else default_bridge_env_files()
    )
    _scan_env_files(paths)

    provider = str(req.provider or "").strip().lower()
    if provider not in {"ctrader", "oanda"}:
        raise LiveExecutionDenied(f"unsupported_provider:{req.provider}")

    _assert_environment_allowed(
        provider,
        req.environment,
        environ=env_map,
        enablement_path=enablement_path,
    )
    _assert_account_allowed(provider, req.account_id, environ=env_map)

    if req.intent == "ORDERS":
        _assert_orders_authorized(env_map)
    elif req.intent != "SESSION":
        raise LiveExecutionDenied(f"unsupported_intent:{req.intent}")


def resolve_ctrader_host(
    environment: str,
    *,
    environ: Mapping[str, str] | None = None,
    enablement_path: Optional[Path] = None,
) -> str:
    """Allowlist + live freeze; return ``demo`` or ``live``. Never fail-open."""
    env_map: Mapping[str, str] = os.environ if environ is None else environ
    env = _assert_environment_allowed(
        "ctrader",
        environment,
        environ=env_map,
        enablement_path=enablement_path,
    )
    if env == "demo":
        return "demo"
    if env == "live":
        return "live"
    raise LiveExecutionDenied(f"ctrader_host_unmapped:{env}")
