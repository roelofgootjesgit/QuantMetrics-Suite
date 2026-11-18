"""DATA-002 I3 (#133): fail-closed research source/instrument policy.

Offline only — no network. Mutants must not allow GC=F/yfinance as XAUUSD spot
or silent auto-fallback after Dukascopy/cTrader denial.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

from src.quantbuild.io import parquet_loader
from src.quantbuild.io.research_source_policy import (
    RESEARCH_AUTO_ORDER,
    ResearchSourcePolicyError,
    assert_research_provenance_claim,
    assert_spot_xauusd_instrument_allowed,
    research_auto_includes_yfinance,
    resolve_research_source_order,
    yfinance_ticker_for_symbol,
)


def _ohlcv(n: int = 3, *, end: str | None = None) -> pd.DataFrame:
    # Default near "now" so ensure_data period_days window still sees rows.
    from datetime import datetime, timedelta, timezone

    last = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        if end is None
        else pd.Timestamp(end).to_pydatetime()
    )
    idx = pd.date_range(last - timedelta(hours=n - 1), periods=n, freq="h")
    return pd.DataFrame(
        {
            "open": [1.0 + i for i in range(n)],
            "high": [1.5 + i for i in range(n)],
            "low": [0.5 + i for i in range(n)],
            "close": [1.2 + i for i in range(n)],
            "volume": [10.0 + i for i in range(n)],
        },
        index=idx,
    )


def _inventory(root: Path) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return out


def test_research_auto_order_excludes_yfinance_mutant() -> None:
    """Source mutant: auto must never include yfinance."""
    assert "yfinance" not in RESEARCH_AUTO_ORDER
    assert research_auto_includes_yfinance(RESEARCH_AUTO_ORDER) is False
    requested, order = resolve_research_source_order("auto", symbol="XAUUSD")
    assert requested == "auto"
    assert order == ["ctrader", "dukascopy"]
    assert "yfinance" not in order

    src = inspect.getsource(parquet_loader._resolve_source_order)
    assert "resolve_research_source_order" in src
    # Kill pre-I3 mutant that hard-coded yfinance into auto.
    auto_src = inspect.getsource(resolve_research_source_order)
    assert '["ctrader", "dukascopy", "yfinance"]' not in auto_src
    assert "RESEARCH_AUTO_ORDER" in auto_src


def test_explicit_yfinance_xauusd_deny() -> None:
    with pytest.raises(ResearchSourcePolicyError, match="never accepted|XAUUSD spot"):
        resolve_research_source_order("yfinance", symbol="XAUUSD")
    with pytest.raises(ResearchSourcePolicyError, match="never accepted|XAUUSD spot"):
        assert_spot_xauusd_instrument_allowed("XAUUSD", source="yfinance")
    with pytest.raises(ResearchSourcePolicyError, match="instrument incompatible"):
        assert_spot_xauusd_instrument_allowed(
            "XAUUSD", instrument="gc_f_futures"
        )


def test_unknown_research_source_deny_no_silent_auto() -> None:
    with pytest.raises(ResearchSourcePolicyError, match="unknown research source"):
        resolve_research_source_order("mystery_feed", symbol="XAUUSD")
    with pytest.raises(ResearchSourcePolicyError, match="unknown/mixed"):
        assert_research_provenance_claim(
            "XAUUSD", {"source": "unknown", "single_source": True}
        )
    with pytest.raises(ResearchSourcePolicyError, match="single_source"):
        assert_research_provenance_claim(
            "XAUUSD",
            {"source": "dukascopy", "single_source": False, "instrument": "spot_xauusd"},
        )


def test_fetch_yfinance_xauusd_denied_before_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutant: XAUUSD must not reach yfinance.download / GC=F mapping."""
    called = {"download": 0}

    class _FakeYf:
        @staticmethod
        def download(*_a, **_k):
            called["download"] += 1
            return _ohlcv(120)

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _FakeYf)
    with pytest.raises(ResearchSourcePolicyError, match="never accepted|XAUUSD spot"):
        parquet_loader._fetch_yfinance("XAUUSD", "15m", 60)
    assert called["download"] == 0

    # Mapping helper still documents historical GC=F ticker — must not be used for spot write.
    assert yfinance_ticker_for_symbol("XAUUSD") == "GC=F"
    src = inspect.getsource(parquet_loader._fetch_yfinance)
    assert "assert_spot_xauusd_instrument_allowed" in src


def test_ensure_data_auto_no_yfinance_fallback_after_dukascopy_deny(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After cTrader/Dukascopy fail, auto must not call yfinance; cache untouched."""
    base = tmp_path / "cache"
    symbol_dir = base / "XAUUSD"
    symbol_dir.mkdir(parents=True)
    pq = symbol_dir / "15m.parquet"
    _ohlcv(5).to_parquet(pq, compression="snappy")
    before = _inventory(base)

    yf_calls: list[str] = []

    def _deny_ctrader(*_a, **_k):
        return pd.DataFrame()

    def _deny_duka(*_a, **_k):
        return pd.DataFrame()

    def _trap_yf(symbol, *args, **kwargs):
        yf_calls.append(symbol)
        return _ohlcv(200)  # would "succeed" if called — must not be

    monkeypatch.setattr(parquet_loader, "_fetch_ctrader", _deny_ctrader)
    monkeypatch.setattr(parquet_loader, "_fetch_dukascopy", _deny_duka)
    monkeypatch.setattr(parquet_loader, "_fetch_yfinance", _trap_yf)

    out = parquet_loader.ensure_data(
        symbol="XAUUSD",
        timeframe="15m",
        base_path=base,
        period_days=60,
        source="auto",
    )
    assert yf_calls == []
    assert _inventory(base) == before
    # Sparse existing (<100) returned unchanged — no overwrite from GC=F.
    assert len(out) == 5


def test_ensure_data_explicit_yfinance_xauusd_deny_inventory_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "cache"
    symbol_dir = base / "XAUUSD"
    symbol_dir.mkdir(parents=True)
    pq = symbol_dir / "15m.parquet"
    _ohlcv(8).to_parquet(pq, compression="snappy")
    before = _inventory(base)

    def _trap_yf(*_a, **_k):
        raise AssertionError("yfinance must not run for spot XAUUSD")

    monkeypatch.setattr(parquet_loader, "_fetch_yfinance", _trap_yf)
    with pytest.raises(ResearchSourcePolicyError, match="never accepted|XAUUSD spot"):
        parquet_loader.ensure_data(
            symbol="XAUUSD",
            timeframe="15m",
            base_path=base,
            period_days=60,
            source="yfinance",
        )
    assert _inventory(base) == before


def test_ensure_data_unknown_source_deny_inventory_unchanged(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    (base / "XAUUSD").mkdir(parents=True)
    pq = base / "XAUUSD" / "15m.parquet"
    _ohlcv(6).to_parquet(pq, compression="snappy")
    before = _inventory(base)
    with pytest.raises(ResearchSourcePolicyError, match="unknown research source"):
        parquet_loader.ensure_data(
            symbol="XAUUSD",
            timeframe="15m",
            base_path=base,
            period_days=60,
            source="garbage",
        )
    assert _inventory(base) == before


def test_gc_f_cannot_be_saved_via_ensure_data_auto_mutant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even if a mutant re-adds yfinance to auto, spot policy on fetch must DENY write."""
    base = tmp_path / "cache"
    before = _inventory(base)

    monkeypatch.setattr(
        parquet_loader,
        "_resolve_source_order",
        lambda source, symbol="XAUUSD": ("auto", ["yfinance"]),
    )

    def _fake_yf(symbol, timeframe, period_days):
        # Simulate pre-I3 behaviour that would return GC=F bars.
        assert_spot_xauusd_instrument_allowed(symbol, source="yfinance")
        return _ohlcv(150)

    monkeypatch.setattr(parquet_loader, "_fetch_yfinance", _fake_yf)
    with pytest.raises(ResearchSourcePolicyError):
        parquet_loader.ensure_data(
            symbol="XAUUSD",
            timeframe="15m",
            base_path=base,
            period_days=60,
            source="auto",
        )
    assert _inventory(base) == before
    assert not (base / "XAUUSD" / "15m.parquet").exists()


def test_cmd_fetch_respects_yfinance_xauusd_deny(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    from src.quantbuild import app as qb_app

    monkeypatch.setattr(
        qb_app,
        "load_config",
        lambda _p: {"data": {"base_path": str(tmp_path / "cache")}, "symbol": "XAUUSD"},
    )
    monkeypatch.setattr(qb_app, "setup_logging", lambda *a, **k: None)
    args = SimpleNamespace(
        config="unused.yaml",
        command="fetch",
        symbol="XAUUSD",
        days=30,
        timeframe="15m",
        source="yfinance",
    )
    before = _inventory(tmp_path)
    rc = qb_app.cmd_fetch(args)
    assert rc == 2
    assert _inventory(tmp_path) == before


def test_i3_does_not_import_unmerged_i2_provenance_cache() -> None:
    """I3 must not depend on unmerged I2 sidecar module."""
    import src.quantbuild.io.research_source_policy as pol
    import src.quantbuild.io.parquet_loader as pl

    assert "provenance_cache" not in inspect.getsource(pol)
    # parquet_loader may gain I2 imports later; I3 change set must not require it now.
    assert "provenance_cache" not in inspect.getsource(pl)
