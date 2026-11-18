"""DATA-002 I3 — fail-closed research source / instrument policy.

Research must never accept GC=F / yfinance as XAUUSD spot, must not auto-fallback
to yfinance after Dukascopy/cTrader denial, and must DENY unknown/mixed origins.

This module is intentionally independent of I2 sidecar code (PR #137 MERGE HOLD).
I2 will later persist ``source`` / ``instrument`` / ``single_source`` on disk;
I3 gates the *fetch/write* path so those bytes cannot be produced for spot XAUUSD.
See ``docs/plans/ISSUE_133_DATA002_I3_INTEGRATION.md``.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

# Spot gold research identity — never confuse with COMEX futures.
SPOT_XAUUSD = "XAUUSD"
INSTRUMENT_SPOT_XAUUSD = "spot_xauusd"
INSTRUMENT_GC_F_FUTURES = "gc_f_futures"

# Research auto: spot-safe venues only. yfinance is NEVER in this list.
RESEARCH_AUTO_ORDER: tuple[str, ...] = ("ctrader", "dukascopy")

RESEARCH_EXPLICIT_PROVIDERS = frozenset({"ctrader", "dukascopy", "yfinance"})

FORBIDDEN_SPOT_XAUUSD_SOURCES = frozenset({"yfinance"})
FORBIDDEN_SPOT_XAUUSD_INSTRUMENTS = frozenset(
    {
        INSTRUMENT_GC_F_FUTURES,
        "gc=f",
        "GC=F",
        "gcf",
        "comex_gold_futures",
    }
)
FORBIDDEN_SPOT_XAUUSD_TICKERS = frozenset({"GC=F", "gc=f"})


class ResearchSourcePolicyError(ValueError):
    """Fail-closed research source / instrument DENY (no cache mutation expected)."""


def is_spot_xauusd(symbol: str) -> bool:
    return str(symbol or "").upper() == SPOT_XAUUSD


def normalize_source_name(source: Any) -> str:
    return str(source or "").strip().lower()


def yfinance_ticker_for_symbol(symbol: str) -> str:
    """Historical yfinance ticker mapping (documentation / mutant probes).

    Must never be used to accept/write XAUUSD spot research data.
    """
    if is_spot_xauusd(symbol):
        return "GC=F"
    return f"{str(symbol).upper()}=X"


def instrument_for_research_source(symbol: str, source: str) -> str:
    """Declared instrument identity for a research write intent."""
    src = normalize_source_name(source)
    if is_spot_xauusd(symbol):
        if src == "yfinance":
            return INSTRUMENT_GC_F_FUTURES
        return INSTRUMENT_SPOT_XAUUSD
    if src == "yfinance":
        return f"yfinance_{str(symbol).lower()}"
    return f"{src}_{str(symbol).lower()}"


def assert_spot_xauusd_instrument_allowed(
    symbol: str,
    *,
    source: Optional[str] = None,
    instrument: Optional[str] = None,
    ticker: Optional[str] = None,
) -> None:
    """DENY GC=F / futures identity as XAUUSD spot research."""
    if not is_spot_xauusd(symbol):
        return
    src = normalize_source_name(source) if source is not None else ""
    if src in FORBIDDEN_SPOT_XAUUSD_SOURCES:
        raise ResearchSourcePolicyError(
            "research DENY: yfinance/GC=F is never accepted as XAUUSD spot "
            f"(requested_source={src})"
        )
    if instrument is not None:
        inst = str(instrument).strip()
        if inst.lower() in {x.lower() for x in FORBIDDEN_SPOT_XAUUSD_INSTRUMENTS}:
            raise ResearchSourcePolicyError(
                "research DENY: instrument incompatible with spot XAUUSD "
                f"(instrument={inst})"
            )
    if ticker is not None and str(ticker).strip() in FORBIDDEN_SPOT_XAUUSD_TICKERS:
        raise ResearchSourcePolicyError(
            f"research DENY: ticker {ticker!r} is not XAUUSD spot"
        )


def assert_research_provenance_claim(
    symbol: str,
    claim: Mapping[str, Any],
) -> None:
    """DENY unknown/mixed or GC=F provenance claims for research acceptance."""
    source = claim.get("source")
    single_source = claim.get("single_source", True)
    instrument = claim.get("instrument")

    if source is None or normalize_source_name(source) in {"", "unknown", "mixed"}:
        raise ResearchSourcePolicyError(
            "research DENY: unknown/mixed research source"
        )
    if single_source is not True:
        raise ResearchSourcePolicyError(
            "research DENY: single_source must be true (mixed origin)"
        )
    assert_spot_xauusd_instrument_allowed(
        symbol, source=str(source), instrument=instrument
    )


def resolve_research_source_order(
    source: str,
    *,
    symbol: str,
) -> tuple[str, list[str]]:
    """Resolve research provider order or DENY.

    Rules:
    - ``auto`` → ctrader, dukascopy only (never yfinance / GC=F fallback)
    - explicit ctrader/dukascopy → that provider only
    - explicit yfinance + XAUUSD → DENY
    - explicit yfinance + other symbol → yfinance only (FX path; not spot gold)
    - unknown / empty → DENY (no silent auto-with-yfinance)
    """
    source_name = normalize_source_name(source) or "auto"

    if source_name == "auto":
        return source_name, list(RESEARCH_AUTO_ORDER)

    if source_name not in RESEARCH_EXPLICIT_PROVIDERS:
        raise ResearchSourcePolicyError(
            f"research DENY: unknown research source '{source_name}' "
            "(no silent auto fallback)"
        )

    if source_name == "yfinance":
        assert_spot_xauusd_instrument_allowed(symbol, source="yfinance")
        # Non-spot symbols may still request yfinance explicitly.
        return source_name, ["yfinance"]

    return source_name, [source_name]


def research_auto_includes_yfinance(order: Sequence[str]) -> bool:
    """Mutant probe helper: auto order must never include yfinance."""
    return "yfinance" in {normalize_source_name(x) for x in order}
