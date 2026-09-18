# Retro — 0002-ai-suggest

**Run outcome:** PARKED (code gate cap: second `changes requested`)
**Phases with friction:** 2, 5, 6, 7

## What cost time or tokens that shouldn't have

| Phase | What happened | Root cause |
|---|---|---|
| 2 | The spec rev 2 edit script failed on an assertion, but the next shell line committed and the re-gate was spawned on the **unchanged rev 1** spec; it had to be killed and re-run | The orchestrator didn't verify the revision bump before spawning the gate, and the commit wasn't chained with `set -e`/`&&` |
| 5 | The real-GPU case (AC14) couldn't run: the model server is lifetime-bound to Obsidian and had been stopped | The protocol's "Dependencies" named the service but Phase 0 didn't check it; a stopped service was discovered only mid-hunt |
| 6/7 | The fix for code-gate R1 (IBAN leak) over-corrected: word boundaries dropped, so ordinary text got masked. Caught only by the second code gate, which parks | The fix phase has no rule that a **sanitiser/filter fix must come with a negative test** (what must stay intact); the new tests only checked what must be removed |
| 6 | AC14 (real GPU) ran before the code-gate fix round changed the prompt code, so its "passed" no longer covers the final code | No rule to re-run manual ACs affected by later fixes |
| 6 | A PO amendment mid-run (zoekterm = full name) had no documented procedure; improvised as a brief amendment section + spec rev 3 + re-gate, which used the last revision slot | `pipeline.md` doesn't cover PO amendments during an interactive run |

## Proposed upstream changes (Agents repo)

| # | File (in Joost-Maker/Agents) | Change | Why |
|---|---|---|---|
| 1 | `skills/dev-programmer/SKILL.md` (Phase 6) | "A fix to any sanitiser, filter, validator or guard must add a **negative** regression test (legitimate input passes unchanged) next to the positive one." | Would have prevented R5 and the park |
| 2 | `skills/dev-go/references/pipeline.md` (Phase 2) | "Before spawning a gate, verify the artifact actually changed (revision number bumped, diff non-empty); chain edit → verify → commit with `set -e`." | Avoids gating a stale spec |
| 3 | `skills/dev-go/references/pipeline.md` (Phase 0) | "Check the protocol-relevant runtime dependencies (services, hardware) at intake and note any that are down in the implementation log." | AC14 would have been flagged at intake, not mid-hunt |
| 4 | `skills/dev-go/references/pipeline.md` (Phase 8) | "Manual ACs whose code path changed after they were executed are re-run (or marked stale) before sign-off." | The AC14 result would otherwise silently cover changed code |
| 5 | `skills/dev-go/references/pipeline.md` (new section) | "PO amendment (interactive only): append a dated `## PO amendment` to `00-brief.md` and the vault note, bump the spec revision, and re-gate. An amendment does **not** consume a revision cycle." | Keeps an explicit PO decision from burning the cap reserved for spec quality |

## Worked well (keep)

- **Real-hardware probing before the spec** (one synthetic call) exposed the wrong VRAM premise (Jan desktop holding 9 GiB) and the `zekerheid: 95` output. The per-process GPU guard came straight out of it.
- **Fresh-context gates kept catching real things:** proxy env leakage (spec gate), `--out` overwriting the DB (hunt), the `<out>.tmp` link, IBAN variants, and the over-masking regression (code gate).
- **Mutation checks** (temporarily breaking a guard and confirming its test goes red) gave confidence that the safety tests actually test something.
