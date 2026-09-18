# Implementation log template

`docs/features/NNNN-<slug>/03-implementation-log.md` — written **during** the build, not
reconstructed after. This file is what makes an unattended night auditable: the code review
gate audits the Decisions table, and the sign-off package lifts it verbatim into the morning
report.

```markdown
# Implementation log — [Feature Name]

**Spec:** 01-spec.md (rev N, approved YYYY-MM-DD)

## Build notes

| Requirement | Status | Where | Note |
|---|---|---|---|
| [FR1] | done | `file:line` | [1 line if non-obvious] |

## Decisions (ambiguities resolved without the PO)

| # | Ambiguity | Chose | Alternative rejected | Why reversible |
|---|---|---|---|---|
| 1 | [what the brief didn't cover] | [conservative choice] | [the other option] | [why this can be undone cheaply] |

## Deviations from the spec

[Any place the build differs from 01-spec.md, each with reason and re-gate note. "None" if none
— an undocumented deviation fails the code gate.]

## Test command runs

| When | Command | Result |
|---|---|---|
| after FR2 | `npm test` | green |
```

## Rules

- A Decision entry must pass the reversibility test honestly — "Why reversible" is the column
  the code gate audits hardest. If you can't fill it, the decision wasn't yours to make: park
  (pipeline) or ask (interactive).
- Log decisions when they happen; a reconstructed log defeats its purpose and reads like one.
