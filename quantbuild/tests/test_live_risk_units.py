"""Regression tests for live risk unit conventions (position sizing + spread pips)."""
from unittest.mock import MagicMock

from src.quantbuild.execution.live_runner import LiveRunner


def _minimal_cfg(symbol: str = "XAUUSD", max_spread_pips: float = 4.0):
    return {
        "symbol": symbol,
        "timeframes": ["15m", "1h"],
        "data": {"base_path": "data/market_cache"},
        "backtest": {"tp_r": 2.0, "sl_r": 1.0, "session_mode": "extended"},
        "risk": {"max_daily_loss_r": 3.0, "max_position_pct": 0.015, "paper_equity": 10000},
        "strategy": {},
        "regime": {},
        "regime_profiles": {},
        "execution_guards": {
            "max_spread_pips": max_spread_pips,
            "max_slippage_r": 0.15,
            "max_open_positions": 3,
        },
        "execution": {"check_interval_seconds": 60, "regime_update_seconds": 900},
        "news": {"enabled": False},
        "broker": {
            "provider": "oanda",
            "account_id": "",
            "token": "",
            "environment": "practice",
            "instrument": "XAU_USD",
        },
    }


class TestRiskPctToFraction:
    def test_schema_fraction_prod_value(self):
        assert LiveRunner._risk_pct_to_fraction(0.015) == 0.015

    def test_schema_default_fraction(self):
        assert LiveRunner._risk_pct_to_fraction(0.02) == 0.02

    def test_legacy_percent_unit(self):
        assert LiveRunner._risk_pct_to_fraction(1.0) == 0.01

    def test_boundary_schema_max_is_fraction(self):
        assert LiveRunner._risk_pct_to_fraction(0.1) == 0.1


class TestCalculateUnitsFractionConvention:
    def test_prod_fraction_sizes_1_5_percent(self):
        """strict_prod_v2 max_position_pct=0.015 must risk 1.5% equity, not 0.015%."""
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        # equity 10_000, risk 1.5% = $150, SL distance $10 → 15 units
        units = runner._calculate_units(entry=2000.0, sl=1990.0, risk_pct=0.015)
        assert units == 15

    def test_legacy_percent_still_sizes_1_percent(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        # equity 10_000, risk 1% = $100, SL distance $2 → 50 units
        units = runner._calculate_units(entry=2000.0, sl=1998.0, risk_pct=1.0)
        assert units == 50

    def test_old_divide_by_100_path_is_not_used_for_fractions(self):
        runner = LiveRunner(_minimal_cfg(), dry_run=True)
        buggy_units = round(10000 * (0.015 / 100.0) / 10.0)  # would clamp to 1
        fixed_units = runner._calculate_units(entry=2000.0, sl=1990.0, risk_pct=0.015)
        assert fixed_units == 15
        assert fixed_units != max(1, buggy_units)


class TestSpreadGuardPipConversion:
    def test_xau_wide_price_spread_blocked_against_pip_threshold(self):
        """Oanda returns ask-bid in price units; 0.30 on XAU = 30 pips > 4.0."""
        runner = LiveRunner(_minimal_cfg(symbol="XAUUSD", max_spread_pips=4.0), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.get_current_price.return_value = {
            "bid": 2300.00,
            "ask": 2300.30,
            "spread": 0.30,
        }
        issue = runner._check_spread_guard()
        assert issue is not None
        assert issue["code"] == "spread_block"
        assert issue["observed"] == 30.0
        assert issue["threshold"] == 4.0

    def test_xau_tight_price_spread_allowed(self):
        runner = LiveRunner(_minimal_cfg(symbol="XAUUSD", max_spread_pips=4.0), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.get_current_price.return_value = {
            "bid": 2300.00,
            "ask": 2300.03,
            "spread": 0.03,
        }
        assert runner._check_spread_guard() is None

    def test_eurusd_price_spread_converted_to_pips(self):
        runner = LiveRunner(_minimal_cfg(symbol="EURUSD", max_spread_pips=1.5), dry_run=False)
        runner.broker = MagicMock()
        # 2.0 pips in price units
        runner.broker.get_current_price.return_value = {
            "bid": 1.10000,
            "ask": 1.10020,
            "spread": 0.00020,
        }
        issue = runner._check_spread_guard()
        assert issue is not None
        assert issue["observed"] == 2.0
        assert issue["threshold"] == 1.5

    def test_try_current_spread_pips_converts_units(self):
        runner = LiveRunner(_minimal_cfg(symbol="XAUUSD"), dry_run=False)
        runner.broker = MagicMock()
        runner.broker.is_connected = True
        runner.broker.get_current_price.return_value = {"spread": 0.05}
        assert runner._try_current_spread_pips() == 5.0
