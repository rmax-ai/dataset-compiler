# Semantic evidence and the predicate plane

Semantic observation turns an asset into a **typed, reusable intermediate representation**. Models
never make the final dataset decision: deterministic code does, over frozen evidence.

## 1. Observer contract

```python
class SemanticObserver(Protocol):
    observer_id: str          # e.g. "mock.v1", "vlm.<provider>.<model>.v1"
    observation_schema: str   # e.g. "image.v1"

    def observe(self, asset: CandidateAsset, bytes_ref: BytesRef) -> ObservationResult: ...
```

`ObservationResult` = validated `SemanticObservation` + `EvaluationReceipt` (identity/cache
metadata). Observers are invoked only for the reduced pool (staged cost reduction; see
docs/architecture.md §3).

## 2. Typed observations (image.v1)

```yaml
observation_schema: image.v1
subject:    {primary: cat, count: 2, breed_group: "domestic shorthair", confidence: 0.91}
framing:    {kind: close_up, centeredness: 0.72, cropped_subject: false}
occlusion:  {severity: none, parts: []}
pose:       {visibility: good, notes: "sitting"}
environment:{setting: indoor, background_busy: 0.3, location_guess: "living room"}
lighting:   {quality: good, direction: natural_window, harsh_shadows: false}
quality:    {overall: 0.74, sharpness: 0.8, noise: 0.1, exposure: good}
composition:{subjective: 0.66}     # free-subjectivity score (model judgment, 0..1)
defects:    [{kind: motion_blur, severity: mild}]
medium:     photograph          # photograph | artwork | screenshot | other
artwork_score: 0.03             # illustration/cartoon likelihood
description: "A tabby cat sitting on a windowsill in daylight."
```

- Every field is schema-validated (`image.v1`); malformed observer output **fails closed** into an
  explicit evidence error for that asset (never a silent default).
- `defects` entries use kinds from the closed set {`motion_blur`, `noise`, `overexposure`,
  `underexposure`, `watermark`, `occlusion`, `other`}; severity is the ordered enum
  `none < mild < moderate < severe` (docs/specification.md §12).
- The observation is cached as evidence keyed by the receipt (§4); predicates are evaluated later
  and repeatedly against it without re-invoking the observer.
- Domain-neutral core: the observation envelope (`observer_id`, schema, asset ref, status,
  abstention reason) is domain-independent; typed payloads live behind `observation_schema`.

## 3. Predicates

Two deterministic layers operate on frozen inputs:

1. **Atomic predicates** — rules over catalog/technical/observation fields. Evaluated by the
   predicate engine; each yields `PredicateResult{predicate_id, outcome, reason, evidence_refs}`.
   Stable reason codes only (`min_dimensions`, `phash_distance`, …); no prose in selection logic.
2. **External predicates (provider-neutral)** — a contract for delegating *text-classification-ish*
   atomic rules to an external provider. Versioned envelopes (Pydantic; `contract_version: "1"`):

```yaml
request:
  contract_version: "1"
  rule_id: "…"                # the calling predicate
  schema_id: "external.text.v1"
  input: {kind: text | observation_field, value: "…" | "<jsonpath value>"}
response:
  contract_version: "1"
  rule_id: "…"
  outcome: label | abstained | error      # never a dataset decision
  label: "…"                  # required iff outcome=label
  confidence: 0.0-1.0         # optional
  receipt: {provider_id, model, model_revision, prompt_sha256}   # required
```

   The calling rule maps labels to three-valued truth (`true`/`false`/`indeterminate`):
   `label ∈ declared_true_labels` → true; `abstained` → indeterminate; `error` → indeterminate
   (and, per the rule's `on_unavailable`, at most rejects — never admits). **ADR-0003 boundary:**
   rmax-side integration satisfies this contract through `rmax-ai/jev-tool`; this repository ships
   **no Jev wire adapter** and no provider SDK. Contract fixtures (request/response examples,
   including abstain/error) are consumed by the rmax-side adapter to prove implementability.

## 4. Receipts and caching

```yaml
receipt:
  receipt_id: sha256:...            # digest of EXACTLY the identity fields below
  evaluator: {kind: semantic_observer, observer_id: vlm.x.y.v1, model: "…", model_revision: "…"}
  prompt:    {prompt_id: "image-observe-v3", prompt_sha256: "…"}
  schema:    {observation_schema: image.v1, schema_sha256: "…"}
  preprocessing: {version: "…", params_sha256: "…"}   # decode/resize/normalize pipeline identity
  requested_fields: ["subject.primary", "quality.overall", …]
  input:     {asset_ref: "…", content_sha256: "…"}
  status: ok | error | abstained | unavailable        # recorded, NOT part of receipt_id
  output_sha256: "…"                                  # recorded, NOT part of receipt_id
  execution_attempt:                                  # linked record, never identity
    {started_at: "…", host: "…", run_id: "…", attempts: 1}
```

`receipt_id` covers **exactly** evaluator + prompt + schema + preprocessing + requested_fields +
input-content identity. `status`, `output_sha256` and the execution attempt are recorded values but
are excluded from `receipt_id` (outputs are identified separately; attempts are linked records).

Cache key = **all meaning-bearing inputs**: schema version, observer/model identity, prompt digest,
preprocessing version, requested observation fields, source content/revision. Disallowed in keys:
wall-clock, hostname, run id. Execution attempts (timestamps, host, run) are recorded as **linked
attempt records** — never part of receipt identity.

Rebuild semantics:

- Changing only quotas/weights/thresholds/diversity constraints → **no observer calls**
  (observations and predicate-compatible evidence are reused). Enforced by a counter-based test
  (a counting observer harness must record zero calls for quota-only edits).
- Re-running an evaluator after a model/prompt change → new receipts; prior evidence retained;
  builds record which receipts they consumed (no silent overwrite).
- Compatibility: evidence is reusable only when it matches on **content digest + schema +
  evaluator/model revision + prompt digest + preprocessing + requested fields**; otherwise the run
  reports `EVIDENCE_INCOMPATIBLE` and (budget permitting) schedules re-observation.

## 5. Failure model (fail-closed policy)

Evidence states — exactly four: `ok` | `error` (malformed/invalid output, parse failure) |
`abstained` (observer declines to judge) | `unavailable` (provider unavailable/timeout after bounded
retries/rate-limited). Predicate truth is three-valued: `true` | `false` | `indeterminate`.

Truth table mapping (uniform across hard and semantic predicates):

| evidence state | predicate term | rule result |
|---|---|---|
| ok | evaluated | true / false |
| error / abstained / unavailable | — | indeterminate |
| any | any false conjunct | false (false dominates) |

Semantics: hard-predicate `indeterminate` → **reject** with stable reason
`EVIDENCE_INDETERMINATE` (the evidence state is recorded in the reason detail). Soft-objective
terms: missing terms use the objective's missing-term policy (renormalize by default;
docs/specification.md §6); `indeterminate` never imputes a positive value. External-predicate
rules declare `on_unavailable: reject | abstain` (default reject for hard predicates) — **neither
option may admit a candidate**.

Group aggregation (when a predicate is evaluated at group scope): `aggregation: all | any |
fraction(p)` (default `all`); aggregation of `indeterminate` follows the same three-valued logic
(`all` → indeterminate if no member is false but some are indeterminate). The aggregation mode is
recorded per rule.

Other failure modes:

| condition | behavior |
|---|---|
| timeout/rate limit | bounded retries with jitter; each attempt receipted; exhausted → `unavailable` |
| provider identity mismatch (cache hit but different model revision) | treated as different evidence (new receipt) |
| external predicate provider unavailable | per `on_unavailable`; hard rules never admit |

## 6. Spend discipline

- `plan` computes the preflight accounting (docs/specification.md §11): expected semantic-call
  volume from staged reduction (group-aware) and the cache-hit map, with a worst-case reserve per
  call, **before** any call.
- Budgets (`max_semantic_calls`, `usd_estimate_cap`) are hard ceilings; a run halts BEFORE any call
  that could breach the cap and writes a resumable `budget_halt.json`.
- Reference build (E6): initial cap USD 5; raise only via an explicit queue issue.
- Group-level staging: members of groups that cannot qualify under their constraints are not
  observed at all.
