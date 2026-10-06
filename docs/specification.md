# DatasetSpec v1 — specification

A `DatasetSpec` declares the desired dataset. It is validated at the boundary with Pydantic v2
(ADR-0011), carries an explicit `spec_version`, and describes **what** the dataset must satisfy —
not imperative pipeline steps. Evaluators/readers may be named explicitly where a source or
observer must be pinned.

## 1. Envelope

```yaml
spec_version: "1"                 # required; major-versioned contract
spec_id: pets-v1                  # stable id (referenced by BuildManifests)
metadata:
  name: "Pet reference corpus v1"
  purpose: "Photo-culling evaluation corpus for rmax-ai/cull-audit"
  maintainers: ["rmax-ai"]
  created: "2026-10-03"
  tags: [pets, cull-audit, reference]
```

Field policy: **extra fields are forbidden** at every level except inside explicit `extensions:`
blocks, which are versioned and namespaced (e.g. `image.v1`). Unknown keys outside extensions are
load errors with stable diagnostics.

## 2. Sources

```yaml
sources:
  - source_id: pets_snapshot
    snapshot:
      uri: "s3://rmax-ai-datasets-source/sources/pets/snapshots/sha256-<digest>/manifest.json"
      digest: "sha256:<digest>"   # content digest of the snapshot manifest; source identity
      frozen: true                # builds require frozen snapshots
    reader: auto                  # thin reader resolved from URI scheme: file|http|s3
    params: {}                    # reader-level options only (timeouts, bounded concurrency)
    license_policy:
      allow: [CC0, PD, CC_BY, CC_BY_SA]   # redistribution-relevant allowlist
      require_evidence: true              # fail closed if absent
```

- `sources` bind **frozen `SourceSnapshot` manifests** produced by `rmax-ai/dataset-sources`
  (ADR-0013): consumption + digest verification + provenance passthrough. Provider
  registration/discovery/acquisition/mirroring live upstream, not here.
- Each snapshot is pinned by content digest (`snapshot.digest`), so catalogs are reproducible; a
  changed snapshot changes the catalog digest by construction. Draft (`frozen: false`) snapshots
  are exploration-only.
- Compiler-side `params` are reader-level only — no provider parameters in a spec.
- `license_policy` applies at the catalog gate; per-asset evidence is always preserved regardless
  of policy outcome.

## 3. Selection units and groups

```yaml
selection:
  unit: group                     # asset | group
  group:
    group_by: [source_id, collection]   # catalogs may carry group_id
    min_items_per_group: 4
    max_items_per_group: 12
    min_groups_selected: 8
    max_groups_selected: 12
    item_order: capture_order            # optional, when provider supplies ordering
  targets:
    items: 90                     # portfolio target (after grouping semantics)
    oversample_factor: 20        # enumerate ≫ target before reductions
```

- `unit: asset` selects individual candidates; `unit: group` selects **coherent groups**
  (mini-shoots/bursts/series) and then per-group item membership, using the same atomic machinery.
- Group-level predicates evaluate aggregate/metadata properties of the whole group; item-level
  predicates evaluate within-group members (e.g. "at most 40% near-duplicates inside a group").
- Group constraints are domain-neutral: any catalog exposing `group_id` (or a `group_by` rule over
  catalog fields) is expressible.

## 4. Admissibility: hard predicates

```yaml
admissibility:
  hard:
    - id: licensed_for_redistribution
      scope: item            # item vs portfolio — see §12 (rule layer)
      rule: license_in {allow}
    - id: min_dimensions
      scope: item
      rule: width >= 1200 and height >= 800
    - id: sane_aspect
      scope: item
      rule: 0.5 <= (width/height) <= 2.2
    - id: exact_duplicate
      scope: portfolio       # selected-set check, evaluated once at portfolio phase
      rule: content_sha256 not_in selected.content_hashes
```

Hard predicates are **deterministic** and evaluated by the predicate engine, respecting their
`scope` (item scope = pre-selection; portfolio scope = selected-set checks during selection).
Near-duplicate control lives ONLY in the portfolio diversity floor (§7) — there is exactly one
effective pHash floor per spec. A candidate failing an item-scope predicate is rejected with that
predicate's id as the primary reason; portfolio-scope violations are reason-coded at selection time.

## 5. Semantic predicates

Semantic predicates consume typed observations (§docs/semantic-evidence.md) — they never call a
model inline:

```yaml
admissibility:
  semantic:
    - id: primary_subject_is_pet
      scope: item
      rule: observation.subject.primary in {cat, dog}
    - id: plausibly_single_subject
      scope: item
      rule: 1 <= observation.subject.count <= 3
    - id: not_artwork
      scope: item
      rule: observation.medium == photograph and observation.artwork_score < 0.5
    - id: acceptable_visibility
      scope: item
      rule: observation.occlusion.severity <= moderate
            and observation.defects[motion_blur].severity <= mild
```

Rules are expressions over the field registry (§12). Semantics of missing values are fixed by §12
(three-valued logic): absent observation fields make a rule `indeterminate` (never silently
skipped); absent defect entries read as `none` severity. `indeterminate` on a hard predicate
rejects with the evidence reason recorded (see docs/semantic-evidence.md §5). Unknown fields fail
at rule-compile time.

## 6. Soft objectives

```yaml
objectives:
  - id: quality
    kind: weighted_sum
    weights:
      observation.quality.overall: 0.6
      observation.composition.subjective: 0.2
      technical.resolution_score: 0.2
  - id: utility
    kind: weighted_sum
    weights:
      quality: 0.7               # nested objective reference (DAG, topological order)
      metadata.novelty: 0.3
    missing_term_policy: renormalize    # default: drop missing terms, renormalize weights
    default: 0.0                        # used when no term is available
```

Objectives produce per-candidate utility used by the selector. Nested references form a DAG
(evaluated in topological order; cycles are compile errors). When a weighted term is missing
(`indeterminate` evidence), the default policy **renormalizes** the remaining weights; each
objective declares a numeric `default` used when nothing is available. `metadata.novelty` is a
derived feature: reciprocal class frequency within the frozen candidate pool (deterministic, defined
in docs/selection.md §3). Weights are spec-level and re-tuning them must **not** invalidate frozen
observations/predicates (cache layer rule).

## 7. Coverage and distribution constraints

```yaml
portfolio:
  quotas:
    species:
      cat: {min: 0.4, max: 0.6}              # share bounds (explicit grammar; see §12)
      dog: {min: 0.4, max: 0.6}
    environment:
      indoor: {min: 0.25, max: 0.5}
      outdoor: {min: 0.25, max: 0.5}
      studio: {min: 0.0, max: 0.15}
  coverage:
    - id: breeds
      field: observation.subject.breed_group
      min_distinct: 8
    - id: settings
      field: observation.environment.setting
      min_distinct: 3
  diversity:
    phash_min_distance: 8            # the ONLY effective pHash floor (hard predicates must not restate it)
    embedding:
      enabled: true                  # optional; skippable without semantic loss
      min_cosine_distance: 0.15
      weight: 0.25
```

- Quotas express **dataset-level** share bounds (hard portfolio constraints). Share bounds convert
  to integer counts against the target N with documented rounding (min → ceil(min·N),
  max → floor(max·N)); infeasible combinations are caught at plan time where computable and are
  `shortfall` outcomes at selection time — never silent underfill (docs/selection.md §2).
- Coverage expresses minimum distinct values over observed fields.
- Diversity is a pairwise-repulsion objective with floors; all three are portfolio properties that
  per-item top-scoring cannot satisfy (see docs/selection.md for the collapse example).

## 8. Verification policy

```yaml
verification:
  level: digest                 # digest (always) | bytes (when frozen/available bytes exist)
  verify_checksums: true
  recheck_license_evidence: against_snapshot   # snapshot replay; never live pages
  sample_reinspection:
    enabled: true
    sample_size: 8              # independent pass over selected items (manual or observer)
    method: seeded_random       # sample selection method recorded (with seed) in the verification record
  fail_closed_on_ambiguity: true
```

Verification levels are explicit: **digest**-level verification (schema + digest recomputation over
the frozen evidence pack) is always available offline; **bytes**-level adds checksum checks when
frozen/available bytes exist and reports `unverifiable` (distinct from pass/fail) when they do not.
Every verification run writes an immutable verification record (docs/provenance.md §5).

## 9. Provenance requirements

```yaml
provenance:
  retain: [snapshot_digest, source_uri, source_revision, license_evidence, technical_observations,
           semantic_receipts, predicate_results, selection_decisions]
  record_evaluator_identity: true     # model / prompt / schema versions on every receipt
  allow_evidence_reuse: true          # rebuilds may consume compatible frozen evidence
```

## 10. Output / materialization policy

```yaml
output:
  build_manifest: manifests/pets-v1.build.json
  materialization:                     # OPTIONAL; absence is valid (manifest-only build)
    adapter: local                     # v0.1: local destinations only (fsspec/object-store deferred)
    target: "file:///data/datasets/pets-v1"
    max_edge: 1536
    format: jpeg
    quality: 85
    max_total_bytes: 45000000
```

Materialization never alters selection semantics; a build may be compiled manifest-only and
materialized later from the frozen manifest. Materialization records are linked artifacts, separate
from the canonical build digest (docs/provenance.md §4).

## 11. Budgets (compile-time guards)

```yaml
budgets:
  max_semantic_calls: 1200           # hard ceiling; plan surfaces expected volume
  usd_estimate_cap: 5.00             # initial reference-build cap (E6)
  price_table: reference.v1          # pinned per-call price table id used for estimates
  worst_case_reserve_per_call: 0.01  # USD reservation, so the estimate can never undercount a call
```

`plan` must compute a **preflight accounting** before any live call:
`expected_calls = candidates after staged reduction (group-aware) × calls-per-asset`, then
`reserved = expected_calls × worst_case_reserve_per_call`; cached calls count as zero. A run halts
BEFORE issuing any call that could breach the cap and writes a resumable `budget_halt.json`
(receipt-equivalent) so the build can continue after a cap increase. Group-level staging applies:
members of groups that cannot qualify are not observed.

## 12. Rule expression layer (v1) & value semantics

The expression layer is deliberately small, typed, and versioned (`rules_version: "1"`). It is
pinned by E1 before `pets-v1` can validate.

**Grammar (informal; E1 freezes the formal form):**

```text
expr      := or_expr
or_expr   := and_expr ('or' and_expr)*
and_expr  := not_expr ('and' not_expr)*
not_expr  := 'not'? cmp
cmp       := term (op term)?                # op ∈ {==, !=, <, <=, >, >=, in, not_in, not_in_set}
term      := field | literal | set | '(' expr ')' | agg
field     := path['.' path]* ('[' ident ']')*      # registry-validated
set       := '{' literal (',' literal)* '}'
agg       := identifier '(' field ')'       # closed set per version, e.g. count(), share()
```

**Phases (where each rule kind runs):**

| phase | runs on | examples |
|---|---|---|
| compile | spec + registry only | field/type checks, DAG checks, range grammar |
| catalog | candidate catalog rows | license gate, dimensions, MIME |
| evidence | candidate + observations | subject/quality/defect predicates |
| portfolio | selected-set state | exact-duplicate checks, diversity floors, quotas, coverage |

**Field registry (v1):** every expression field resolves against the registry assembled from
(`technical.*`, `metadata.*`, `observation.*` for the active `observation_schema`, derived
`features.*`). Registry entries declare: name, type (`int|float|bool|enum|string|severity`), units,
and phase availability. Unknown or phase-misplaced fields are compile errors
(`SPEC_RULE_UNCOMPILABLE`) — never silent skips.

**Value semantics:**

- **Severity** is an ordered enum: `none < mild < moderate < severe`. Comparisons use that order.
- **Defects accessor:** `defects[kind]` yields the highest severity among entries with that kind;
  absent kind → `none`. `defects[kind].severity` is therefore total (never missing).
- **Absent fields make rules `indeterminate`** (three-valued logic: a conjunction containing
  `indeterminate` and no `false` is `indeterminate`; `false` dominates). Hard predicate
  `indeterminate` → candidate rejected (reason `EVIDENCE_INDETERMINATE`); soft objective terms use
  the objective's missing-term policy (§6).
- **Quota shares** use the explicit grammar `{min: <float>, max: <float>}`, `0 ≤ min ≤ max ≤ 1`;
  conversion to integer counts against target N is defined in §7.
- **`license_in {allow}`** resolves against the union of source `license_policy.allow` sets at
  catalog phase; per-asset absent evidence → `indeterminate`, which fails closed for
  redistribution (`fail_closed_on_ambiguity`).
- **Objective references** (`quality: 0.7` where `quality` is another objective id) form a DAG.

## 13. Diagnostics

`spec lint` emits stable machine-readable diagnostics: `{code, path, message, hint}`.

| code | meaning |
|---|---|
| `SPEC_YAML_INVALID` | YAML/JSON parse failure |
| `SPEC_UNKNOWN_FIELD` | unknown key outside `extensions` |
| `SPEC_VERSION_UNSUPPORTED` | unsupported `spec_version` |
| `SPEC_SOURCE_PARAMS_INVALID` | snapshot/reader params invalid |
| `SPEC_SNAPSHOT_UNFROZEN` | build requested from a non-frozen (draft) snapshot |
| `SPEC_RULE_UNCOMPILABLE` | predicate/objective expression invalid or references unknown field |
| `SPEC_BUDGET_MISSING` | semantic objectives present without a budget ceiling |
| `SPEC_INFEASIBLE_TARGETS` | declared targets cannot be satisfied under constraints (checked when catalog known) |

## 13. Instance example

See [../specs/examples/pets-v1.yaml](../specs/examples/pets-v1.yaml) — the realistic reference spec
used by milestone M1 acceptance and the E6 reference build.
