"""DATA-002 I2 — refresh-safe parquet + provenance sidecar protocol.

Protocol (not jointly atomic across both files):
  1. per-cache FileLock
  2. temp parquet → os.replace
  3. SHA-256 of final parquet bytes
  4. temp sidecar → os.replace
Readers DENY on missing/mismatched sidecar (incl. crash gap). No silent recovery.
Writer sidecar is not independent DTA evidence; HTF needs owner attestation
bound to the same content_sha256.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

from filelock import FileLock

SCHEMA_VERSION = "data002-i2-v1"

IDENTITY_FIELDS = (
    "source",
    "instrument",
    "offer_side",
    "timezone_storage",
    "index_semantics",
)

# Owner DTA fields — ordinary writers must not invent or overwrite these.
OWNER_ATTESTED_FIELDS = frozenset(
    {
        "attested_by",
        "attested_at_utc",
        "method",
        "probe_results",
        "dta_attestation",
    }
)

WRITER_FIELDS = frozenset(
    {
        "symbol",
        "instrument",
        "timeframe",
        "source",
        "single_source",
        "offer_side",
        "timezone_storage",
        "index_semantics",
        "content_sha256",
        "written_at_utc",
        "writer",
        "schema_version",
    }
)


class ProvenanceError(ValueError):
    """Fail-closed provenance / sidecar violation."""


class ProvenanceDenyError(ProvenanceError):
    """Reader DENY — sidecar absent, unreadable, or hash mismatch."""


class ProvenanceIdentityError(ProvenanceError):
    """Refresh DENY — identity fields do not match existing sidecar."""


def parquet_path_for(base_path: Path, symbol: str, timeframe: str) -> Path:
    return Path(base_path) / symbol.upper() / f"{timeframe}.parquet"


def sidecar_path_for(base_path: Path, symbol: str, timeframe: str) -> Path:
    return Path(base_path) / symbol.upper() / f"{timeframe}.provenance.json"


def lock_path_for(base_path: Path, symbol: str, timeframe: str) -> Path:
    return Path(base_path) / symbol.upper() / f"{timeframe}.parquet.lock"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory_snapshot(dir_path: Path) -> dict[str, tuple[int, int]]:
    """Map relative path → (size, mtime_ns) for files under dir_path (no recursion into quarantine)."""
    root = Path(dir_path)
    out: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        st = p.stat()
        out[rel] = (st.st_size, st.st_mtime_ns)
    return out


def read_sidecar(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvenanceDenyError(f"sidecar unreadable: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProvenanceDenyError(f"sidecar not an object: {path}")
    return data


def _identity_tuple(meta: Mapping[str, Any]) -> tuple:
    return tuple(meta.get(k) for k in IDENTITY_FIELDS)


def _strip_writer_attestation(intent: Mapping[str, Any]) -> dict[str, Any]:
    """Remove owner-attested keys from writer-supplied intent (cannot invent attestation)."""
    return {k: v for k, v in intent.items() if k not in OWNER_ATTESTED_FIELDS}


def _merge_sidecar(
    *,
    intent: Mapping[str, Any],
    content_sha256: str,
    existing: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    clean_intent = _strip_writer_attestation(intent)
    out: dict[str, Any] = dict(clean_intent)
    out["content_sha256"] = content_sha256
    out["schema_version"] = str(clean_intent.get("schema_version") or SCHEMA_VERSION)
    out["written_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["single_source"] = bool(clean_intent.get("single_source", True))

    if existing is None:
        return out

    # Preserve owner-attested fields only when still bound to the same content hash.
    prev_hash = existing.get("content_sha256")
    if prev_hash == content_sha256:
        for key in OWNER_ATTESTED_FIELDS:
            if key in existing and key not in out:
                out[key] = existing[key]
        # Also preserve attested semantic fields when hash unchanged and previously attested.
        if existing.get("attested_by"):
            for key in ("index_semantics", "timezone_storage"):
                if key in existing:
                    out[key] = existing[key]
    # If hash changed: do not copy old attestation (invalid for new bytes).
    return out


def validate_sidecar_against_parquet(
    parquet: Path,
    sidecar: Path,
    *,
    require_single_source: bool = True,
) -> dict[str, Any]:
    if not parquet.is_file():
        raise ProvenanceDenyError(f"parquet missing: {parquet}")
    if not sidecar.is_file():
        raise ProvenanceDenyError(f"sidecar missing: {sidecar}")

    meta = read_sidecar(sidecar)
    digest = sha256_file(parquet)
    claimed = meta.get("content_sha256")
    if not claimed or claimed == "unknown":
        raise ProvenanceDenyError("sidecar content_sha256 missing/unknown")
    if claimed != digest:
        raise ProvenanceDenyError(
            f"content_sha256 mismatch: sidecar={claimed} file={digest}"
        )
    if require_single_source and meta.get("single_source") is not True:
        raise ProvenanceDenyError("single_source must be true")
    for key in IDENTITY_FIELDS:
        if key not in meta or meta[key] in (None, ""):
            raise ProvenanceDenyError(f"sidecar missing identity field: {key}")
    return meta


def require_owner_dta_for_htf(meta: Mapping[str, Any], content_sha256: str) -> None:
    """HTF research gate: writer sidecar alone is insufficient.

    Requires owner attestation fields bound to the same content_sha256.
    """
    attested_hash = meta.get("content_sha256")
    if not attested_hash or attested_hash == "unknown" or attested_hash != content_sha256:
        raise ProvenanceDenyError(
            "HTF DENY: owner DTA attestation content_sha256 missing/unknown/changed"
        )
    if not meta.get("attested_by"):
        raise ProvenanceDenyError(
            "HTF DENY: writer sidecar is not independent evidence; owner attested_by required"
        )
    if not meta.get("attested_at_utc"):
        raise ProvenanceDenyError("HTF DENY: attested_at_utc required")
    if not meta.get("method"):
        raise ProvenanceDenyError("HTF DENY: attestation method required")


def write_parquet_atomic_with_sidecar(
    *,
    base_path: Path,
    symbol: str,
    timeframe: str,
    frame_writer,  # Callable[[Path], None] writes parquet bytes to given path
    provenance: Mapping[str, Any],
    lock_timeout: float = 30.0,
) -> dict[str, Any]:
    """Refresh-safe write under per-cache lock. Leaves originals untouched on identity DENY."""
    base_path = Path(base_path)
    symbol_u = symbol.upper()
    out_dir = base_path / symbol_u
    out_dir.mkdir(parents=True, exist_ok=True)

    pq_path = parquet_path_for(base_path, symbol_u, timeframe)
    sc_path = sidecar_path_for(base_path, symbol_u, timeframe)
    lk_path = lock_path_for(base_path, symbol_u, timeframe)

    intent = _strip_writer_attestation(provenance)
    for key in IDENTITY_FIELDS:
        if key not in intent or intent[key] in (None, ""):
            raise ProvenanceError(f"write intent missing identity field: {key}")

    lock = FileLock(str(lk_path), timeout=lock_timeout)
    with lock:
        existing_meta: Optional[dict[str, Any]] = None
        if pq_path.is_file():
            if not sc_path.is_file():
                raise ProvenanceDenyError(
                    "parquet exists without sidecar; refusing overwrite; no silent recovery"
                )
            try:
                existing_meta = validate_sidecar_against_parquet(pq_path, sc_path)
            except ProvenanceDenyError as exc:
                # Corrupt/crash-gap pair: do not refresh in place; never delete/repair here.
                raise ProvenanceDenyError(
                    "existing cache pair invalid (crash-gap or mismatch); "
                    "refusing overwrite; no silent recovery"
                ) from exc

            if _identity_tuple(existing_meta) != _identity_tuple(intent):
                raise ProvenanceIdentityError(
                    "refresh DENY: identity mismatch "
                    f"existing={_identity_tuple(existing_meta)} "
                    f"intent={_identity_tuple(intent)}; originals untouched"
                )

        tmp_pq = out_dir / f".{timeframe}.parquet.tmp.{os.getpid()}"
        tmp_sc = out_dir / f".{timeframe}.provenance.json.tmp.{os.getpid()}"
        try:
            if tmp_pq.exists():
                tmp_pq.unlink()
            frame_writer(tmp_pq)
            with tmp_pq.open("rb") as fh:
                os.fsync(fh.fileno())

            os.replace(tmp_pq, pq_path)
            digest = sha256_file(pq_path)

            sidecar_body = _merge_sidecar(
                intent=intent,
                content_sha256=digest,
                existing=existing_meta,
            )
            sidecar_body["symbol"] = intent.get("symbol", symbol_u)
            sidecar_body["timeframe"] = intent.get("timeframe", timeframe)
            sidecar_body["writer"] = intent.get(
                "writer", "quantbuild.provenance_cache"
            )
            for key in IDENTITY_FIELDS:
                # Hash changed → writer identity wins; attested semantics only preserved
                # inside _merge_sidecar when hash unchanged + attested_by present.
                if not (
                    existing_meta
                    and digest == existing_meta.get("content_sha256")
                    and existing_meta.get("attested_by")
                    and key in ("index_semantics", "timezone_storage")
                ):
                    sidecar_body[key] = intent[key]

            tmp_sc.write_text(
                json.dumps(sidecar_body, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with tmp_sc.open("rb") as fh:
                os.fsync(fh.fileno())
            os.replace(tmp_sc, sc_path)
            return sidecar_body
        finally:
            for tmp in (tmp_pq, tmp_sc):
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass


def load_sidecar_fail_closed(
    base_path: Path,
    symbol: str,
    timeframe: str,
    *,
    require_htf_owner_dta: bool = False,
) -> dict[str, Any]:
    """Validate sidecar vs parquet; DENY without mutating any files."""
    pq = parquet_path_for(base_path, symbol, timeframe)
    sc = sidecar_path_for(base_path, symbol, timeframe)
    meta = validate_sidecar_against_parquet(pq, sc)
    if require_htf_owner_dta:
        require_owner_dta_for_htf(meta, meta["content_sha256"])
    return meta
