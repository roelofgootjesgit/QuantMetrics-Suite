"""DATA-002 I4 — owner-invoked legacy cache inventory / quarantine.

Default action is **COPY** into ``base_path/_quarantine/...``.
**MOVE** only with explicit ``move=True`` / CLI ``--move``.
**Never delete** cache files (no delete API).

Not called from ``load_parquet`` / ``ensure_data`` / ``ensure_live_data``.
Does not reinterpret bytes as UTC spot; quarantine is isolation only.

I2 sidecar naming is mirrored here as a **stable documented interface** without
importing unmerged ``provenance_cache`` (PR #137 MERGE HOLD). See
``docs/plans/ISSUE_133_DATA002_I4_INTEGRATION.md``.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Sequence

SCHEMA_VERSION = "data002-i4-v1"
QUARANTINE_DIRNAME = "_quarantine"

# Stable I2-compatible naming (do not import provenance_cache).
SIDECAR_SUFFIX = ".provenance.json"
LOCK_SUFFIX = ".parquet.lock"
PARQUET_SUFFIX = ".parquet"

_ORPHAN_TEMP_RE = re.compile(
    r"^\.(?P<stem>.+)\.(?:parquet|provenance\.json)\.tmp(?:\.\d+)?$"
)


class QuarantineError(ValueError):
    """Invalid quarantine request (e.g. delete requested)."""


ActionMode = Literal["copy", "move"]
FindingKind = Literal[
    "legacy_parquet_no_sidecar",
    "orphan_temp",
    "orphan_sidecar_without_parquet",
]


@dataclass(frozen=True)
class CacheFinding:
    kind: FindingKind
    symbol: str
    relative_path: str
    absolute_path: str
    size: int
    mtime_ns: int
    timeframe_hint: str = ""
    note: str = ""


@dataclass
class QuarantineAction:
    finding: CacheFinding
    mode: ActionMode
    dry_run: bool
    source_path: str
    dest_path: str
    note_path: str
    content_sha256: str
    performed: bool
    skipped_reason: str = ""


@dataclass
class QuarantineReport:
    base_path: str
    dry_run: bool
    mode: ActionMode
    findings: list[CacheFinding] = field(default_factory=list)
    actions: list[QuarantineAction] = field(default_factory=list)
    generated_at_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "base_path": self.base_path,
            "dry_run": self.dry_run,
            "mode": self.mode,
            "generated_at_utc": self.generated_at_utc,
            "findings": [asdict(f) for f in self.findings],
            "actions": [
                {
                    **{k: v for k, v in asdict(a).items() if k != "finding"},
                    "finding": asdict(a.finding),
                }
                for a in self.actions
            ],
            "semantics": (
                "Quarantine does not reinterpret bytes as UTC spot; "
                "research remains DENY until re-fetch under new writer+sidecar "
                "or owner attestation binds old bytes. Never deletes."
            ),
        }


def inventory_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Map relative path → (size, mtime_ns) for all files under root."""
    root = Path(root)
    out: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        st = p.stat()
        out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sidecar_path_for_parquet(parquet: Path) -> Path:
    """I2-compatible: ``15m.parquet`` → ``15m.provenance.json``."""
    if parquet.suffix != PARQUET_SUFFIX:
        raise QuarantineError(f"not a parquet path: {parquet}")
    return parquet.with_name(parquet.name[: -len(PARQUET_SUFFIX)] + SIDECAR_SUFFIX)


def _symbol_from_parts(base: Path, path: Path) -> str:
    try:
        rel = path.relative_to(base)
    except ValueError:
        return "UNKNOWN"
    parts = rel.parts
    if not parts:
        return "UNKNOWN"
    if parts[0] == QUARANTINE_DIRNAME:
        return parts[1] if len(parts) > 1 else "UNKNOWN"
    return parts[0]


def _timeframe_hint(name: str) -> str:
    if name.endswith(PARQUET_SUFFIX):
        return name[: -len(PARQUET_SUFFIX)]
    m = _ORPHAN_TEMP_RE.match(name)
    if m:
        return m.group("stem")
    if name.endswith(SIDECAR_SUFFIX):
        return name[: -len(SIDECAR_SUFFIX)]
    return ""


def scan_legacy_cache(
    base_path: Path,
    *,
    symbols: Optional[Sequence[str]] = None,
) -> list[CacheFinding]:
    """Inventory quarantine candidates under ``base_path`` (skips ``_quarantine``)."""
    base = Path(base_path)
    if not base.exists():
        return []

    allow = {s.upper() for s in symbols} if symbols else None
    findings: list[CacheFinding] = []

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if rel.parts and rel.parts[0] == QUARANTINE_DIRNAME:
            continue
        # Locks are coordination artifacts, not quarantine targets.
        if path.name.endswith(LOCK_SUFFIX):
            continue

        symbol = _symbol_from_parts(base, path)
        if allow is not None and symbol.upper() not in allow:
            continue

        st = path.stat()
        common = dict(
            symbol=symbol,
            relative_path=str(rel),
            absolute_path=str(path),
            size=st.st_size,
            mtime_ns=st.st_mtime_ns,
            timeframe_hint=_timeframe_hint(path.name),
        )

        if _ORPHAN_TEMP_RE.match(path.name):
            findings.append(
                CacheFinding(
                    kind="orphan_temp",
                    note="orphan write temp; safe quarantine via copy/move only",
                    **common,
                )
            )
            continue

        if path.name.endswith(PARQUET_SUFFIX) and not path.name.startswith("."):
            sc = sidecar_path_for_parquet(path)
            if not sc.is_file():
                findings.append(
                    CacheFinding(
                        kind="legacy_parquet_no_sidecar",
                        note="parquet without I2 sidecar; owner quarantine candidate",
                        **common,
                    )
                )
            continue

        if path.name.endswith(SIDECAR_SUFFIX) and not path.name.startswith("."):
            stem = path.name[: -len(SIDECAR_SUFFIX)]
            pq = path.with_name(stem + PARQUET_SUFFIX)
            if not pq.is_file():
                findings.append(
                    CacheFinding(
                        kind="orphan_sidecar_without_parquet",
                        note="sidecar without parquet; quarantine candidate",
                        **common,
                    )
                )

    return findings


def _dest_paths(
    base: Path,
    finding: CacheFinding,
    digest: str,
    *,
    ts_slug: str,
) -> tuple[Path, Path]:
    qroot = base / QUARANTINE_DIRNAME
    if finding.kind == "orphan_temp":
        dest_dir = qroot / "_orphans" / finding.symbol
    else:
        dest_dir = qroot / finding.symbol
    short = digest[:12] if digest else ts_slug
    src_name = Path(finding.relative_path).name
    dest = dest_dir / f"{src_name}.{short}.quarantined"
    note = dest.with_suffix(dest.suffix + ".note.json")
    return dest, note


def quarantine_finding(
    base_path: Path,
    finding: CacheFinding,
    *,
    mode: ActionMode = "copy",
    dry_run: bool = True,
) -> QuarantineAction:
    """Quarantine one finding. Default COPY; MOVE only when mode='move'. Never delete."""
    if mode not in ("copy", "move"):
        raise QuarantineError(f"unsupported mode {mode!r}; use copy|move (never delete)")

    base = Path(base_path)
    src = Path(finding.absolute_path)
    if not src.is_file():
        return QuarantineAction(
            finding=finding,
            mode=mode,
            dry_run=dry_run,
            source_path=str(src),
            dest_path="",
            note_path="",
            content_sha256="",
            performed=False,
            skipped_reason="source missing",
        )

    digest = sha256_file(src)
    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest, note_path = _dest_paths(base, finding, digest, ts_slug=ts_slug)

    action = QuarantineAction(
        finding=finding,
        mode=mode,
        dry_run=dry_run,
        source_path=str(src),
        dest_path=str(dest),
        note_path=str(note_path),
        content_sha256=digest,
        performed=False,
    )

    if dry_run:
        return action

    dest.parent.mkdir(parents=True, exist_ok=True)
    if mode == "copy":
        shutil.copy2(src, dest)
    else:
        # Explicit MOVE only — still never delete; destination retains bytes.
        shutil.move(str(src), str(dest))

    note_body = {
        "schema_version": SCHEMA_VERSION,
        "action": mode,
        "source_path": str(src),
        "dest_path": str(dest),
        "relative_source": finding.relative_path,
        "kind": finding.kind,
        "symbol": finding.symbol,
        "content_sha256": digest,
        "quarantined_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "semantics": (
            "Isolation only — does not reinterpret as UTC spot; "
            "no delete; research DENY until re-fetch or owner attestation."
        ),
    }
    note_path.write_text(json.dumps(note_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    action.performed = True
    return action


def run_quarantine(
    base_path: Path,
    *,
    dry_run: bool = True,
    move: bool = False,
    symbols: Optional[Sequence[str]] = None,
    kinds: Optional[Iterable[FindingKind]] = None,
) -> QuarantineReport:
    """Scan + optional quarantine. ``move=False`` ⇒ COPY (default)."""
    if move is not True and move is not False:
        raise QuarantineError("move must be bool")
    mode: ActionMode = "move" if move else "copy"
    base = Path(base_path)
    findings = scan_legacy_cache(base, symbols=symbols)
    if kinds is not None:
        allow_kinds = set(kinds)
        findings = [f for f in findings if f.kind in allow_kinds]

    report = QuarantineReport(
        base_path=str(base),
        dry_run=dry_run,
        mode=mode,
        findings=list(findings),
        generated_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    for finding in findings:
        report.actions.append(
            quarantine_finding(base, finding, mode=mode, dry_run=dry_run)
        )
    return report


def format_report_text(report: QuarantineReport) -> str:
    lines = [
        f"DATA-002 I4 quarantine report  mode={report.mode}  dry_run={report.dry_run}",
        f"base_path={report.base_path}",
        f"findings={len(report.findings)}  actions={len(report.actions)}",
        "NEVER deletes. Default is COPY; MOVE only when requested.",
        "Do not run against real owner cache without explicit owner approval.",
        "",
    ]
    for a in report.actions:
        tag = "WOULD" if report.dry_run else ("DID" if a.performed else "SKIP")
        lines.append(
            f"  [{tag}] {a.mode} {a.finding.kind} {a.finding.relative_path} "
            f"-> {a.dest_path or '(n/a)'} sha={a.content_sha256[:12] if a.content_sha256 else '-'}"
        )
    return "\n".join(lines) + "\n"
