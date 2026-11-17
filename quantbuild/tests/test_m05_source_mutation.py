"""M0.5 SOURCE_MUTATION probes — restore future leak must fail (#127 Slice A).

Protocol: scratch copy + PYTHONPATH + ``__file__`` check (not monkeypatch).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mirror_qb(scratch: Path) -> Path:
    dst = scratch / "quantbuild" / "src" / "quantbuild"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "quantbuild" / "src" / "quantbuild", dst)
    return scratch / "quantbuild"


def _pythonpath(qb_root: Path) -> str:
    # ``import src.quantbuild`` requires the quantbuild repo root (parent of ``src/``).
    return str(qb_root)


def _run(code: str, *, pythonpath: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    # Prepend scratch; drop empty entries.
    env["PYTHONPATH"] = pythonpath
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_killed(proc: subprocess.CompletedProcess[str], label: str) -> None:
    assert "MUTATION_KILLED" in proc.stdout, (
        f"{label} SURVIVED or probe error\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


MUTANTS = {
    "structure_context": (
        "src/quantbuild/strategy_modules/ict/structure_context.py",
        # Restore centered rolling pivots (legacy leak).
        '''
"""mutant structure_context"""
from typing import Dict
import numpy as np
import pandas as pd
from src.quantbuild.strategy_modules.ict.structure_labels import (
    BULLISH_STRUCTURE, BEARISH_STRUCTURE, RANGE,
)

def compute_structure_labels(data, lookback=30, pivot_bars=2):
    n = len(data)
    high_roll = data["high"].rolling(2 * pivot_bars + 1, center=True, min_periods=pivot_bars + 1).max()
    low_roll = data["low"].rolling(2 * pivot_bars + 1, center=True, min_periods=pivot_bars + 1).min()
    is_pivot_high = ((data["high"] == high_roll) & high_roll.notna()).values
    is_pivot_low = ((data["low"] == low_roll) & low_roll.notna()).values
    high_arr = data["high"].values.astype(np.float64)
    low_arr = data["low"].values.astype(np.float64)
    out_arr = np.full(n, 0, dtype=np.int8)
    for i in range(lookback, n):
        start = max(0, i - lookback)
        ph_vals = high_arr[start:i + 1][is_pivot_high[start:i + 1]]
        pl_vals = low_arr[start:i + 1][is_pivot_low[start:i + 1]]
        if len(ph_vals) < 2 or len(pl_vals) < 2:
            continue
        sh2, sh1 = ph_vals[-1], ph_vals[-2]
        sl2, sl1 = pl_vals[-1], pl_vals[-2]
        if sh2 > sh1 and sl2 > sl1:
            out_arr[i] = 1
        elif sh2 < sh1 and sl2 < sl1:
            out_arr[i] = -1
    label_map = {0: RANGE, 1: BULLISH_STRUCTURE, -1: BEARISH_STRUCTURE}
    return pd.Series([label_map[v] for v in out_arr], index=data.index, dtype=object)

def add_structure_context(df, config, inplace=False):
    lookback = config.get("lookback", 30)
    pivot_bars = config.get("pivot_bars", 2)
    if not inplace:
        df = df.copy()
    df["structure_label"] = compute_structure_labels(df, lookback=lookback, pivot_bars=pivot_bars)
    df["in_bullish_structure"] = df["structure_label"] == BULLISH_STRUCTURE
    df["in_bearish_structure"] = df["structure_label"] == BEARISH_STRUCTURE
    return df
''',
        "src.quantbuild.strategy_modules.ict" + ".structure_context",
        "structure_label",
    ),
}


def _probe_truncation(module_import: str, runner_code: str) -> str:
    return textwrap.dedent(
        f"""
        import importlib
        import numpy as np
        import pandas as pd
        m = importlib.import_module({module_import!r})
        print("FILE", m.__file__)
        assert "scratch" in m.__file__.replace("\\\\", "/") or "/tmp/" in m.__file__.replace("\\\\", "/") or "pytest-of" in m.__file__.replace("\\\\", "/")
        {runner_code}
        """
    )


def test_mutation_swing_center_true_killed(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/indicators/swing.py"
    text = target.read_text(encoding="utf-8")
    # Inject centered leak into pivot_highs
    leak = '''
def pivot_highs(data, pivot_bars=2):
    import pandas as pd
    window = 2 * pivot_bars + 1
    high_roll = data["high"].rolling(window, center=True, min_periods=pivot_bars + 1).max()
    return (data["high"] == high_roll) & high_roll.notna()
'''
    # Replace function body start marker
    start = text.index("def pivot_highs(")
    end = text.index("def pivot_lows(")
    target.write_text(text[:start] + leak + "\n\n" + text[end:], encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.indicators.swing as m
        print("FILE", m.__file__)
        assert "scratch" in m.__file__ or "pytest" in m.__file__
        import numpy as np, pandas as pd
        from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches, _ind_frame
        idx = pd.date_range("2024-01-01", periods=40, freq="15min", tz="UTC")
        rng = np.random.RandomState(0)
        close = 100 + np.cumsum(rng.randn(40))
        df = pd.DataFrame({
            "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1
        }, index=idx)
        unit = FeatureUnit(
            "mut.pivot",
            "indicators/swing.py",
            ("pivot_high",),
            lambda d: _ind_frame({"pivot_high": m.pivot_highs(d, 2)}, d.index),
            requires_positive_event=False,
        )
        errs = truncation_mismatches(unit, df)
        if errs:
            print("MUTATION_KILLED")
            print("FAIL_IDS", "truncation_mismatches")
        else:
            print("MUTATION_UNDETECTED")
        """
    )
    proc = _run(code, pythonpath=_pythonpath(qb))
    _assert_killed(proc, "swing_pivots")


def test_mutation_fvg_middle_backwrite_killed(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/fair_value_gaps.py"
    src = target.read_text(encoding="utf-8")
    # Force legacy middle-bar assignment if present pattern; else rewrite calculate loop end
    mutant = src.replace(
        "bullish_fvg[t] = True",
        "bullish_fvg[t - 1] = True  # MUTANT back-write to middle",
    ).replace(
        "bearish_fvg[t] = True",
        "bearish_fvg[t - 1] = True",
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.fair_value_gaps as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_fvg_bullish
        df = fixture_fvg_bullish()
        out = m.FairValueGapModule().calculate(df, {"min_gap_pct": 0.5, "validity_candles": 50})
        # Causal rule: confirmation on third candle index 2; mutant writes index 1
        if bool(out["bullish_fvg"].iloc[1]) and not bool(out["bullish_fvg"].iloc[2]):
            print("MUTATION_KILLED")
            print("FAIL_IDS", "test_fvg_confirms_on_third_candle_not_earlier_not_later")
        else:
            # Also kill via truncation
            from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches
            unit = FeatureUnit(
                "mut.fvg",
                "strategy_modules/ict/fair_value_gaps.py",
                ("bullish_fvg", "bearish_fvg", "in_bullish_fvg", "in_bearish_fvg",
                 "bullish_fvg_quality", "bearish_fvg_quality"),
                lambda d: m.FairValueGapModule().calculate(d, {"min_gap_pct": 0.5, "validity_candles": 50}),
            )
            errs = truncation_mismatches(unit, df)
            print("MUTATION_KILLED" if errs else "MUTATION_UNDETECTED")
            print("FAIL_IDS", "truncation_mismatches" if errs else "none")
        """
    )
    proc = _run(code, pythonpath=_pythonpath(qb))
    _assert_killed(proc, "fvg")


def test_mutation_sweep_origin_flag_killed(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/liquidity_sweep.py"
    text = target.read_text(encoding="utf-8")
    mutant = text.replace("bullish_sweep[j] = True", "bullish_sweep[i] = True  # MUTANT origin").replace(
        "bearish_sweep[j] = True", "bearish_sweep[i] = True"
    ).replace("swept_low[j] = sl_val", "swept_low[i] = sl_val").replace(
        "swept_high[j] = sh", "swept_high[i] = sh"
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.liquidity_sweep as m
        print("FILE", m.__file__)
        import numpy as np, pandas as pd
        n = 20
        idx = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
        high = np.full(n, 101.0); low = np.full(n, 99.0); close = np.full(n, 100.0); opn = np.full(n, 100.0)
        for i in range(0, 8):
            low[i] = 98.0; high[i] = 100.0
        for i in range(8, 11):
            low[i] = 99.0; high[i] = 100.5
        low[11] = 97.0; high[11] = 97.8; close[11] = 97.5
        low[12] = 97.5; high[12] = 100.0; close[12] = 99.5
        df = pd.DataFrame({"open": opn, "high": high, "low": low, "close": close, "volume": 1}, index=idx)
        cfg = {"lookback_candles": 5, "sweep_threshold_pct": 0.2, "reversal_candles": 3}
        out = m.LiquiditySweepModule().calculate(df, cfg)
        # Causal: reversal-only bar 12; mutant flags sweep origin 11.
        if bool(out["bullish_sweep"].iloc[11]):
            print("MUTATION_KILLED")
            print("FAIL_IDS", "test_sweep_flags_reversal_bar_not_sweep_origin")
        else:
            print("MUTATION_UNDETECTED", out["bullish_sweep"].tolist())
        """
    )
    proc = _run(code, pythonpath=_pythonpath(qb))
    _assert_killed(proc, "sweep")


def test_mutation_ob_origin_flag_killed(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/order_blocks.py"
    text = target.read_text(encoding="utf-8")
    mutant = text.replace("bearish_ob[conf] = True", "bearish_ob[i] = True  # MUTANT").replace(
        "bullish_ob[conf] = True", "bullish_ob[i] = True  # MUTANT"
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.order_blocks as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_ob_bullish
        df = fixture_ob_bullish()
        out = m.OrderBlockModule().calculate(df, {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 20})
        if bool(out["bullish_ob"].iloc[3]) and not bool(out["bullish_ob"].iloc[6]):
            print("MUTATION_KILLED")
            print("FAIL_IDS", "test_ob_confirms_when_forward_extrema_known")
        else:
            print("MUTATION_UNDETECTED", out["bullish_ob"].tolist())
        """
    )
    proc = _run(code, pythonpath=_pythonpath(qb))
    _assert_killed(proc, "ob")


def test_mutation_mss_center_true_killed(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/market_structure_shift.py"
    target.write_text(
        textwrap.dedent(
            '''
            """MUTANT centered MSS"""
            import pandas as pd
            from typing import Dict
            from src.quantbuild.strategy_modules.base import BaseModule

            class MarketStructureShiftModule(BaseModule):
                @property
                def name(self):
                    return "MSS"
                @property
                def description(self):
                    return "mutant"
                def get_config_schema(self):
                    return {"fields": []}
                def calculate(self, data, config):
                    df = data.copy()
                    lb = config.get("swing_lookback", 5)
                    thresh = config.get("break_threshold_pct", 0.2) / 100.0
                    df["swing_high"] = df["high"].rolling(2 * lb + 1, center=True).max()
                    df["swing_low"] = df["low"].rolling(2 * lb + 1, center=True).min()
                    df["bullish_mss"] = (df["high"] >= df["swing_high"].shift(1) * (1 + thresh)) & (df["swing_high"].shift(1).notna())
                    df["bearish_mss"] = (df["low"] <= df["swing_low"].shift(1) * (1 - thresh)) & (df["swing_low"].shift(1).notna())
                    return df
                def check_entry_condition(self, data, index, config, direction):
                    return False
            '''
        ),
        encoding="utf-8",
    )
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.market_structure_shift as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches
        import numpy as np, pandas as pd
        idx = pd.date_range("2024-01-01", periods=60, freq="15min", tz="UTC")
        rng = np.random.RandomState(1)
        close = 100 + np.cumsum(rng.randn(60))
        df = pd.DataFrame({
            "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1
        }, index=idx)
        unit = FeatureUnit(
            "mut.mss",
            "strategy_modules/ict/market_structure_shift.py",
            ("swing_high", "swing_low", "bullish_mss", "bearish_mss"),
            lambda d: m.MarketStructureShiftModule().calculate(d, {"swing_lookback": 5, "break_threshold_pct": 0.2}),
        )
        errs = truncation_mismatches(unit, df)
        print("MUTATION_KILLED" if errs else "MUTATION_UNDETECTED")
        print("FAIL_IDS", "truncation_mismatches")
        """
    )
    proc = _run(code, pythonpath=_pythonpath(qb))
    _assert_killed(proc, "mss")


def test_mutation_structure_context_center_killed(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/structure_context.py"
    target.write_text(MUTANTS["structure_context"][1], encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.structure_context as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches
        import numpy as np, pandas as pd
        idx = pd.date_range("2024-01-01", periods=80, freq="15min", tz="UTC")
        rng = np.random.RandomState(2)
        close = 100 + np.cumsum(rng.randn(80))
        df = pd.DataFrame({
            "open": close, "high": close + 1.5, "low": close - 1.5, "close": close, "volume": 1
        }, index=idx)
        unit = FeatureUnit(
            "mut.struct",
            "strategy_modules/ict/structure_context.py",
            ("structure_label", "in_bullish_structure", "in_bearish_structure"),
            lambda d: m.add_structure_context(d, {"lookback": 30, "pivot_bars": 2}),
        )
        errs = truncation_mismatches(unit, df)
        print("MUTATION_KILLED" if errs else "MUTATION_UNDETECTED")
        print("FAIL_IDS", "truncation_mismatches")
        """
    )
    proc = _run(code, pythonpath=_pythonpath(qb))
    _assert_killed(proc, "structure_context")
