# Selection — portfolio compilation

Dataset quality is a **portfolio property**. Selecting individually top-scoring candidates collapses
onto correlated modes (same breed, same setting, near-identical frames). The selector optimizes a
dataset-level objective under hard constraints.

## 1. Model

```text
maximize   Σ utility(c) + λ_div · Σ diversity_gain(c, S) + λ_cov · Σ coverage_gain(c, S)
subject to hard constraints (admissibility),
          quotas (share bounds over observed fields),
          coverage floors (min distinct values),
          diversity floors (pairwise distances),
          group semantics (min/max items, group counts),
          target item count
```

- `utility(c)`: weighted soft objectives (docs/specification.md §6).
- `diversity_gain`: pHash distance (exact, deterministic) and optional embedding distance.
- `coverage_gain`: marginal distinct-value gain over observed fields.
- λ weights are spec-level; changing them must not invalidate frozen evidence.

## 2. Bounded greedy selector v0.1 (deterministic, frozen contract)

The v0.1 selector is a **bounded heuristic with honest failure semantics** — not a complete
optimizer. The frozen contract:

**Ordering.** Groups are ranked by `(group_utility desc, group_id asc)`; candidates within a group
by `(utility desc, asset_id asc)`; asset-mode candidates by `(utility desc, asset_id asc)`.

**Feasibility = necessary conditions only.** At each step, "can still satisfy" is implemented as
cheap COUNT bounds: (a) remaining selectable items can reach the target count; (b) for each quota
minimum, the count upper bound of satisfying candidates is ≥ the required integer count;
(c) coverage floors are reachable in count. It is explicitly NOT a completeness guarantee — the
selector is greedy and may report `shortfall` on a feasible-but-unlucky pool (documented, tested).

**Exact quota arithmetic.** Quota shares convert to integer counts against the target N once:
`min_items = ceil(min_share × N)`, `max_items = floor(max_share × N)`; the denominator is always the
target N (never the achieved count).

**Group mode.** Phase G: admit groups (group-level predicates + reservation bounds); reserve a
group only if `min_items_per_group` can be met from its admissible members under intra-group caps.
Phase M: fill reserved groups with members in ranked order subject to intra-group diversity caps.
**Repair order:** if the target is unmet after the main pass, a second pass tries remaining
candidates/groups in ranked order; then selection stops and reports `shortfall` with per-constraint
diagnosis. Group reservation never blocks later repair within the documented order.

**Bounds.** O(pool × target) steps, monotone selections; no randomness, no wall-clock; deterministic
tie-breaks as above. Same frozen inputs → byte-identical `BuildManifest`.

**Outcomes.** `complete` (target met) | `shortfall` (target unmet; marked `incomplete` in the
manifest with the binding constraint reported) | `infeasible` (detected at plan/compile time where
computable, else as final shortfall). No silent underfill.

```text
S ← ∅ ; reserved ← ∅
# phase G (group mode only): reserve groups by rank while reservation bounds hold
# phase M / asset mode: iterate ranked candidates; pick c* = first feasible with
#   marginal_objective(c*) = utility(c*) + λ_div·diversity_gain + λ_cov·coverage_gain
# repair pass over remaining candidates; then emit decisions + status
```

The selector implements a frozen `Selector.select(spec, catalog, evidence) → SelectionResult`
interface so later ILP/submodular solvers can replace the greedy implementation without touching
the spec contract (solver version participates in the selection cache key).

## 3. Diversity features

| feature | v0.1 | notes |
|---|---|---|
| pHash (64-bit) | required | Hamming distance; exact and cheap; computed at inspection; single effective floor (portfolio only) |
| Embedding | optional | only when semantic embedding evidence exists; cosine distance; versioned |
| Group spread | required | per-group caps prevent single-group dominance |
| Novelty | derived | `novelty(c) = 1 − freq(class(c)) / pool_size` over a declared class field (deterministic; available to objectives as `metadata.novelty`) |

Diversity floors are pairwise constraints within the selected set (e.g. `phash_min_distance: 8`).
The greedy adds candidates only if the floors remain satisfiable; near-duplicate candidates are
bypassed with reason `DIVERSITY_FLOOR`.

## 4. Reason codes

Every candidate in the manifest carries a decision:

```yaml
decision:
  asset_id: "…"
  outcome: selected | rejected
  primary_reason: PREDICATE_FAILED | EVIDENCE_INDETERMINATE | QUOTA_INFEASIBLE | DIVERSITY_FLOOR |
                  COVERAGE_SATURATED | NOT_SELECTED_TARGET_REACHED | SELECTED
  detail: {predicate_id: near_duplicate, distance: 4}   # structured, stable keys
  group_id: "…"                                         # when grouping active
```

Reason taxonomy is closed (documented enum). `EVIDENCE_INDETERMINATE` carries the evidence state
(error/abstained/unavailable) in `detail`. `explain` renders any decision from the manifest alone.

## 5. Collapse demonstration (acceptance fixture, E4.5)

A constructed fixture (near-identical high-utility cluster + diverse lower-utility candidates)
must show:

| mode | expected outcome |
|---|---|
| random sampling | coverage ≈ baseline |
| top-score (no portfolio constraints) | collapses onto the high-utility cluster; coverage drops |
| constrained/diversity-aware | recovers coverage/diversity while utility stays within a declared band |

This test is the project's core claim in miniature and is part of E4 acceptance.

## 6. Replaceability

- The solver is an interface with a default greedy implementation; selection must remain
  reproducible from (spec digest, catalog digest, evidence digests, solver version).
- Solver version participates in the selection cache key.
- Future solvers (ILP, submodular) are additive; spec semantics do not change.
