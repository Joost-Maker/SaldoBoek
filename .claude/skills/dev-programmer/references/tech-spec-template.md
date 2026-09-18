# Technical Spec template

Saved as `docs/features/NNNN-<slug>/01-spec.md` and committed. Reviewed by `dev-review` (spec
mode) against `00-brief.md` — write it to be gate-checkable: claims about current code must be
verifiable, scope must map 1:1 to the brief.

```markdown
# Technical Spec — [Feature Name]

**Date:** YYYY-MM-DD
**Brief:** 00-brief.md (snapshot of [vault item path])
**Revision:** 1

---

## Interpretation of the brief

[Restate the requirement in technical terms, 2–4 sentences. The gate checks this against the
brief — a misreading dies here, cheaply.]

---

## Proposed approach

### Files to create
- `path/to/new_file` — [purpose]

### Files to modify
- `path/to/existing_file` — [what changes and **why**]

### Config changes (if any)
### Data model / stored format changes (if any — these are park-territory if not in the brief)

---

## Requirement mapping

| Brief requirement / acceptance criterion | Where it's handled |
|---|---|
| [FR1] | [file / approach] |

---

## High-stakes output impact

[Changes to critical calculations, stored data, or user-visible numbers. Mandatory — write
"None" explicitly if none.]

---

## Architecture notes

- [ ] CLAUDE.md architecture rules respected
- [ ] No changes outside the files listed above
- [ ] Config over hardcoding

---

## Test scope

[What 04-test-protocol.md will cover — specific functions and flows, including how each
acceptance criterion gets verified.]

---

## Open questions for PO

[Anything genuinely unresolved. NON-EMPTY = the gate parks the run — that is the correct
outcome when a real question exists. Empty if none.]
```

## Rules

- Every "Files to modify" bullet says *why*, not just *what*.
- The Requirement mapping table is mandatory — it's how the gate checks coverage without
  re-deriving your reasoning.
- Spec revisions (after `changes requested`) bump **Revision** and keep a one-line
  `## Revision notes` trail at the bottom; max 2 revision cycles before the run parks.
