# Test Protocol template

Pipeline: save as `docs/features/NNNN-<slug>/04-test-protocol.md`.
Ad-hoc: save as `testing/YYYYMMDDTHHMMSSZ_testprotocol_[feature].md`.

```markdown
# Test Protocol
**Date (UTC):** YYYY-MM-DDTHH:MM:SSZ
**Feature:** [name (NNNN-<slug> if pipeline)]
**Brief ref:** 00-brief.md · **Spec ref:** 01-spec.md  [or n/a for ad-hoc]
**Scope:** [one sentence: what changed or was built]
**Dependencies:** [running services, test data, URLs — the hunter starts cold]

---

## Acceptance criteria coverage  <!-- pipeline runs: mandatory -->

| Acceptance criterion (from 00-brief.md) | Automated test (file::case) | Manual case below |
|---|---|---|
| | | [case #, or "—"] |

An AC with no automated test must say `manual: <reason>` in the middle column — it will land in
the sign-off's "What to eyeball".

---

## Functions to test

### 1. [Function / interaction name]
**Description:** [what it does]
**Location in code:** [file:line or file + function]

| Test case | Input / action | Expected result | Priority |
|-----------|----------------|------------------|----------|
| Happy path | | | Normal |
| Edge case | | | Normal |
| Error state | | | High |

### 2. [Next function]

...

---

## High-stakes output checks

Concrete values to spot-check. If none: "No high-stakes outputs in this change."

| Output | Input values | Expected result | Formula / logic reference |
|--------|--------------|------------------|---------------------------|
| | | | |

---

## Regression scope

Features that could plausibly break because of this change:

- [ ] [Feature + why it could be affected]

---

## Notes for tester

- App URL: [localhost:port or staging]
- Test credentials: [or "none needed"]
- Known quirks / incomplete parts: [what the hunter should expect]
```
