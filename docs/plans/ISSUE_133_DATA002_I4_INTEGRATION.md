# DATA-002 I4 ↔ I2 integration (MERGE HOLD)

**Status:** I4 owner quarantine/inventory on `main` **without merging I2**
(PR #137 APPROVED, MERGE HOLD).

## Stable interface (no quiet I2 import)

I4 mirrors planned I2 filenames locally in `legacy_cache_quarantine.py`:

| Artifact | Pattern |
|---|---|
| Parquet | `<SYMBOL>/<tf>.parquet` |
| Sidecar | `<SYMBOL>/<tf>.provenance.json` |
| Lock | `<SYMBOL>/<tf>.parquet.lock` (ignored by quarantine) |
| Orphan temps | `.<tf>.parquet.tmp[.pid]`, `.<tf>.provenance.json.tmp[.pid]` |
| Quarantine root | `<base>/_quarantine/<SYMBOL>/...` and `_quarantine/_orphans/...` |

I4 **does not** `import provenance_cache`. When I2 merges, keep these names;
wire I2 readers to DENY legacy parquet-without-sidecar while owners use this
CLI to COPY (default) or `--move` into quarantine.

## Owner instructions (non-production first)

1. Copy a non-production cache tree to a scratch path.
2. `python scripts/quarantine_legacy_cache.py --base-path <scratch> --dry-run`
3. Review report / optional `--json-out`.
4. `... --execute` for COPY (originals preserved) or `... --execute --move`.
5. **Never** run against real owner cache without explicit owner approval.
6. Quarantine does **not** reinterpret bytes; research stays DENY until re-fetch
   under I2 writer+sidecar or owner attestation.

## Load / ensure

`load_parquet` / `ensure_data` / `ensure_live_data` must **never** call this
module, and on policy DENY must not move/copy/delete cache files (inventory
path/size/mtime unchanged).
