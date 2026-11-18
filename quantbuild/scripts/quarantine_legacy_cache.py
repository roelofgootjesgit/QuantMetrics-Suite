#!/usr/bin/env python3
"""Owner-invoked DATA-002 I4 legacy cache inventory / quarantine CLI.

Default: COPY into ``<base>/_quarantine/...`` (originals preserved).
MOVE: only with explicit ``--move`` (never the default).
Delete: not offered — never deletes cache files.

Safety: mutations require ``--execute``. Prefer ``--dry-run`` on a **copy** of
non-production cache first. Do not target real owner cache without approval.

``load_parquet`` / ``ensure_data`` never call this tool.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from src.quantbuild.io.legacy_cache_quarantine import (  # noqa: E402
    format_report_text,
    run_quarantine,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="quarantine_legacy_cache",
        description=(
            "Owner-invoked legacy parquet cache inventory/quarantine (DATA-002 I4). "
            "Default COPY; --move only explicit; never deletes."
        ),
    )
    p.add_argument(
        "--base-path",
        required=True,
        type=Path,
        help="Cache root to scan (required; no implicit production default)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned actions without copying or moving",
    )
    p.add_argument(
        "--inventory-only",
        action="store_true",
        help="Alias for --dry-run (scan/report only)",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Perform COPY (default) or MOVE (--move); required for mutation",
    )
    p.add_argument(
        "--move",
        action="store_true",
        help="Opt-in MOVE into quarantine (default is COPY preserving originals)",
    )
    p.add_argument(
        "--symbol",
        action="append",
        dest="symbols",
        default=None,
        help="Limit to symbol (repeatable). Default: all symbols",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write machine-readable report JSON",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = bool(args.dry_run or args.inventory_only or not args.execute)
    if args.execute and (args.dry_run or args.inventory_only):
        print("Use either --dry-run/--inventory-only or --execute, not both.", file=sys.stderr)
        return 2
    if not args.execute and not (args.dry_run or args.inventory_only):
        # Bare invocation → dry-run by default (fail-safe).
        dry_run = True

    report = run_quarantine(
        args.base_path,
        dry_run=dry_run,
        move=bool(args.move),
        symbols=args.symbols,
    )
    print(format_report_text(report), end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote JSON report: {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
