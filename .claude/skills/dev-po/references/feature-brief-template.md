# Feature Brief template

Written into the **DEV item note body** in the vault (below the frontmatter, replacing the
`## Description` stub; keep the `## Log` section). The brief is the contract for an unattended
pipeline run — at 3am it is the only voice of the PO in the room. The note body holds only the
brief (plus the Log); everything downstream lives in the repo.

```markdown
# Feature Brief — [Feature Name]

**Date:** YYYY-MM-DD
**Author:** Joost (PO)
**Priority:** High / Medium / Low
**Scope:** One-night (buildable + verifiable in a single pipeline run)

---

## What and why

[1–3 sentences: what this does and why it serves the mission]

---

## User story

As a [user], I want to [do something], so that [outcome].

---

## Functional requirements

- [ ] [Specific, testable requirement]
- [ ] [Specific, testable requirement]

## Out of scope (load-bearing — the pipeline may not cross this line)

- [Related thing explicitly NOT included]

---

## Acceptance criteria

Done when (Given/When/Then with concrete values — phase 4 turns each into a permanent
automated test):
- [ ] Given [state/setup], when [action], then [observable result]
- [ ] Given [state/setup], when [action], then [observable result]
- [ ] `manual:` [only for genuine taste/feel criteria — these go to "What to eyeball"]

---

## Ambiguity guidance

- Delegated (decide conservatively + log): [e.g. exact copy, spacing, naming]
- Must park: [e.g. anything touching stored data formats, localStorage schema]

---

## Known constraints or dependencies

[Architecture rules, modules to preserve, data formats, external services]

## Notes for Programmer

[Rough ideas, references, prior discussion — optional]
```

## GO-readiness checklist

Refinement isn't done until every box is honestly checkable. An unchecked box = a parked or
wrong run.

- [ ] Every acceptance criterion is **Given/When/Then with concrete values** — it should read
      like the test it will become. Can't phrase it that way? Rewrite it, or mark it
      `manual: <reason>` honestly (sparingly — DOM state is automatable, taste is not).
- [ ] **Out of scope** has at least one real exclusion (empty = scope-creep license).
- [ ] **One-night-sized** — if build + protocol + hunt + fixes won't fit one run, split the
      brief now; Joost chooses the seams.
- [ ] **Ambiguity guidance** filled: what's delegated, what must park.
- [ ] No acceptance criterion depends on subjective judgement ("looks good", "feels fast")
      unless Joost explicitly moves it to "What to eyeball" territory — the pipeline can't
      verify taste.
- [ ] The project's `Test command` exists and was green at last run (check Project config;
      without it, `dev-go` will refuse the autonomous run).
