# Evaluation methodology

The project's central claim: **declarative compilation changes dataset composition measurably and
correctly** vs naive sampling. The reference evaluation (E6.3) tests this on the pet corpus; the
method is general.

## 1. What is evaluated

Given a frozen candidate pool (catalog + evidence) and a target size N:

| arm | selection rule |
|---|---|
| **R — random** | uniform sample of admissible candidates |
| **Q — quality-only** | top-N by utility score (no portfolio constraints) |
| **C — compiled** | full portfolio rules (constraints, quotas, coverage, diversity, groups) |

Metrics are computed **at the dataset level** over observed fields (never on the outcome a model
might produce downstream):

- **Coverage**: distinct-value counts over observed fields (breed groups, settings) + share bounds
  compliance (species 40–60%, environment mixes).
- **Diversity**: minimum pairwise pHash distance; mean pairwise distance; near-duplicate rate.
- **Group integrity**: share of groups satisfying min/max item bounds; burst coherence where
  applicable.
- **Quality retained**: mean utility of selected set (C vs Q gap must be bounded — diversity is
  bought at a declared cost, not free).
- **Admissibility**: 100% of selected items pass hard predicates (precondition; a violation fails
  the run).
- **Resource envelope**: full snapshot bytes vs peak local dataset-cache bytes on the compiled
  arm — the worker path stays bounded (peak dataset-cache < source snapshot; ADR-0010/ADR-0013).

## 2. Protocol

1. Freeze: catalog digest + evidence digests + spec digest recorded before any arm runs.
2. Run R/Q/C over the same frozen inputs (no re-inference between arms).
3. Report per-metric medians over k=5 random seeds for R (Q/C are deterministic).
4. Publish: machine-readable `evaluation.json` + a short human report; both versioned with the
   build manifest.

## 3. Correctness gates vs comparative reporting (E6.3)

**Correctness gates** (pass/fail, checked on the compiled arm C):
- 100% of selected items pass hard predicates; license evidence present for every redistributed item.
- Deterministic replay: rebuild reproduces the same `build_id` (or a recorded version-change).
- Group integrity: selected groups respect min/max item bounds; no invented groups.
- Manifest completeness: decisions exist for every candidate in the frozen pool.

**Comparative reporting** (predeclared hypotheses — REPORTED, not gates):
- H1: coverage(C) ≥ coverage(R) for each covered field.
- H2: diversity min-pairwise(C) > diversity(Q) > diversity(R) in expectation.
- H3: quality gap mean-utility(Q) − mean-utility(C) stays within a predeclared band (default ≤ 0.10).
- Reported as medians + seed distributions (R over k=5 seeds; Q/C deterministic) with honest
  "hypothesis met / not met" statements. An unmet hypothesis is reported as-is — the response is
  never to retune thresholds or metrics (anti-gaming rule §4).

**Run freeze (before any arm executes):** candidate pool digest, admissibility gate, selection unit,
N, seeds, metric formulas, missing-value handling, and the arm implementations are committed; all
arms run on the same frozen pool with comparable units (the compiled arm's group constraints are
not retro-applied to R/Q, and unit differences are disclosed).

## 4. Anti-gaming policy

- The corpus spec is optimized for the declared culling/group/diversity requirements, never for a
  desired downstream model outcome ("do not tune the dataset to manufacture model flips").
- Metric definitions, predeclared hypotheses, and arm implementations are committed before running.
- Any post-hoc change is recorded as a new evaluation version — never silently amended; unmet
  hypotheses are reported honestly rather than retuned away.

## 5. Extensibility

The method applies to future domains (documents, scientific images) by swapping observed fields
and coverage targets; the arm definitions and protocol stay constant.
