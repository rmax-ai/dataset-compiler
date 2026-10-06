# PLAN.md — rmax-ai/dataset-compiler

Status: **bootstrap plan** (2026-10-03). This file is the durable contract for the project: the
architecture, the milestone/epic/task tree, dependency order, and the acceptance each task must
satisfy. GitHub issues in this repository mirror this document; planning state here is not
execution authority (see §8).

Architecture authority: `rmax-ai/architecture` ADR-0012 (declarative purpose-specific dataset
compilation; amended 2026-10-03 — single Jev adapter boundary), ADR-0013 (dataset source registry +
S3 streaming data plane — source boundary), ADR-0010 (ephemeral workspace/cache tier), ADR-0003
(single rmax-side Jev adapter), ADR-0008 (worker boundaries), ADR-0011 (Pydantic v2 boundary
models).

## 1. Purpose and positioning

Given (a) frozen source snapshots and (b) a versioned declarative specification of admissibility,
semantic qualities, coverage, diversity, and provenance requirements, **deterministically produce
an explainable dataset manifest** — and *optionally* materialize the selected bytes.

The product is a compiler, not a curator:

```text
DatasetSpec (declarative intent)
      │
      ▼
frozen SourceSnapshot ──► CandidateCatalog (stable identity + provenance)
      │
      ├── deterministic inspection      (hash, MIME, dimensions, license fields, pHash)
      └── semantic observation          (VLM/provider → typed evidence)
      │
      ▼
atomic predicate evaluation ──► objectives + embeddings
      │
      ▼
portfolio selection (hard constraints / quotas / coverage / diversity / groups)
      │
      ▼
verification ──► BuildManifest ──► optional materializer (local / archive / object URI)
```

First reference consumer: `rmax-ai/cull-audit` (photo-culling evaluation). Source-of-truth chain:

```text
public sources → dataset-sources (SourceSnapshot) → DatasetSpec/compiler → frozen BuildManifest → optional pet materialization → cull-audit
```

## 2. Boundaries (hard refusals)

- **No storage ownership.** The compiler reads frozen SourceSnapshot manifests and referenced
  object URIs. It does not provision buckets, manage lifecycles, mirror datasets, or own
  S3/CDN/credentials. Materialization targets are *destinations*, not managed infrastructure.
- **No provider acquisition** (ADR-0013). Registration/discovery/acquisition/mirroring live in
  `rmax-ai/dataset-sources`; this repo consumes frozen snapshots via thin readers and never
  implements a duplicate acquisition path.
- **No second Jev adapter** (ADR-0003). Public code exposes a provider-neutral **external predicate
  contract**; rmax-side Jev integration reuses `rmax-ai/jev-tool`. This repo never implements a Jev
  wire client.
- **BuildManifest is canonical.** Materialization is optional and replaceable; selection semantics
  never depend on where bytes landed.
- **Git carries specs, manifests, evidence, tiny/generated fixtures** — never large source datasets
  or private photoshoot material.
- **No legal conclusions.** Source-declared license evidence is preserved; redistribution requests
  fail closed on missing/ambiguous metadata. (This is operational policy, not legal advice.)
- **Deterministic authority, probabilistic evidence.** Models may emit typed observations/scores;
  deterministic code owns validation, hard constraints, quotas, final portfolio selection given
  frozen evidence, and provenance.
- **Frozen replay, not live recrawl.** The compiler guarantees byte-identical *replay of frozen
  snapshots* (docs/source-snapshots.md §2). Live upstream recrawl equality is a dataset-sources
  concern (ADR-0013); draft snapshot consumption is exploration mode only.
- **Canonical bytes are normative.** Digests are defined over canonical JSON with pinned float
  quantization, ordering, and normalization (docs/provenance.md §1); volatile fields never enter
  identity.
- **No paid semantic inference** before offline contracts, mock adapters, deterministic selection,
  and provenance/replay tests are green. Initial reference-build semantic spend hard cap: **USD 5**
  (higher only via explicit queue issue).

## 3. Core contracts (v0.1)

All serialized boundaries: **Pydantic v2**, explicit `schema_version`, explicit extra-field policy
(`forbid` unless a versioned extension block), generated JSON Schema.

| Contract | Role |
|---|---|
| `DatasetSpec` | Canonical declarative input (YAML/JSON). |
| `SourceSpec` | One source binding: adapter id, pinned revision/digest, params, license policy. |
| `CandidateAsset` / `CandidateGroup` | Normalized catalog rows: stable identity, revision, URI, checksum?, media type, license/provenance, group_id?. |
| `TechnicalObservation` | Deterministic inspection output (hashes, MIME, dimensions, pHash, basic metadata). |
| `SemanticObservation` | Typed evidence from an observer (subject, count, framing, occlusion, environment, lighting, defects, composition, description). |
| `EvaluationReceipt` | Cache/replay identity: evaluator/model/prompt/schema versions + input refs + output digest. |
| `PredicateResult` / `ObjectiveScore` | Atomic rule outcomes + soft scores with reason codes. |
| `SelectionDecision` | Per-candidate include/exclude + reason path + group membership. |
| `BuildManifest` | Versioned canonical output: spec/source digests, decisions, receipts, provenance graph, verification record. |

Asset/group selection units are first-class: `selection_unit: asset | group`; group-level
predicates, per-group min/max item counts, and group count/distribution constraints are expressible
without domain-specific code. Image-specific fields live under typed extension points
(`observation_schema: image.v1`); the core contracts stay domain-neutral where that costs nothing.

Staged cost reduction (mandatory pipeline order):

```text
enumerate/oversample → license/metadata gate → hash/dedup → cheap technical checks →
semantic observation (only on the reduced pool) → atomic predicates → objectives/embeddings →
diversity/coverage selection → verification → freeze
```

Cache layers (rebuild discipline): source bytes/content identity → observations → predicate/
objective evaluations → selection. Changing only thresholds/weights/quotas/diversity constraints
**must not** force semantic re-inference when compatible frozen evidence exists.

## 4. CLI surface (target)

```text
dataset-compiler spec lint SPEC          dataset-compiler build SPEC
dataset-compiler plan SPEC               dataset-compiler verify BUILD_MANIFEST
dataset-compiler catalog SPEC            dataset-compiler explain BUILD_MANIFEST ASSET_ID
dataset-compiler evaluate SPEC           dataset-compiler materialize BUILD_MANIFEST OUTPUT_URI
```

`plan` surfaces source counts (where cheaply known), evaluator work estimates, cache hits, expected
semantic-call volume, and blockers **before any live model spend**. `verify` performs no hidden
network access.

## 5. Repository layout (target)

```text
dataset-compiler/
  README.md  PLAN.md  pyproject.toml  docs/  specs/examples/  tests/
  src/dataset_compiler/
    cli.py  models/  sources/  inspection/  semantics/  predicates/
    features/  selection/  materialize/  provenance/
```

## 6. Milestones

| M | Exit criterion |
|---|---|
| M0 bootstrap | Public repo + this plan + design corpus + issue graph + first queue triggers. |
| M1 spec | `pets-v1`-class spec validates; `plan` resolves stages offline; malformed specs fail with stable diagnostics. |
| M2 catalog | Pinned public sources freeze to identical catalog digests; revision changes change digests; no provider credentials needed. |
| M3 evidence | Frozen semantic receipts replay offline; quota-only changes skip the observer; malformed model output fails closed. |
| M4 selection | Deterministic selection from frozen inputs; diversity/coverage constraints demonstrably correct naive top-score collapse; groups expressible. |
| M5 manifest | Manifest alone explains each inclusion/rejection; `verify` works offline; materialization replaceable. |
| M6 reference build | Frozen pet corpus handed to cull-audit with traceable licenses; random vs top-score vs constrained comparison reported. |

## 7. Epic/task tree

Task rows carry: scope · depends · deterministic acceptance (abbreviated here; issues carry the
full text). Sizes: S/M/L.

### E1 — DatasetSpec v1 + compile plan (milestone M1)

| id | scope | depends | acceptance |
|---|---|---|---|
| E1.1 | Pydantic v2 models + version envelope + JSON Schema export | — | schema generated + committed; round-trip tests; extra-field policy tests (forbid with named escape) |
| E1.2 | Spec loading (YAML/JSON) + stable diagnostics | E1.1 | valid example loads; malformed/extra/ambiguous specs fail with **stable codes** + paths |
| E1.3 | Predicate/objective/constraint taxonomy + `plan` resolver (`spec lint`, `plan`) | E1.1, E1.2 | `plan` resolves evaluators/stages/counts offline (fixture snapshots), zero paid calls |
| E1.4 | Offline spec fixtures (valid + invalid corpus, incl. `pets-v1`) | E1.1 | fixture corpus committed; every invalid fixture asserts its code |
| E1.5 | CLI wiring `spec lint` + `plan` with deterministic exit codes | E1.2, E1.3 | CLI exit codes asserted in tests; no network |

### E2 — Source catalog + immutable identity (M2)

| id | scope | depends | acceptance |
|---|---|---|---|
| E2.1 | `SnapshotReader` contract + `CandidateAsset`/`CandidateGroup` normalization | E1.1 | contract tests; deterministic ordering; model round-trips |
| E2.2 | `file` + `http` snapshot readers (fixtures, pinned URL) | E2.1 | same frozen snapshot → byte-identical catalog; no-auth path |
| E2.3 | Snapshot + catalog digest verification (fail-closed) | E2.1 | digest mismatch / unfrozen-for-build fails with stable code |
| E2.4 | Thin object reader (streaming/range; file/http/s3) | E2.1 | bounded memory; range reads checked against snapshot checksums |
| E2.5 | Catalog freeze + digest; technical inspection pass (hash verify, MIME, dims, pHash) | E2.2, E2.3 | freeze → digest stable; snapshot change → digest change; pHash deterministic |
| E2.6 | Snapshot consumption contract suite; documented no-credential reference path | E2.2–E2.5 | suite green offline; reference path needs no credentials |

### E3 — Semantic evidence + predicate plane (M3)

| id | scope | depends | acceptance |
|---|---|---|---|
| E3.1 | `SemanticObserver` contract + typed `SemanticObservation` + identity fields | E1.1 | schema-validated outputs; identity fields mandatory |
| E3.2 | Offline/mock observer + receipt/cache semantics | E3.1 | mock receipts replay offline; cache key = all meaning-bearing inputs |
| E3.3 | Deterministic predicate engine over catalog + observations | E1.3, E3.1 | atomic predicates deterministic; reason codes stable |
| E3.4 | External predicate contract (provider-neutral; jev-tool-compatible fixtures; **no Jev client**) | E3.1 | adapter-agnostic fixtures; documented reuse boundary (ADR-0003) |
| E3.5 | ONE bounded reference VLM adapter (after offline battery green) | E3.2, E3.3 | spend-gated; fail-closed on malformed output; identifiers recorded |
| E3.6 | Replay + fail-closed policy tests | E3.2 | quota/weight-only edits do not invoke observer; malformed → explicit evidence error/abstention |

### E4 — Selection, diversity, grouped compilation (M4)

| id | scope | depends | acceptance |
|---|---|---|---|
| E4.1 | Constraint/objective/portfolio models + feasibility validation | E1.3 | infeasible portfolios fail before selection with named constraint |
| E4.2 | Deterministic greedy selector v0.1 + reason codes | E4.1 | byte-stable selection from frozen inputs; replaceable solver interface |
| E4.3 | Diversity features (pHash exact; embedding interface optional) | E4.1 | diversity gain measurably changes selected set |
| E4.4 | Grouped selection (min/max per group; group distribution) | E4.1 | mini-shoot/burst requirements expressible without domain code |
| E4.5 | Collapse-correction tests (naive top-score vs constrained) | E4.2, E4.3, E4.4 | suite proves constraints fix naive collapse on constructed fixture |

### E5 — Build manifest, verify, explain, materialize (M5)

| id | scope | depends | acceptance |
|---|---|---|---|
| E5.1 | Versioned `BuildManifest` + provenance graph | E4.2 | manifest validates against schema; every selected asset has decision + receipt refs |
| E5.2 | CLI `build` + `verify` (offline checksum/replay) | E5.1, E3.6 | `verify` offline over frozen evidence; no hidden network |
| E5.3 | CLI `explain` (per-asset reason path) | E5.1 | each inclusion/rejection explainable from manifest alone |
| E5.4 | Local materializer (replaceable, checksummed) | E5.1 | materialization does not alter selection semantics; checksums verified |
| E5.5 | Optional generic fsspec/object-store materializer (bounded) | E5.4 | only if clean; no infrastructure provisioning; documented as optional |
| E5.6 | End-to-end offline fixture build + replay test | E5.2, E5.3 | deterministic end-to-end: build → verify → explain → materialize on fixtures |

### E6 — Public pet reference build + cull-audit integration (M6)

| id | scope | depends | acceptance |
|---|---|---|---|
| E6.1 | Snapshot intake: frozen pet SourceSnapshot (dataset-sources E7) + oversampled candidate pool | E2.6 | snapshot digest verified; license evidence per asset; pool ≫ target; ≥2 upstream collections where practical |
| E6.2 | Compile reference build with quality/coverage/diversity/group constraints | E6.1, E3.3, E4.2–E4.4, E5.2 | frozen BuildManifest; groups honored where snapshot evidence supports; cache-budget measurement recorded (peak local dataset-cache bytes < full snapshot bytes) |
| E6.3 | Dataset-level evaluation report (random vs top-score vs constrained) | E6.2 | coverage metrics computed; report explains compiler delta |
| E6.4 | Freeze evidence pack + handoff to cull-audit (+ downstream trigger linkage) | E6.3 | source bytes not in git; one canonical provenance path; #136 alignment |
| E6.5 | cull-audit materialization round (downstream, cross-repo) | E6.4 | per cull-audit#17 / dq#136 acceptance; not owned here |

## 8. Execution model (bounded WIP)

- **Planning vs execution authority:** issues in THIS repository are planning state only. Every
  delegated implementation/research/review execution requires its own triggering issue in
  `rmax-ai/delegation-queue` (central queue) — created before delegation, per the standing control
  plane.
- **Dependency waves:** dispatch only tasks whose dependencies have landed; review between waves
  (re-run acceptance independently, one adversarial spot-check). No blind chaining.
- **WIP:** execution capacity is global (one lane at a time set-wide); ready/review lanes are
  capped. Excess items wait in backlog by design.
- **Lanes:** Codex/Droid subscription lanes via `delegateq`; rmax-10 coordinates/reviews; ordinary
  reversible passing work may be handed to external review (ChatGPT) under standing policy.
- **Spend gates:** offline battery green before any live semantic calls; USD 5 initial cap;
  `plan` estimates call volume before spend.

## 9. Minimal-input execution sequence (first waves)

1. **Trigger T-E1** (filed with this bootstrap): E1.1–E1.5 as one bounded first slice (size M).
   Rationale: everything downstream consumes the spec/plan contracts; it is fully offline-testable
   and unlocks E2/E3/E4 in parallel per their deps.
2. **Trigger T-E2** (filed, `blocked_by [T-E1]`): E2.1 → E2.2/E2.3/E2.4/E2.5 → E2.6. Rationale:
   chosen as the second executable slice (not parallel) because snapshot-consumption normalization
   hard-depends on E1's model/envelope conventions; after E1 lands it proceeds offline (file
   fixtures) with the live pet-snapshot leg on the direct rail.
3. **Triggers T-E3…T-E6** (filed with dependency chains): E3 after E1 + frozen catalog contract
   from E2; E4 against frozen fixtures after E1; E5 after E1–E4 (its build/verify path replays E3
   evidence end-to-end and needs the E2 snapshot-consumption contract for its fixture pipeline);
   E6 last (spend-gated; consumes the frozen pet SourceSnapshot from dataset-sources E7). See the
   trigger map on dq#137.

## 10. Risks / open questions (with defaults in force)

| risk / question | default in force |
|---|---|
| Upstream license metadata gaps on public sources | fail closed for redistribution; keep artifact but mark non-redistributable; operator escalation only for ambiguous cases |
| Upstream revision churn (deletion/mutation at providers) | pinning/mirroring policy lives upstream (dataset-sources, ADR-0013); compiler replay is defined by frozen snapshot digests; stale/missing upstream objects surface as `source_unavailable` at inspection |
| Unpinnable collections (Commons categories) | frozen upstream snapshots (dataset-sources); compiler guarantees replay of the frozen snapshot digest only (docs/source-snapshots.md §2) |
| pHash/embedding determinism drift across libs | pin implementations + versions in receipts; diversity features versioned |
| Semantic model output drift | identity (model/prompt/schema/preprocessing) in receipts; new evidence never silently replaces old |
| cull-audit coupling | corpus is a frozen build + optional materialization; no cull-audit logic in this repo |
| Spend creep in reference build | staged reduction + preflight accounting + worst-case reserve + hard cap; resumable budget halt |
| Greedy selector underfilling | explicit `shortfall`/`incomplete` semantics; repair pass; no silent underfill (docs/selection.md §2) |

## 11. Definition of done (this bootstrap)

Public repository; committed PLAN + design corpus + `pets-v1` spec + skeleton; native project epic
tree (parent + E1–E6 + tasks); first central queue triggers filed; discoverability verified
(GitHub App / ChatGPT / control-plane target set); evidence docket + terminal review handoff.
