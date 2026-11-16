"""Canonical fail-closed live execution gate (issue #104 PR-A).

Process environment is the only trusted source for gate keys after env-file
hygiene checks. Dotenv / bridge local.env / orchestrator .env must not mint
authorization. Environment ``live`` stays frozen until an owner-only enablement
file outside the repo exists.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, Optional, Sequence

GATE_ENV_KEYS: tuple[str, ...] = (
    "QUANTMETRICS_EXECUTION_AUTHORIZED",
    "QUANTMETRICS_ALLOWED_ACCOUNT_IDS",
    "QUANTMETRICS_ALLOWED_BROKER_ENVIRONMENTS",
)

# Owner-only live-host enablement (outside all repo checkouts). Presence of a
# regular file is required before environment "live" may pass allowlist checks.
# File format is intentionally unspecified in PR-A; absence => live denied (C3).
DEFAULT_LIVE_ENABLEMENT_PATH = Path("/etc/quantmetrics/execution_authorization")

_GATE_KEY_LINE = re.compile(
    r"^\s*(" + "|".join(re.escape(k) for k in GATE_ENV_KEYS) + r")\s*=",
    re.MULTILINE,
)


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
    # live_execution_gate.py → safety → quantbridge → src → repo root
    return Path(__file__).resolve().parents[3]


def default_bridge_env_files(*, root: Optional[Path] = None) -> list[Path]:
    base = root if root is not None else bridge_repo_root()
    return [base / "local.env", base / ".env"]


def env_file_contains_gate_keys(path: Path | str) -> bool:
    """Return True if file text declares any frozen gate key assignment."""
    p = Path(path)
    if not p.is_file():
        return False
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise LiveExecutionDenied(f"gate_env_file_unreadable:{p}:{exc}") from exc
    return _GATE_KEY_LINE.search(text) is not None


def assert_dotenv_path_has_no_gate_keys(path: Path | str) -> None:
    """Fail closed if the exact dotenv path contains any gate key (C2 / P1)."""
    p = Path(path)
    if env_file_contains_gate_keys(p):
        raise LiveExecutionDenied(f"gate_key_present_in_dotenv:{p.resolve()}")


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
    # Explicit empty => deny all
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
    allowed = _allowed_environments(provider, environ)
    if env not in allowed:
        raise LiveExecutionDenied(f"environment_not_allowlisted:{env}")
    # Live-host freeze (P1 / C3): deny live unless owner-only file exists.
    if env == "live" and not live_host_enablement_satisfied(enablement_path=enablement_path):
        raise LiveExecutionDenied("live_host_enablement_frozen")
    # cTrader must not use Oanda-style "practice"
    if provider.strip().lower() == "ctrader" and env == "practice":
        raise LiveExecutionDenied("ctrader_practice_environment_rejected")
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
