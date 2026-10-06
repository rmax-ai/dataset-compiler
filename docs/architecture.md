# Architecture

This document fixes the system boundaries and the compilation pipeline. It is the operational
expansion of `rmax-ai/architecture` ADR-0012 (amended 2026-10-03 — single Jev adapter boundary) and
ADR-0013 (dataset source registry + S3 streaming data plane — source boundary); where they
disagree, the ADRs win.

## 1. System boundary

The compiler **consumes**: frozen `SourceSnapshot` manifests (ADR-0013), the object URIs they
reference, streams, and locally cached bytes.
The compiler **owns**: contract models, the compilation pipeline, evidence/receipt records, the
`BuildManifest`, and the optional materializers.

The compiler does **not** own:

- provider registration, discovery, acquisition, or mirroring (owned by `rmax-ai/dataset-sources`,
  ADR-0013; the compiler consumes frozen snapshots only);
- source hosting or upstream-provider operations;
- object-store provisioning, bucket lifecycle, credentials, CDN, or mirrors;
- legal conclusions about licenses (it preserves source-declared evidence and fails closed on
  missing/ambiguous redistribution metadata where redistribution is requested).

```text
                    DatasetSpec
                        │
                        ▼
        SourceSnapshot consumption ──────► CandidateCatalog
         (frozen; digest-verified)          (stable identity + provenance)
          ┌─────────────┴─────────────┐
          ▼                           ▼
 deterministic inspection      semantic observation
 hash/MIME/dims/license        observer → typed evidence
 pHash/basic metadata                  │
          │                           ▼
          └──────────────► atomic predicates (deterministic rules; optional external predicates)
                        │
                        ▼
              objectives + embeddings
                        │
                        ▼
                portfolio selector
        hard constraints / quotas / coverage / diversity / groups
                        │
                        ▼
                  verification
                        │
                        ▼
                  BuildManifest ──► optional materializer (local / archive / object URI)
```

## 2. Deterministic vs probabilistic

| Concern | Owner | Notes |
|---|---|---|
| Spec validation, hard constraints, quotas | deterministic code | never model-decided |
| Portfolio selection given frozen evidence | deterministic code | greedy v0.1; replaceable solver |
| Provenance, receipts, digests | deterministic code | content-addressed where possible |
| Observations, scores, embeddings | probabilistic components | produce **evidence**, not decisions |
| External text classification | external predicate provider (e.g. Jev via `jev-tool`) | provider-neutral contract; never in-band model calls from rmax-side code |

Rebuild rule: **changing only thresholds/weights/quotas/diversity constraints must not force
semantic re-inference** when compatible frozen evidence exists. This is enforced by the four
cacheable layers (§4).

## 3. Pipeline stages

Each stage is content-addressed and cacheable; every stage records its full identity.

1. **Consume** — read the frozen `SourceSnapshot`, verify snapshot/catalog digests, normalize
   rows → `CandidateCatalog` (source identity = snapshot digest).
2. **Gate** — license/metadata pre-checks, cheap filters, exact-hash dedup, oversample retention.
3. **Inspect** — deterministic technical pass: MIME, dimensions, byte size, content hash, pHash.
4. **Observe** — semantic observer transforms a candidate into a typed `SemanticObservation`
   (only for the reduced pool; never the full source).
5. **Evaluate** — atomic predicates (hard/semantic) → `PredicateResult`; objectives →
   `ObjectiveScore`; embeddings/features as required.
6. **Select** — portfolio selector applies hard constraints, quotas, coverage, diversity, groups →
   `SelectionDecision` per candidate with reason codes.
7. **Verify** — checksums, schema validation, policy re-checks (offline; no hidden network).
8. **Freeze** — emit `BuildManifest`; materialization (if requested) is a separate replaceable step.

## 4. Cache layers

```text
source bytes / content identity        → key: snapshot digest + asset identity (+ checksum)
technical + semantic observations      → key: + inspector/observer/model/prompt/schema versions
predicate/objective evaluations        → key: + predicate/objective definitions digest
dataset selection                      → key: + spec digest (selection-relevant parts) + evidence digests
```

Re-running a probabilistic evaluator creates **new** evidence; it never silently overwrites prior
evidence. A build records which receipts it consumed.

## 5. Extension points (v0.1)

- **Snapshot readers**: `file`, `http` (v0.1); `s3` thin reader optional (object-storage data
  plane, ADR-0013). No provider adapters — registration/discovery/acquisition/mirroring live in
  `rmax-ai/dataset-sources`. Optional/later: fsspec-style materialize. Kaggle: not required for
  v0.1.
- **Observers**: `mock`/offline (CI), one bounded VLM reference adapter (spend-gated).
- **External predicates**: provider-neutral contract; `jev-tool` satisfies it for rmax-side
  integration (ADR-0003).
- **Domain blocks**: image-specific observation/feature fields live behind a typed block
  (`observation_schema: image.v1`). Core models remain domain-neutral where that costs nothing.

## 6. External data plane and worker invariant (ADR-0010, ADR-0013)

The data plane is external and operator-provisioned: Hetzner S3-compatible object storage
(Nuremberg / EU Central), buckets `rmax-ai-datasets-source|derived|cache|public`. The compiler
reads object URIs referenced by snapshots and provisions nothing; no credentials or endpoints
with secrets live in the repository.

Worker invariant: the normal path is **manifest/object ref → streaming/range read → bounded
memory/cache → result** — no full-dataset staging on worker disks. Individual-object or
bounded-batch local materialization is allowed only as disposable ADR-0010 cache with explicit
limits (documented configuration; surfaced by `plan`).

## 7. Determinism policy

- Serialization: canonical JSON (sorted keys, minimal separators) for all digests.
- Ordering: catalogs and decision sets are deterministically ordered before hashing.
- Time/randomness: no wall-clock or random inputs in selection; IDs derive from content.
- Floating point: scores are rounded to a documented precision before participation in digests.
- Library versions that affect digests (hashing, pHash) are pinned and recorded in receipts.

## 8. Process model

- CLI-first, library-first: the CLI is a thin shell over the library; all stages usable offline.
- `plan` performs no live inference; it estimates work and surfaces blockers.
- `verify` requires no network: it re-validates the manifest against available frozen
  evidence/bytes.
- No background services, no daemons in v0.1.

## 9. Boundary leak tests (acceptance themes)

- Selection identical across materialization targets (or none).
- `verify` fails when network is unavailable? No: `verify` **passes** offline by design; a hidden
  network attempt is a defect (assert no sockets in tests).
- Quota-only spec edits reuse receipts (observer call count stays zero).
- Catalog digest stable under reordering of enumeration, unstable under revision change.
- No provider acquisition code: no provider API clients or enumeration paths for Wikimedia/
  Hugging Face/others exist (grep-level boundary test); source input arrives only via snapshot
  readers.
- No bucket provisioning logic anywhere; object URIs are read/destination-only.
