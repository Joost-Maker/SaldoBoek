# Sign-off package template

`08-signoff.md` is the morning read: five minutes, then Joost knows exactly what happened and
what (if anything) he must do. Written by dev-go in Phase 8, for both shipped and parked runs.

```markdown
# Sign-off — [Feature Name] (NNNN-<slug>)

**Status:** SHIPPED | PARKED (<reason>) | READY FOR REVIEW (manual merge policy)
**Date (UTC):** YYYY-MM-DDTHH:MM:SSZ
**Vault item:** [DEV/<name>.md]
**Branch / commit:** [squash commit sha on <working-branch>, or feat/NNNN-<slug> pushed]
**Rollback:** tag `pre-NNNN-<slug>` (or: nothing merged)
**Vault:** updated | not updated — reconcile in morning review
**Tests added (accretion):** [N cases in <files> — or "none: <reason>"]

## What shipped / state when parked

[3–6 sentences. For parked runs: which phase, what is done, what is not.]

## Gate results

| Gate | Verdict | Artifact |
|---|---|---|
| Spec review | approved (rev N) | 02-spec-review.md |
| Bug hunt | N 🔴 · N 🟠 · N 🟡 · N 🟢 (round N) | 05-bughunt-report.md |
| Project tests | green (`<test command>`) | — |
| Code review | approved | 07-code-review.md |

## Assumptions made (from the decision log)

[Every Decisions-table entry from 03-implementation-log.md, one line each: choice + the
alternative not taken. "None" if the brief covered everything.]

## What to eyeball

[1–3 concrete things worth checking in the live app — the spots where a human eye still beats
the protocol. For parked runs: the recommended next step instead.]

## Backlog candidates (capture via dev-po)

[🟡/🟢 bugs left open, out-of-scope discoveries, follow-up ideas — one line each with severity.
These were deliberately NOT created in the vault overnight.]
```
