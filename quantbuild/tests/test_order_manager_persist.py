"""OrderManager must persist BE / partial / trail flags after update_price.

Without this, a SIGTERM restart (systemd Restart=always, launch_live_safe
max-runtime) reloads register-time state and re-fires the 50% partial,
flattening the runner.
"""
from unittest.mock import MagicMock

import src.quantbuild.execution.order_manager as om_mod
from src.quantbuild.execution.order_manager import OrderManager


def _om(tmp_path, monkeypatch, broker=None, config=None) -> OrderManager:
    monkeypatch.setattr(om_mod, "STATE_FILE", tmp_path / "state.json")
    return OrderManager(broker=broker, config=config)


def _register(om: OrderManager, *, direction="LONG", units=100.0) -> None:
    om.register_trade(
        trade_id="T1",
        instrument="XAUUSD",
        direction=direction,
        entry_price=2000.0,
        units=units,
        sl=1990.0 if direction == "LONG" else 2010.0,
        tp=2020.0 if direction == "LONG" else 1980.0,
        atr=10.0,
        regime="trend",
    )


class TestPartialClosePersistsAcrossRestart:
    def test_partial_flag_and_units_survive_reload(self, tmp_path, monkeypatch):
        broker = MagicMock()
        broker.close_trade.return_value = True
        broker.modify_trade.return_value = True
        om = _om(tmp_path, monkeypatch, broker=broker)
        _register(om)

        # 1R LONG: BE + 50% partial fire on the same mark.
        om.update_price("T1", 2010.0)
        assert broker.close_trade.call_count == 1
        assert om.managed_orders["T1"].partial_closed is True
        assert om.managed_orders["T1"].units == 50.0
        assert om.managed_orders["T1"].break_even_set is True

        restarted = _om(tmp_path, monkeypatch, broker=broker)
        loaded = restarted.load_state()
        assert loaded == 1
        restored = restarted.managed_orders["T1"]
        assert restored.partial_closed is True
        assert restored.units == 50.0
        assert restored.break_even_set is True

        restarted.update_price("T1", 2010.0)
        assert broker.close_trade.call_count == 1


class TestTrailPersistsAcrossRestart:
    def test_trailing_active_not_rewound_on_reload(self, tmp_path, monkeypatch):
        broker = MagicMock()
        broker.close_trade.return_value = True
        broker.modify_trade.return_value = True
        cfg = {
            "break_even": {"enabled": True, "trigger_r": 1.0, "offset_pips": 2},
            "partial_close": {"enabled": False},
            "trailing_stop": {"enabled": True, "activation_r": 1.5, "trail_distance_r": 1.0},
        }
        om = _om(tmp_path, monkeypatch, broker=broker, config=cfg)
        _register(om)
        om.update_price("T1", 2015.0)
        assert om.managed_orders["T1"].trailing_active is True
        sl_after_trail = om.managed_orders["T1"].current_sl

        restarted = _om(tmp_path, monkeypatch, broker=broker, config=cfg)
        restarted.load_state()
        restored = restarted.managed_orders["T1"]
        assert restored.trailing_active is True
        assert restored.current_sl == sl_after_trail
        assert restored.peak_price == 2015.0
