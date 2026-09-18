# Retro — 0001-knab-csv-parser

**Run outcome:** READY FOR REVIEW (manual merge policy)
**Phases with friction:** 0 (setup + brief), 2, 5

## What cost time or tokens that shouldn't have

| Phase | What happened | Root cause |
|---|---|---|
| pre-0 | The DEV item was marked `Refined` without Given/When/Then ACs, Out of scope or Ambiguity guidance, and spanned two repos; it had to be split and rewritten at GO time | The `obsidian-notes` skill's DEV section defines Refined as "brief in body is GO-ready" but doesn't point to the GO-readiness checklist, so Refined could be set outside `dev-po` |
| pre-0 | `obsidian-notes` DEV frontmatter example uses `Type/Status/Refinement/Priority`; the real template and notes use `dev_type/dev_status/dev_refinement/dev_priority` | Skill example drifted from `DEV/DEV Item Template.md` |
| 0 | Scaffolding a **fork** for an upstream contribution had no guidance: where the pipeline files go, which branch is the working branch, how the PR branch stays clean | `dev-init` assumes the repo is Joost's own project |
| 2 | Spec rev 1 was rejected because upstream `.gitignore` ignores `*.csv`, which would have silently dropped the planned fixtures | The spec template has no "check new file types against `.gitignore`" prompt |
| 2 | A re-review appended to `02-spec-review.md` leaves the rev-1 `Verdict: changes requested` line earlier in the file; tools must read the last verdict line | `pipeline.md` doesn't say whether re-reviews append or replace, or that the last line wins |
| 5 | `dev-bughunt` is written for Playwright/browser; this headless library/desktop feature needed an ad-hoc "drive it from Python" adaptation in every hunter prompt | No non-browser mode in the bughunt skill |

## Proposed upstream changes (Agents repo)

| # | File (in Joost-Maker/Agents) | Change | Why |
|---|---|---|---|
| 1 | `skills/dev-bughunt/SKILL.md` | Add a "Non-browser projects" section: drive the documented entry points headlessly, with exact input, command and output per finding instead of screenshots; keep the exploratory pass | Removes per-run prompt adaptation for CLI/library/desktop apps |
| 2 | `skills/dev-init/SKILL.md` | Add "Fork mode": working branch `dev` holds the scaffolding, `main` mirrors upstream, upstream PRs come from a clean branch off `upstream/main`; list the fork-only files | Keeps upstream PRs free of pipeline files without re-deciding it each time |
| 3 | `skills/dev-programmer/references/tech-spec-template.md` | Under "Files to create": "Check new file types against `.gitignore` (`git check-ignore`)" | Would have avoided a full spec revision cycle |
| 4 | `skills/dev-go/references/pipeline.md` (Phase 2) | "Re-reviews append a `## Re-review (rev N)` section; the **last** `Verdict:` line in the file is authoritative" | Makes verdict parsing unambiguous |
| 5 | vault skill `obsidian-notes` (DEV items section; lives outside the Agents repo) | Fix the frontmatter field names to `dev_*`; add "Refined = passes the GO-readiness checklist in dev-po's feature-brief template, set only via dev-po" | Prevents premature Refined flags and invented field names |

## Worked well (keep)

- **Fresh-context gates caught real defects:** the spec gate caught the `.gitignore` trap before any code existed, and the bug hunter caught the 🔴 (the header corrupted by a quoted preamble, which would double-count on re-import).
- **Accretion paid off immediately:** writing the AC tests exposed a silently-dropped-data bug (the unnamed trailing column) before the hunt.
- **Data boundary held:** synthetic fixtures only; no agent opened the real export, and the no-real-data rule sat in `CLAUDE.md` and in every gate prompt.
