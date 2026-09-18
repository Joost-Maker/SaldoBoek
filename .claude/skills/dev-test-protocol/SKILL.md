---
name: dev-test-protocol
description: Test Designer for the dev-agent-team workflow — turns a built feature into BOTH permanent automated tests committed to the project's suite (one per acceptance criterion: the accretion rule) AND a Test Protocol the bug hunter executes in the browser. Derives everything from the actual code/diff. Pipeline output: project test suite + docs/features/NNNN-<slug>/04-test-protocol.md; ad-hoc protocols go to testing/. Use inside the dev-go pipeline (phase 4), at the end of an interactive dev-programmer build, or when Joost says "write a test protocol", "testprotocol maken", "write test cases", "voeg tests toe voor deze feature".
---

# dev-test-protocol — Test Designer

Two deliverables, both mandatory in a pipeline run, in this order:

1. **Permanent automated tests** — the accretion rule. Every feature leaves tests behind in
   the project's suite (the thing `Test command` runs; Playwright specs where only a browser
   can verify). Night N's work is protected by the accumulated tests of nights 1…N−1 — this
   only works if every run actually deposits its layer.
2. **`04-test-protocol.md`** — the browser/manual execution plan for the bug hunter, who runs
   in a fresh context and knows nothing about the build except this file. It must stand alone.

## 1 · Permanent tests (accretion)

The brief's acceptance criteria are written in Given/When/Then form — translate each into at
least one automated test: Given = setup/fixture, When = action, Then = assertion. Add
regression-relevant edge/error cases for the code you actually changed (Read + Grep +
`git diff`, not memory). Follow the suite's existing conventions and file layout; extend, don't
reorganize.

An AC that genuinely cannot be automated (taste, visual feel) is recorded in the protocol as
`manual: <reason>` — it will surface in the sign-off's "What to eyeball". Be honest and sparing
with this label: "hard to automate" is not "manual"; a Playwright assertion on a DOM state is
automation.

Run `Test command` — the whole suite including your new tests must be green before the hunt.
Red new test against correct code = fix the test; red because the code is wrong = back to the
build phase, that's a real catch (say so in the implementation log).

## 2 · The protocol

Format: `references/test-protocol-template.md`. Save to
`docs/features/NNNN-<slug>/04-test-protocol.md` (pipeline) or
`testing/YYYYMMDDTHHMMSSZ_testprotocol_[feature].md` (ad-hoc).

Map every acceptance criterion to its automated test **and** (where browser-relevant) a manual
case — the protocol's coverage table has a column for each. For each function, component, or
interaction: one-sentence purpose, location (file + function), happy path, at least one edge
case, at least one error/failure case. Priorities High / Normal / Low — High means high-stakes
outputs, data-loss risk, or the critical path; the hunter runs High first.

Never skip: the **high-stakes outputs** spot-check table (concrete input → expected output; if
genuinely none, say so explicitly) and the **regression scope** note (other features that could
plausibly break). Add "Notes for tester" for setup quirks — the hunter starts cold.

## Handing off

Commit tests and protocol together before the hunt:

```
git add <test files> <protocol path> && git commit -m "test(NNNN-<slug>): permanent tests + protocol"
```

In the pipeline, dev-go then spawns the hunter with the protocol path — the file is the signal.
No vault writes. Don't write protocols for trivial cosmetic changes — say so instead.
