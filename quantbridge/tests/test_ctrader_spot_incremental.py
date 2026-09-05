"""cTrader ProtoOASpotEvent bid/ask are optional incremental ticks.

Spotware sends only the side that changed. Overwriting the cache with proto
defaults (0) halves the mid used as open-trade mark and can fire OrderManager
BE/partial/trail on a live SHORT.
"""
from __future__ import annotations

import pytest

from quantbridge.execution.clients.ctrader_openapi_client import (
    CTraderOpenApiClient,
    _from_price,
    _optional_spot_price,
    _quote_sides_valid,
)

XAUUSD_BID_RAW = 265000000  # 2650.00
XAUUSD_ASK_RAW = 265050000  # 2650.50
SYMBOL_ID = 42


class ProtoOASpotEvent:
    def __init__(self, symbol_id: int, bid=None, ask=None):
        self.symbolId = symbol_id
        self._bid = bid
        self._ask = ask

    @property
    def bid(self):
        return 0 if self._bid is None else self._bid

    @property
    def ask(self):
        return 0 if self._ask is None else self._ask

    def HasField(self, name: str) -> bool:
        if name == "bid":
            return self._bid is not None
        if name == "ask":
            return self._ask is not None
        return False


def _client() -> CTraderOpenApiClient:
    c = CTraderOpenApiClient(account_id="1", access_token="token")
    c._symbol_id_by_name["XAUUSD"] = SYMBOL_ID
    c._symbol_name_by_id[SYMBOL_ID] = "XAUUSD"
    c.connected = True
    return c


def test_from_price_gold_relative_units():
    assert _from_price(XAUUSD_BID_RAW) == pytest.approx(2650.0)
    assert _from_price(0) == 0.0


def test_optional_spot_price_unset_is_none():
    evt = ProtoOASpotEvent(SYMBOL_ID, bid=XAUUSD_BID_RAW, ask=None)
    assert _optional_spot_price(evt, "bid") == pytest.approx(2650.0)
    assert _optional_spot_price(evt, "ask") is None


def test_optional_spot_price_zero_raw_is_none():
    evt = ProtoOASpotEvent(SYMBOL_ID, bid=0, ask=XAUUSD_ASK_RAW)
    assert _optional_spot_price(evt, "bid") is None


def test_optional_spot_price_without_hasfield_treats_zero_as_missing():
    class _BareSpot:
        symbolId = SYMBOL_ID
        bid = 0
        ask = XAUUSD_ASK_RAW

    assert _optional_spot_price(_BareSpot(), "bid") is None
    assert _optional_spot_price(_BareSpot(), "ask") == pytest.approx(2650.50)


def test_incremental_bid_only_preserves_ask():
    client = _client()
    client._on_message(
        ProtoOASpotEvent(SYMBOL_ID, bid=XAUUSD_BID_RAW, ask=XAUUSD_ASK_RAW)
    )
    client._on_message(ProtoOASpotEvent(SYMBOL_ID, bid=265100000, ask=None))

    spot = client._spot_by_symbol_id[SYMBOL_ID]
    assert spot["bid"] == pytest.approx(2651.0)
    assert spot["ask"] == pytest.approx(2650.50)
    quote = client.get_current_price("XAUUSD")
    assert quote is not None
    assert quote["bid"] == pytest.approx(2651.0)
    assert quote["ask"] == pytest.approx(2650.50)


def test_incremental_ask_only_preserves_bid():
    client = _client()
    client._on_message(
        ProtoOASpotEvent(SYMBOL_ID, bid=XAUUSD_BID_RAW, ask=XAUUSD_ASK_RAW)
    )
    client._on_message(ProtoOASpotEvent(SYMBOL_ID, bid=None, ask=265200000))

    spot = client._spot_by_symbol_id[SYMBOL_ID]
    assert spot["bid"] == pytest.approx(2650.0)
    assert spot["ask"] == pytest.approx(2652.0)


def test_one_sided_first_tick_does_not_publish():
    client = _client()
    client._on_message(ProtoOASpotEvent(SYMBOL_ID, bid=XAUUSD_BID_RAW, ask=None))
    assert SYMBOL_ID not in client._spot_by_symbol_id
    assert client.get_current_price("XAUUSD") is None


def test_legacy_overwrite_would_halve_mid():
    """Document the pre-fix failure: bid-only tick with ask defaulted to 0."""
    bid = _from_price(XAUUSD_BID_RAW)
    ask = _from_price(0)
    mid = (ask + bid) / 2.0
    assert mid == pytest.approx(1325.0)
    assert not _quote_sides_valid({"bid": bid, "ask": ask})


def test_missing_quote_uses_entry_not_half_price_as_mark():
    entry = _from_price(XAUUSD_BID_RAW)
    px = None
    mid = (float(px["ask"]) + float(px["bid"])) / 2.0 if _quote_sides_valid(px) else 0.0
    current = mid or entry
    assert current == pytest.approx(2650.0)
    assert current != pytest.approx(1325.0)


def test_bid_only_after_full_quote_mid_is_not_halved():
    client = _client()
    client._on_message(
        ProtoOASpotEvent(SYMBOL_ID, bid=XAUUSD_BID_RAW, ask=XAUUSD_ASK_RAW)
    )
    client._on_message(ProtoOASpotEvent(SYMBOL_ID, bid=265100000, ask=None))
    quote = client.get_current_price("XAUUSD")
    assert quote is not None
    mid = (quote["ask"] + quote["bid"]) / 2.0
    assert mid == pytest.approx((2651.0 + 2650.50) / 2.0)
    assert mid > 2600.0
