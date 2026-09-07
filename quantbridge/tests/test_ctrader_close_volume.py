"""cTrader close must send required ProtoOAClosePositionReq.volume (cents)."""
from types import SimpleNamespace

from quantbridge.execution.clients.ctrader_openapi_client import _close_volume_cents


def test_explicit_positive_units_used_as_volume():
    assert _close_volume_cents(100, [], "1") == 100
    assert _close_volume_cents(100.9, [], "1") == 100


def test_zero_or_negative_units_rejected():
    assert _close_volume_cents(0, [], "1") is None
    assert _close_volume_cents(-5, [], "1") is None


def test_missing_units_uses_open_trade_volume():
    trades = [SimpleNamespace(trade_id="42", units=250.0)]
    assert _close_volume_cents(None, trades, "42") == 250
    assert _close_volume_cents(None, trades, 42) == 250


def test_missing_units_without_matching_trade_is_none():
    trades = [SimpleNamespace(trade_id="99", units=250.0)]
    assert _close_volume_cents(None, trades, "42") is None
    assert _close_volume_cents(None, [], "42") is None


def test_matching_trade_with_zero_units_is_none():
    trades = [SimpleNamespace(trade_id="42", units=0)]
    assert _close_volume_cents(None, trades, "42") is None


def test_openapi_close_without_volume_does_not_send():
    from quantbridge.execution.clients.ctrader_openapi_client import CTraderOpenApiClient

    client = CTraderOpenApiClient(account_id="1", access_token="token")
    client.connected = True
    client.get_open_trades = lambda instrument=None: []
    sent = []
    client._send_message = lambda msg: sent.append(msg)

    assert client.close_trade("42") is False
    assert sent == []
    assert "missing_close_volume" in (client.last_error or "")
