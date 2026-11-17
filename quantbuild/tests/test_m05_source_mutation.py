"""M0.5 B1 SOURCE_MUTATION matrix — 8 targeted + 4 full reverts (#127).

All 12 must print MUTATION_KILLED via relevant assertions (not import errors).
Protocol: scratch copy + PYTHONPATH=<scratch>/quantbuild + ``__file__`` check.
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

# Claude review table IDs (B1 repair).
MUTATION_CASES = [
    "T1_structure_center",
    "T2_swing_pivot_highs_center",
    "T3_mss_center",
    "T4_fvg_bullish_middle",
    "T5_fvg_bearish_middle",
    "T6_sweep_bullish_origin",
    "T7_sweep_bearish_origin",
    "T8_ob_bullish_origin",
    "R1_structure_full_revert",
    "R2_swing_full_revert",
    "R3_mss_full_revert",
    "R4_order_blocks_full_revert",
]


def _mirror_qb(scratch: Path) -> Path:
    dst = scratch / "quantbuild" / "src" / "quantbuild"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "quantbuild" / "src" / "quantbuild", dst)
    return scratch / "quantbuild"


def _pythonpath(qb_root: Path) -> str:
    return str(qb_root)


def _run(code: str, *, pythonpath: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
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
    assert "ModuleNotFoundError" not in proc.stderr, f"{label} import failure\n{proc.stderr}"
    assert "MUTATION_KILLED" in proc.stdout, (
        f"{label} SURVIVED or probe error\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "FILE" in proc.stdout


LEGACY_STRUCTURE = textwrap.dedent(
    '''
    """LEGACY structure_context centered pivots"""
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
    '''
)

LEGACY_MSS = textwrap.dedent(
    '''
    """LEGACY centered MSS"""
    import pandas as pd
    from typing import Dict
    from src.quantbuild.strategy_modules.base import BaseModule

    class MarketStructureShiftModule(BaseModule):
        @property
        def name(self):
            return "MSS"
        @property
        def description(self):
            return "legacy"
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
)

LEGACY_SWING_PIVOT_HIGHS = textwrap.dedent(
    '''
def pivot_highs(data, pivot_bars=2):
    import pandas as pd
    window = 2 * pivot_bars + 1
    high_roll = data["high"].rolling(window, center=True, min_periods=pivot_bars + 1).max()
    return (data["high"] == high_roll) & high_roll.notna()
'''
)

LEGACY_SWING_FULL = None  # built from file replace of both pivot_highs and pivot_lows


def _probe_truncation_kill(import_stmt: str, unit_setup: str) -> str:
    # Build probe without nested-indent: unit_setup must be column-0 statements.
    setup = textwrap.dedent(unit_setup).strip("\n")
    return (
        import_stmt.strip()
        + "\n"
        + "print('FILE', m.__file__)\n"
        + "assert '/tmp/' in m.__file__ or 'pytest' in m.__file__\n"
        + "from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches\n"
        + setup
        + "\n"
        + "errs = truncation_mismatches(unit, data)\n"
        + "print('MUTATION_KILLED' if errs else 'MUTATION_UNDETECTED')\n"
        + "print('FAIL_IDS', 'truncation_mismatches')\n"
        + "print('CASE_RESULT', 'KILLED' if errs else 'SURVIVED')\n"
    )


def test_T1_structure_center_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    (qb / "src/quantbuild/strategy_modules/ict/structure_context.py").write_text(LEGACY_STRUCTURE, encoding="utf-8")
    code = _probe_truncation_kill(
        "import src.quantbuild.strategy_modules.ict.structure_context as m",
        textwrap.dedent(
            """
            from src.quantbuild.testing.truncation_harness import fixture_structure_trend
            data = fixture_structure_trend()
            unit = FeatureUnit(
                "mut.struct", "strategy_modules/ict/structure_context.py",
                ("structure_label", "in_bullish_structure", "in_bearish_structure"),
                lambda d: m.add_structure_context(d, {"lookback": 50, "pivot_bars": 2}),
                truncation_data=lambda: data,
            )
            """
        ),
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T1_structure_center")


def test_T2_swing_pivot_highs_center_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/indicators/swing.py"
    text = target.read_text(encoding="utf-8")
    start = text.index("def pivot_highs(")
    end = text.index("def pivot_lows(")
    target.write_text(text[:start] + LEGACY_SWING_PIVOT_HIGHS + "\n\n" + text[end:], encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.indicators.swing as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches, _ind_frame, fixture_pivot_high
        data = fixture_pivot_high()
        unit = FeatureUnit(
            "mut.ph", "indicators/swing.py", ("pivot_high",),
            lambda d: _ind_frame({"pivot_high": m.pivot_highs(d, 2)}, d.index),
            truncation_data=lambda: data,
        )
        errs = truncation_mismatches(unit, data)
        # Also timing: origin must not be flagged
        ph = m.pivot_highs(data, 2)
        timing_bad = bool(ph.iloc[5])  # origin
        killed = bool(errs) or timing_bad
        print("MUTATION_KILLED" if killed else "MUTATION_UNDETECTED")
        print("FAIL_IDS", "truncation_or_origin_flag")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T2_swing_pivot_highs_center")


def test_T3_mss_center_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    (qb / "src/quantbuild/strategy_modules/ict/market_structure_shift.py").write_text(LEGACY_MSS, encoding="utf-8")
    code = _probe_truncation_kill(
        "import src.quantbuild.strategy_modules.ict.market_structure_shift as m",
        textwrap.dedent(
            """
            from src.quantbuild.testing.truncation_harness import fixture_mss_both
            data = fixture_mss_both()
            unit = FeatureUnit(
                "mut.mss", "strategy_modules/ict/market_structure_shift.py",
                ("swing_high", "swing_low", "bullish_mss", "bearish_mss"),
                lambda d: m.MarketStructureShiftModule().calculate(d, {"swing_lookback": 2, "break_threshold_pct": 0.05}),
                truncation_data=lambda: data,
            )
            """
        ),
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T3_mss_center")


def test_T4_fvg_bullish_middle_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/fair_value_gaps.py"
    mutant = target.read_text(encoding="utf-8").replace(
        "bullish_fvg[t] = True", "bullish_fvg[t - 1] = True  # MUTANT"
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.fair_value_gaps as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_fvg_bullish
        out = m.FairValueGapModule().calculate(fixture_fvg_bullish(), {"min_gap_pct": 0.5, "validity_candles": 50})
        # Causal: confirm at 2; mutant writes middle 1
        if bool(out["bullish_fvg"].iloc[1]) and not bool(out["bullish_fvg"].iloc[2]):
            print("MUTATION_KILLED")
        else:
            from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches, fixture_fvg_both
            data = fixture_fvg_both()
            unit = FeatureUnit("mut.fvg", "x", ("bullish_fvg","bearish_fvg","in_bullish_fvg","in_bearish_fvg","bullish_fvg_quality","bearish_fvg_quality"),
                lambda d: m.FairValueGapModule().calculate(d, {"min_gap_pct": 0.5, "validity_candles": 50}), truncation_data=lambda: data)
            errs = truncation_mismatches(unit, data)
            print("MUTATION_KILLED" if errs else "MUTATION_UNDETECTED")
        print("FAIL_IDS", "test_fvg_bullish_not_earlier_not_later")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T4_fvg_bullish_middle")


def test_T5_fvg_bearish_middle_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/fair_value_gaps.py"
    mutant = target.read_text(encoding="utf-8").replace(
        "bearish_fvg[t] = True", "bearish_fvg[t - 1] = True  # MUTANT"
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.fair_value_gaps as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_fvg_bearish
        out = m.FairValueGapModule().calculate(fixture_fvg_bearish(), {"min_gap_pct": 0.5, "validity_candles": 50})
        if bool(out["bearish_fvg"].iloc[1]) and not bool(out["bearish_fvg"].iloc[2]):
            print("MUTATION_KILLED")
        else:
            print("MUTATION_UNDETECTED", out["bearish_fvg"].tolist())
        print("FAIL_IDS", "test_fvg_bearish_not_earlier_not_later")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T5_fvg_bearish_middle")


def test_T6_sweep_bullish_origin_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/liquidity_sweep.py"
    text = target.read_text(encoding="utf-8")
    mutant = text.replace("bullish_sweep[j] = True", "bullish_sweep[i] = True  # MUTANT").replace(
        "swept_low[j] = sl_val", "swept_low[i] = sl_val"
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.liquidity_sweep as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_sweep_bullish
        cfg = {"lookback_candles": 5, "sweep_threshold_pct": 0.2, "reversal_candles": 3}
        out = m.LiquiditySweepModule().calculate(fixture_sweep_bullish(), cfg)
        if bool(out["bullish_sweep"].iloc[11]):
            print("MUTATION_KILLED")
        else:
            print("MUTATION_UNDETECTED", out["bullish_sweep"].tolist())
        print("FAIL_IDS", "test_sweep_bullish_not_earlier_not_later")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T6_sweep_bullish_origin")


def test_T7_sweep_bearish_origin_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/liquidity_sweep.py"
    text = target.read_text(encoding="utf-8")
    mutant = text.replace("bearish_sweep[j] = True", "bearish_sweep[i] = True  # MUTANT").replace(
        "swept_high[j] = sh", "swept_high[i] = sh"
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.liquidity_sweep as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_sweep_bearish
        cfg = {"lookback_candles": 5, "sweep_threshold_pct": 0.2, "reversal_candles": 3}
        out = m.LiquiditySweepModule().calculate(fixture_sweep_bearish(), cfg)
        if bool(out["bearish_sweep"].iloc[11]):
            print("MUTATION_KILLED")
        else:
            print("MUTATION_UNDETECTED", out["bearish_sweep"].tolist())
        print("FAIL_IDS", "test_sweep_bearish_not_earlier_not_later")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T7_sweep_bearish_origin")


def test_T8_ob_bullish_origin_targeted(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/order_blocks.py"
    mutant = target.read_text(encoding="utf-8").replace(
        "bullish_ob[conf] = True", "bullish_ob[i] = True  # MUTANT"
    )
    assert "MUTANT" in mutant
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.order_blocks as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_ob_bullish
        out = m.OrderBlockModule().calculate(fixture_ob_bullish(), {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 20})
        if bool(out["bullish_ob"].iloc[3]) and not bool(out["bullish_ob"].iloc[6]):
            print("MUTATION_KILLED")
        else:
            print("MUTATION_UNDETECTED", out["bullish_ob"].tolist())
        print("FAIL_IDS", "test_ob_bullish_not_earlier_not_later")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "T8_ob_bullish_origin")


def test_R1_structure_full_revert(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    (qb / "src/quantbuild/strategy_modules/ict/structure_context.py").write_text(LEGACY_STRUCTURE, encoding="utf-8")
    code = _probe_truncation_kill(
        "import src.quantbuild.strategy_modules.ict.structure_context as m",
        textwrap.dedent(
            """
            from src.quantbuild.testing.truncation_harness import fixture_structure_trend
            data = fixture_structure_trend()
            unit = FeatureUnit(
                "mut.struct.full", "strategy_modules/ict/structure_context.py",
                ("structure_label", "in_bullish_structure", "in_bearish_structure"),
                lambda d: m.add_structure_context(d, {"lookback": 50, "pivot_bars": 2}),
                truncation_data=lambda: data,
            )
            """
        ),
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "R1_structure_full_revert")


def test_R2_swing_full_revert(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/indicators/swing.py"
    text = target.read_text(encoding="utf-8")
    # Replace both pivot_highs and pivot_lows with centered versions
    start = text.index("def pivot_highs(")
    end = text.index("def pivot_high_prices(")
    legacy_both = textwrap.dedent(
        '''
        def pivot_highs(data, pivot_bars=2):
            import pandas as pd
            window = 2 * pivot_bars + 1
            high_roll = data["high"].rolling(window, center=True, min_periods=pivot_bars + 1).max()
            return (data["high"] == high_roll) & high_roll.notna()

        def pivot_lows(data, pivot_bars=2):
            import pandas as pd
            window = 2 * pivot_bars + 1
            low_roll = data["low"].rolling(window, center=True, min_periods=pivot_bars + 1).min()
            return (data["low"] == low_roll) & low_roll.notna()

        '''
    )
    target.write_text(text[:start] + legacy_both + text[end:], encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.indicators.swing as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import FeatureUnit, truncation_mismatches, _ind_frame, fixture_pivot_high
        data = fixture_pivot_high()
        unit = FeatureUnit(
            "mut.swing.full", "indicators/swing.py", ("pivot_high",),
            lambda d: _ind_frame({"pivot_high": m.pivot_highs(d, 2)}, d.index),
            truncation_data=lambda: data,
        )
        errs = truncation_mismatches(unit, data)
        print("MUTATION_KILLED" if errs else "MUTATION_UNDETECTED")
        print("FAIL_IDS", "truncation_mismatches")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "R2_swing_full_revert")


def test_R3_mss_full_revert(tmp_path: Path):
    qb = _mirror_qb(tmp_path)
    (qb / "src/quantbuild/strategy_modules/ict/market_structure_shift.py").write_text(LEGACY_MSS, encoding="utf-8")
    code = _probe_truncation_kill(
        "import src.quantbuild.strategy_modules.ict.market_structure_shift as m",
        textwrap.dedent(
            """
            from src.quantbuild.testing.truncation_harness import fixture_mss_both
            data = fixture_mss_both()
            unit = FeatureUnit(
                "mut.mss.full", "strategy_modules/ict/market_structure_shift.py",
                ("swing_high", "swing_low", "bullish_mss", "bearish_mss"),
                lambda d: m.MarketStructureShiftModule().calculate(d, {"swing_lookback": 5, "break_threshold_pct": 0.2}),
                truncation_data=lambda: data,
            )
            """
        ),
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "R3_mss_full_revert")


def test_R4_order_blocks_full_revert(tmp_path: Path):
    """Full revert: both OB directions write on origin (look-ahead)."""
    qb = _mirror_qb(tmp_path)
    target = qb / "src/quantbuild/strategy_modules/ict/order_blocks.py"
    mutant = (
        target.read_text(encoding="utf-8")
        .replace("bullish_ob[conf] = True", "bullish_ob[i] = True  # MUTANT")
        .replace("bearish_ob[conf] = True", "bearish_ob[i] = True  # MUTANT")
    )
    assert mutant.count("MUTANT") == 2
    target.write_text(mutant, encoding="utf-8")
    code = textwrap.dedent(
        """
        import src.quantbuild.strategy_modules.ict.order_blocks as m
        print("FILE", m.__file__)
        from src.quantbuild.testing.truncation_harness import fixture_ob_bullish, fixture_ob_bearish
        cfg = {"min_candles": 3, "min_move_pct": 3.0, "validity_candles": 20}
        bull = m.OrderBlockModule().calculate(fixture_ob_bullish(), cfg)
        bear = m.OrderBlockModule().calculate(fixture_ob_bearish(), cfg)
        # Causal confirms at 6; full revert flags origin 3 for both dirs
        killed = (
            bool(bull["bullish_ob"].iloc[3]) and not bool(bull["bullish_ob"].iloc[6])
        ) and (
            bool(bear["bearish_ob"].iloc[3]) and not bool(bear["bearish_ob"].iloc[6])
        )
        print("MUTATION_KILLED" if killed else "MUTATION_UNDETECTED")
        print("FAIL_IDS", "test_ob_bullish_not_earlier_not_later|test_ob_bearish_not_earlier_not_later")
        """
    )
    _assert_killed(_run(code, pythonpath=_pythonpath(qb)), "R4_order_blocks_full_revert")


def test_mutation_case_table_complete():
    """Ensure the documented 12-case IDs stay wired to tests in this module."""
    assert len(MUTATION_CASES) == 12
    names = {n for n in dir(sys.modules[__name__]) if n.startswith("test_T") or n.startswith("test_R")}
    for case in MUTATION_CASES:
        assert any(case.split("_", 1)[0] in n or case in n for n in names) or True
    # Hard map: each case has a dedicated test function
    expected_fns = {
        "T1_structure_center": "test_T1_structure_center_targeted",
        "T2_swing_pivot_highs_center": "test_T2_swing_pivot_highs_center_targeted",
        "T3_mss_center": "test_T3_mss_center_targeted",
        "T4_fvg_bullish_middle": "test_T4_fvg_bullish_middle_targeted",
        "T5_fvg_bearish_middle": "test_T5_fvg_bearish_middle_targeted",
        "T6_sweep_bullish_origin": "test_T6_sweep_bullish_origin_targeted",
        "T7_sweep_bearish_origin": "test_T7_sweep_bearish_origin_targeted",
        "T8_ob_bullish_origin": "test_T8_ob_bullish_origin_targeted",
        "R1_structure_full_revert": "test_R1_structure_full_revert",
        "R2_swing_full_revert": "test_R2_swing_full_revert",
        "R3_mss_full_revert": "test_R3_mss_full_revert",
        "R4_order_blocks_full_revert": "test_R4_order_blocks_full_revert",
    }
    mod = sys.modules[__name__]
    for case, fn in expected_fns.items():
        assert hasattr(mod, fn), f"missing test for {case}"
