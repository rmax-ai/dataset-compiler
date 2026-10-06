# Provenance, caching, and replay

Every artifact — candidate, observation, decision, build — has stable, content-addressed identity.
The compiler must be able to answer: *why is this asset in this dataset, and can I rebuild the
exact same dataset from frozen inputs?*

## 1. Identity chain

```text
source pin (revision)
   └─ CandidateCatalog digest      (normalized catalog, deterministic order)
        └─ per-asset content identity (sha256 when bytes present; else provider id + metadata)
             └─ TechnicalObservation digest
             └─ SemanticObservation + EvaluationReceipt digest
                  └─ PredicateResult / ObjectiveScore digests
                       └─ SelectionDecision digest
                            └─ BuildManifest digest  ← canonical frozen output
```

Rules:

- **Canonical bytes (normative):** `json.dumps(value, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False, allow_nan=False)` encoded UTF-8. Floats are quantized to **6 decimal places**
  before hashing; NaN/Infinity are rejected at validation (never hashed). Arrays use the order
  defined per artifact (e.g. candidates in catalog order, receipt ids sorted). URIs are normalized
  (lowercased scheme/host, no default ports, no trailing-ambiguity); local paths are POSIX-relative
  to a declared root. Library/runtime versions that affect any digest (pHash, hashing, JSON) are
  pinned and recorded.
- No volatile fields (timestamps, host, run ids) in any digest input. Timestamps appear only in
  informational/attempt fields explicitly marked non-identity.
- Digests are recorded everywhere they are consumed: a `BuildManifest` is self-contained — a
  verifier needs only the manifest + the frozen evidence pack (and bytes, for bytes-level checks).

## 2. Cache layers

| layer | key includes | invalidation |
|---|---|---|
| source bytes / catalog | snapshot digest + reader version + params digest | snapshot change; reader change |
| observations | + inspector/observer/model/prompt/schema identity + content hash | evaluator/model/prompt/schema change |
| predicate/objective evaluations | + definitions digest (rules, thresholds, weights) | rule/threshold/weight change |
| selection/build | + spec digest (selection-relevant parts) + solver version | spec/solver change |

**Load-bearing rule:** quota/weight/diversity edits reuse compatible frozen observations and
receipts; the semantic observer is not re-invoked. This is enforced by a receipt-compatibility
check, not by convention, and is acceptance-tested (E3.6).

## 3. EvaluationReceipt

```yaml
receipt_id: sha256:…            # digest of identity block
evaluator: {observer_id/model/model_revision | inspector_id/inspector_version | solver_id/version}
prompt:   {prompt_id, prompt_sha256}        # when applicable
schema:   {observation_schema, schema_sha256}
input:    {asset_ref | catalog_ref, content_sha256 | revision}
output_sha256: …
status: ok | error | abstained
```

Receipts are append-only evidence. Re-running an evaluator adds receipts; it never rewrites old
ones. Builds record the receipt ids they consumed, so "which evidence produced this dataset" is a
manifest query, not archaeology.

## 4. BuildManifest (canonical output)

```yaml
manifest_version: "1"
build_id: sha256:…                 # digest over the frozen CORE manifest (below); verification +
                                   # materialization records are LINKED artifacts, excluded here
core:
  spec: {spec_id, spec_version, spec_sha256}
  sources: [{source_id, revision | snapshot_digest, catalog_digest}]
  counts: {candidates, admitted, selected}
  selection: {unit, solver_id, solver_version, targets, actual, status: complete | incomplete}
  decisions:                       # ONE entry per candidate in the frozen evaluated pool
    - {asset_id, group_id?, outcome: selected | rejected, primary_reason, detail?, evidence_refs?}
  coverage: {…observed distribution summaries…}
  diversity: {phash_min_pairwise, embedding_metric_summary?}
  budgets: {semantic_calls, estimated_usd, actual_usd}
linked:
  verification: {…immutable verification record ids…}
  materialization: {performed: false} | {target, counts, per_item_checksums…}
```

- `decisions` covers **every candidate** in the frozen pool, including gate-rejected ones
  (evidence refs present only where observations exist) — this is what makes `explain` total over
  the manifest.
- Manifest-only builds are complete deliverables (`materialization.performed: false`).
- An **incomplete** build (shortfall against declared targets) is marked `selection.status:
  incomplete` with per-constraint diagnosis and is not a successful handoff (PLAN.md §7 E6).
- Materialization records are descriptive additions; they never change selection semantics or the
  core digest (materialization is a separate artifact layer).

## 5. Replay and explainability

- `verify BUILD_MANIFEST`: verification **levels** are explicit. Level `digest` (always, offline):
  schema validation + digest recomputation over the frozen evidence pack. Level `bytes` (when
  frozen/available bytes exist): checksum verification. Results are `pass` | `fail` |
  `unverifiable` (e.g. `UNVERIFIABLE_MISSING_EVIDENCE`) — `unverifiable` is never silently a pass.
  Each run emits an **immutable verification record** (levels exercised, inputs, result, sample
  method + seed for reinspection). **No network.**
- `explain BUILD_MANIFEST ASSET_ID`: renders the full why-path from the manifest + frozen evidence
  pack: source → license evidence → technical observations → semantic receipt(s) → predicate
  outcomes → objective scores → selection decision (selected/rejected + reason + neighbors used for
  diversity floors). Total over all candidates because decisions cover the whole frozen pool (§4).
- Rebuild: `build` against the same spec + frozen evidence must reproduce the same `build_id`;
  divergence is a defect (or an explicitly recorded evaluator/solver version change).

## 6. Redaction and safety

- Manifests reference URIs; they never embed credentials or private paths.
- License evidence is preserved verbatim (with URLs); no legal interpretation is stored.
- Private photoshoot material must never enter public artifacts (policy, tested by scan in the
  reference pipeline).
