# Source snapshots — consumption, thin readers, and immutable identity

The compiler's canonical source input is a **frozen `SourceSnapshot`** produced by
`rmax-ai/dataset-sources` (ADR-0013): a digest-addressed immutable manifest of catalog rows —
stable identity, provider revision facts, per-row license evidence, object URIs — with optional
mirrored object references (S3 data plane).

Provider registration, discovery, acquisition, and mirroring live in `rmax-ai/dataset-sources`.
This repository **consumes** snapshots and the object URIs they reference; it never performs
provider enumeration or acquisition itself.

Compiler-side source layer (ADR-0013 amendment):

1. **snapshot consumption** — read and validate snapshot manifests; verify snapshot and catalog
   digests; normalize rows into `CandidateAsset`/`CandidateGroup`;
2. **thin URI/object readers** — streaming/range reads of referenced objects (`file:`/`https:`/
   `s3:`) for technical inspection, bounded memory;
3. **technical inspection** — sha256 verification, MIME, dimensions, pHash, basic metadata.

## 1. The contract

```python
class SnapshotReader(Protocol):
    reader_id: str            # "file" | "http" | "s3" (thin reader implementations)

    def resolve(self, source: SourceSpec) -> CandidateCatalog: ...
```

`SourceSpec` binds one snapshot:

| field | notes |
|---|---|
| `snapshot.uri` | manifest location (`file:`, `https:`, `s3://…`) |
| `snapshot.digest` | expected content digest of the snapshot manifest; the source identity |
| `snapshot.frozen` | `true` required for build eligibility; `false` = draft/exploration only |
| `reader` | optional explicit reader id; default resolved from the URI scheme |
| `params` | reader-level options only (timeouts, bounded concurrency, fixture overrides) |
| `license_policy` | redistribution allowlist + `require_evidence` |

`CandidateCatalog` carries, per candidate:

| field | notes |
|---|---|
| `source_id` | logical source (spec key) |
| `snapshot_digest` | frozen snapshot digest (source identity for this build) |
| `source_revision` | provider-native revision facts carried by the snapshot (commit sha, pageid/revid, snapshot id, …) |
| `asset_id` | stable within (source_id, snapshot) |
| `uri` | canonical fetch URI (immutable form where the provider allows) |
| `checksum` | content hash as recorded by the snapshot; verified at inspection when bytes are read |
| `media_type` | declared/derived MIME |
| `license` | source-declared evidence: id/name, URL, author/credit, redistribution flags where declared |
| `group_id` | optional; coherent series/burst/session grouping from snapshot series evidence |
| `snapshot_metadata` | snapshot extras (dimensions hints, categories, capture order) |
| `provenance` | where the metadata came from (snapshot manifest location; upstream endpoint recorded upstream) |

Normalization rules:

- Candidates are deterministically ordered (`asset_id` within group/source) before hashing.
- Rows missing license evidence are **recorded as absent** (never guessed) and later fail closed
  where redistribution is requested.
- `group_id` comes from series evidence carried by the snapshot (a series column, an explicit
  sequence, a documented single-session collection) or a spec-level `group_by` over catalog
  fields. **Group admission rule:** groups are never invented to hit a target — a shortfall is
  reported as an incomplete build (docs/specification.md §3). Heuristic clusters may be proposed
  as derivation candidates only with a documented, reviewed derivation (confidence + traceable
  member list).
- Snapshot rows are passthrough: the compiler adds no upstream facts it cannot attribute.

## 2. Immutable identity rules

- The **frozen snapshot digest is the source identity**. Replaying a frozen snapshot is
  byte-identical by construction. Whether two live upstream recrawls agree is a
  dataset-sources concern (freezing/mirroring policy, ADR-0013) — the compiler makes no such claim.
- Builds execute from `frozen: true` snapshots only. Draft (non-frozen) snapshots are
  *exploration* mode: `catalog` may consume them with a loud warning; never build-eligible.
- Catalog digest = canonical JSON of the normalized rows + snapshot identity fields.
- Content identity is preferred where bytes are available: `sha256` of the exact byte stream
  (verified against snapshot-recorded checksums at inspection); `pHash` computed at inspection.
- Provider revision facts are preserved in `source_revision` for traceability; identity for
  builds/rebuilds is the snapshot digest.

## 3. v0.1 readers

### 3.1 `file` — local snapshot fixtures

- Input: local snapshot directory/manifest (manifest JSON + JSONL/CSV rows).
- Purpose: offline tests, user-owned snapshots, CI fixtures. Fully deterministic; no network.

### 3.2 `http` — remote snapshot manifests

- Input: pinned snapshot manifest URL (`https:`), digest-verified.
- Network reads on the direct/live rail only; tests use local fixtures.
- Purpose: consuming snapshots published by dataset-sources (or mirrors) without an S3 client.

### 3.3 `s3` — object-storage snapshots (thin; optional in v0.1)

- Input: `s3://` snapshot manifest URI + referenced object URIs; streaming/range reads; bounded
  memory.
- Credentials: never stored in the repo; environment-provided at run time, read-only. Absence of
  the `s3` reader never blocks the reference path (`file`/`http` suffice).
- Data plane context (ADR-0013): external operator-provisioned buckets
  `rmax-ai-datasets-source|derived|cache|public`, Hetzner S3-compatible storage,
  Nuremberg / EU Central.

Not in this repository: provider registration/discovery/acquisition/mirroring
(→ `rmax-ai/dataset-sources`, ADR-0013); Kaggle; provider-credentialed sources.

## 4. No-credential reference path

The public reference path works with **zero credentials**:

- canonical reference input: the small frozen **pet SourceSnapshot** produced by
  `rmax-ai/dataset-sources` E7 (itself compiled upstream from Wikimedia/Hugging Face/anonymous
  sources);
- offline tests and CI: `file` fixture snapshots;
- if a snapshot requires credentials, it is deferred; operator escalation only if a no-auth path
  is impossible.

## 5. Storage non-ownership

- The compiler never creates buckets, configures CDNs, provisions mirrors, or stores credentials.
- The data plane is external and operator-provisioned (ADR-0013). The compiler reads object URIs
  referenced by snapshots; it provisions nothing.
- Optional read/materialize support for object stores (fsspec-style) is a **destination** feature:
  a URI output target for selected bytes. It provisions nothing; credentials never live in the
  repo (environment-provided, operator-scoped).

## 6. Worker invariant (ADR-0010)

- Normal path: **manifest/object ref → streaming/range read → bounded memory/cache → result**.
- No full-dataset staging on worker disks. Individual-object or bounded-batch local materialization
  is allowed only as **disposable ADR-0010 cache with explicit limits** (documented configuration;
  surfaced by `plan` preflight).
- The reference demo measures full snapshot bytes vs peak local dataset-cache bytes and proves the
  cache budget is smaller than the source snapshot (E6 acceptance; docs/evaluation.md).
- Worker filesystems are ephemeral workspace/cache tiers — dataset payloads belong upstream or in
  the object-storage plane.

## 7. Snapshot contract dependency (cross-repo)

- The snapshot manifest shape is co-defined with `rmax-ai/dataset-sources` (ADR-0013; DQ #141).
  Compiler-side consumption contracts link to the matching #141 E1/E2 triggers once filed.
- Do not implement a duplicate provider-acquisition path in this repository — that is a boundary
  defect (leak test, docs/architecture.md §9).
