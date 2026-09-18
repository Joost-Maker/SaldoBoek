# Sign-off — AI suggest: GPU category + rule proposals (0002-ai-suggest)

**Status:** PARKED (code gate: second `changes requested`, cap reached)
**Date (UTC):** 2026-09-18T13:45:00Z
**Vault item:** DEV/SaldoBoek AI suggest - GPU category and rule proposals.md
**Branch / commit:** `feat/0002-ai-suggest`, pushed to `Joost-Maker/SaldoBoek` (not merged into `dev`)
**Rollback:** nothing merged
**Vault:** updated (dev_status stays Doing; Log line added)
**Tests added (accretion):** 63 cases in `tests/ai_suggest/` (conftest with a synthetic DB, a stub LLM and a fake sysfs/proc), all green (64 in the suite)

## State when parked

Phases 0–6 are complete and code gate review 1's four required changes are fixed. **Code gate review 2 found one regression in the fix for review 1 (R5): the new IBAN pattern lost its word boundaries, so it now over-masks ordinary description text.** `Factuur 2026-00123 abonnement oktober` → `Factu[IBAN]`. No data leaks and stdout is unaffected, but the model gets less description text to categorise by (and nameless groups less text to pick a zoekterm from). Per the pipeline, a second code-gate failure parks the run.

**The fix is small and exactly specified in `07-code-review.md`** (restore the boundaries, keep the glued `IBAN…` case). The pattern it proposes: `(?:(?<=IBAN)|(?<![A-Z0-9]))[A-Z]{2}[ .\-]?\d{2}(?:[ .\-]?[A-Z0-9]){11,30}(?![A-Z0-9])`, IGNORECASE, **plus a permanent negative test** that `scrub` leaves non-IBAN text intact. Then update `06-fixes.md` and protocol row 2.4, and re-gate.

## Gate results

| Gate | Verdict | Artifact |
|---|---|---|
| Spec review | approved with notes (rev 3; rev 1 changes requested: network confinement; rev 3 = PO amendment) | 02-spec-review.md |
| Bug hunt | round 1: 0 🔴 · 1 🟠 · 3 🟡 · 3 🟢 → round 2: 0 🔴 · 0 🟠 · 1 🟡 · 2 🟢 | 05-bughunt-report.md |
| Real GPU run (AC14) | **passed**: Qwen3-14B 10.6 GiB resident on the RX 9060 XT, no spill, ~1 s/call warm, 33 s for 8 groups (run *before* the code-gate fix round) | 06-fixes.md |
| Project tests | green, 64 passed | — |
| Code review | 1: changes requested (4) → fixed; **2: changes requested (R5, regression from the R1 fix)** | 07-code-review.md |

## Assumptions made (from the decision log)

1. Per-process VRAM check on top of the brief's card check (the card check alone passes when another app fills the eGPU).
2. A spill below 90 % gives a warning, not an abort.
3. A non-existent `--gebruiker` exits with a message.
4. Nameless groups show `(geen naam)` on stdout, never the description.
5. Up to 3 scrubbed sample descriptions, truncated to 120 chars.
6. A partial CSV after an abort includes the failed groups.
7. Test layout: the I/O-boundary tests live in one `test_io.py`.
8. The review CSV is 0600 (bank data).

**PO amendment (Joost, during the run): the zoekterm is the full counterparty name.**

## What to eyeball / recommended next step

1. **Recommended next step:** apply the R5 fix (the pattern and negative test in `07-code-review.md`), re-run the code gate, then close. That's about 15 minutes interactively, or it can be queued.
2. After R5: one more **real GPU run** on the synthetic DB, because AC14 ran before the IBAN code changed. Check the proposals still look as good.
3. Your real run, once merged: `AI_SUGGEST_API_KEY=<key> .venv/bin/python -m tools.ai_suggest --db saldoboek/data/database.db`. The model server on :6767 only runs while Obsidian is open (`jan-claudian.service`). Keep the Jan desktop app's model unloaded, or you'll get the spill warning and slow calls.

## Backlog candidates (capture via dev-po)

1. 🟡 **E1/N21, for the 0003 brief:** a counterparty with both income and expenses gives two rows with the **same** zoekterm but different categories, and `categorisatie_regels` is `UNIQUE(zoekterm, gebruiker_id)`, so only one can become a rule. Two overlapping names that are both uncategorised in one run (`Test Garage` / `Test Garage Onderdelen`) aren't flagged. Nameless or short-name groups can still get generic model terms.
2. 🟡 E3/N3: an unwritable `--out` directory is only discovered after every model call.
3. 🟢 R2-2: a named group whose model reply has a null/non-string zoekterm is marked `model-fout`, even though the zoekterm isn't used.
4. 🟢 R2-3: re-running with the same explicit `--out` overwrites a reviewed CSV (and its `akkoord` marks). The default timestamped path is safe.
5. 🟢 F1 (`zekerheid` 1.5 → 0,01 without a flag), E4 (control characters in names go raw to stdout), E5 (`--sysfs-root` elsewhere skips the pre-check).
6. Quality observation from AC14: `Test Apotheek Centrum` → Boodschappen at 0.95 although `Zorg` existed. Few-shot examples are the lever; the review step catches it.
