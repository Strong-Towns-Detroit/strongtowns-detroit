# Nonprofit data access

Collaborators must be able to recover and query data without individual
metered API accounts.

## Invariants

- Immutable snapshots and canonical GeoParquet remain authoritative.
- Databases are replaceable query mirrors; edits never flow back to evidence.
- Only clean, promoted manifests may be published.
- Published tables retain dataset, snapshot, manifest, artifact, and row-count
  identity.
- Downloads work without credentials or paid queries after retrieval.
- Publication is explicit and dry-run by default.
- Credentials use organization-owned, narrowly scoped accounts and never enter
  Git, manifests, notebooks, or database files.
- Losing a vendor cannot destroy data or prevent a local rebuild.

## Implemented baseline

`detroit-query-catalog` materializes promoted tables into a portable DuckDB
database with a manifest-bound JSON index. Consumer connections are read-only;
external access and extension installation are disabled.

```bash
uv run strongtowns-data build detroit-query-catalog
uv run strongtowns-data catalog inspect detroit.query.catalog
uv run --extra notebooks marimo edit notebooks/data_catalog.py
```

## Hosting choices

| Option | Benefit | Cost or risk |
|---|---|---|
| Static versioned download | Unlimited local queries; no user accounts or per-query charge | Users redownload new snapshots |
| Managed Postgres/PostGIS | Remote SQL and read-only collaborator accounts | Base price plus storage/egress limits |
| Self-hosted Postgres/PostGIS | Fixed infrastructure bill and full access control | Security, backups, monitoring, and volunteer labor |
| Usage-priced warehouse | Convenient hosted analytics | Unpredictable cost and account barriers |

Start with static download. A remote mirror remains optional and cannot be the
only query or storage path.

## Decision gate

Before implementing an external adapter, choose the maximum monthly cost,
anonymous versus named access, credential owner, alert owner, recovery target,
snapshot retention, and responsible maintainer. No R2 bucket or hosted database
is currently configured.
