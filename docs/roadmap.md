# Roadmap

Milestones (exit criteria in PLAN.md §6; deliveries in §7):

| M | name | epics | gate |
|---|---|---|---|
| M0 | bootstrap | — | repo + plan + corpus + issue graph + first triggers |
| M1 | spec | E1 | pets-v1 validates; `plan` offline; stable diagnostics |
| M2 | snapshots | E2 | frozen snapshot replay reproducible; no-credential path |
| M3 | evidence | E3 | offline replay; quota-only edits skip observer; fail-closed |
| M4 | selection | E4 | deterministic; collapse-correction demonstrated; groups |
| M5 | manifest | E5 | manifest explains all; offline `verify`; materialize replaceable |
| M6 | reference build | E6 | frozen pet corpus → cull-audit; evaluation report |

Dependency spine:

```text
E1 ──► E2 ──┐
 │           ├──► E6
 ├──► E3 ────┤
 ├──► E4 ────┤
 └──► E5 ────┘        (E5 needs E4; E6 needs E2–E5)
```

First waves (detail in PLAN.md §9): **T-E1** (spec + plan) and **T-E2** (catalog) are the first two
executable slices; both are offline-first. E3/E4/E5 follow per dependency; E6 is spend-gated last.

## Open questions (defaults in force; revisit at the named milestone)

| # | question | default | revisit |
|---|---|---|---|
| Q1 | Embedding provider for diversity features | optional; pHash is the v0.1 floor | M4 |
| Q2 | Multi-machine determinism of pHash across lib versions | pin implementation + version in receipts | M2 |
| Q3 | Object-store read/materialize (fsspec) inclusion | bounded optional subtask, only if clean | M5 |
| Q4 | Series/group evidence quality in upstream snapshots | snapshot-carried series evidence; reviewed derivations only | M6 |
| Q5 | External predicate provider fixtures beyond offline | fixture provider only until a real consumer needs it | post-M6 |

## Non-goals (v0.1)

Kaggle; provider acquisition/discovery (→ `rmax-ai/dataset-sources`); credentialed sources;
storage/mirror operations; annotation workflows; training; a UI; a second Jev adapter; domain
logic that belongs to consumers (cull-audit).
