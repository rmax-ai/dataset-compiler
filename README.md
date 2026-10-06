# dataset-compiler

Declarative, purpose-specific dataset compilation.

Given frozen source snapshots and a versioned specification of admissibility, semantic qualities,
coverage, diversity, and provenance requirements, **dataset-compiler deterministically produces an
explainable dataset manifest** — and optionally materializes the selected bytes.

```text
DatasetSpec + frozen SourceSnapshot → candidate catalog → deterministic inspection + semantic evidence
            → predicates/objectives → portfolio selection (constraints/quotas/coverage/diversity)
            → verification → BuildManifest → (optional) materialization
```

## What this is / is not

- **Is:** a compiler from declarative dataset intent to a frozen, replayable `BuildManifest`.
- **Is not:** a storage owner (no buckets/CDN/credentials), a scraper zoo, a model, or a curation
  service. It consumes frozen `SourceSnapshot` manifests (`rmax-ai/dataset-sources`, ADR-0013) and
  the object URIs they reference; materialization targets are destinations, not managed
  infrastructure. Provider registration/discovery/acquisition live upstream — never here.
- **Jev boundary (ADR-0003):** public code exposes a provider-neutral *external predicate contract*.
  rmax-side Jev integration reuses `rmax-ai/jev-tool`; this repository never implements a second
  Jev adapter.

## Status

Bootstrap (2026-10-03): plan + design corpus + reference spec (`specs/examples/pets-v1.yaml`) +
skeleton. Implementation proceeds through the epic tree (E1–E6) under the central delegation queue;
see [PLAN.md](PLAN.md).

```bash
# planned CLI surface (v0.1 target)
dataset-compiler spec lint SPEC          # validate a DatasetSpec, stable diagnostics
dataset-compiler plan SPEC               # resolve stages/evaluators/counts + cache hits, no spend
dataset-compiler catalog SPEC            # freeze the candidate catalog (digest)
dataset-compiler evaluate SPEC           # observations + predicates + objectives
dataset-compiler build SPEC              # selection + verification → BuildManifest
dataset-compiler verify BUILD_MANIFEST   # offline verification/replay
dataset-compiler explain BUILD_MANIFEST ASSET_ID
dataset-compiler materialize BUILD_MANIFEST OUTPUT_URI
```

## Documentation

| Document | Content |
|---|---|
| [PLAN.md](PLAN.md) | Contract: milestones, epic/task tree, dependencies, acceptance, waves. |
| [docs/architecture.md](docs/architecture.md) | Boundaries, pipeline, deterministic/probabilistic split. |
| [docs/specification.md](docs/specification.md) | `DatasetSpec` v1: envelope, predicates, objectives, quotas, groups. |
| [docs/source-snapshots.md](docs/source-snapshots.md) | Snapshot consumption, thin readers, immutable identity, worker invariant. |
| [docs/semantic-evidence.md](docs/semantic-evidence.md) | Observers, typed evidence, receipts, external predicates. |
| [docs/selection.md](docs/selection.md) | Constraints, objectives, diversity, greedy v0.1, reason codes. |
| [docs/provenance.md](docs/provenance.md) | Cache keys, builds, replay, explainability. |
| [docs/evaluation.md](docs/evaluation.md) | Dataset-level evaluation methodology. |
| [docs/roadmap.md](docs/roadmap.md) | Milestones and open questions. |

## Development

Python 3.12+, `uv`. Boundary models are Pydantic v2 with explicit schema versions and generated
JSON Schema (ADR-0011).

```bash
uv sync --dev
uv run pytest -q
uv run ruff check .
```
