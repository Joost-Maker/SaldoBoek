# Sign-off — AI suggest: GPU category + rule proposals (0002-ai-suggest)

**Status:** READY FOR REVIEW (manual merge policy). Earlier PARKED at the code-gate cap, then finished interactively with Joost's OK; final approval is Joost's word in chat, not a code gate (see "Gate results")
**Date (UTC):** 2026-09-18T15:00:00Z
**Vault item:** DEV/SaldoBoek AI suggest - GPU category and rule proposals.md
**Branch / commit:** `feat/0002-ai-suggest`, pushed to `Joost-Maker/SaldoBoek` (not merged into `dev`)
**Rollback:** nothing merged
**Vault:** updated (Log line; dev_status stays Doing until merged)
**Tests added (accretion):** 62 cases in `tests/ai_suggest/` (63 in the suite), green

## What shipped

`python -m tools.ai_suggest` (fork-only) reads SaldoBoek's DB read-only. It groups the `Ongecategoriseerd` transactions per counterparty and sign, and asks Qwen3-14B on the RX 9060 XT (via `llama-server` on 127.0.0.1:6767) for a category constrained to the user's own categories. **The zoekterm is always the full counterparty name** (PO amendment 1). The model gets the full transaction lines (PO amendment 2). Proposals go into a `;`/decimal-comma review CSV for LibreOffice (mode 0600) with collision and shadow flags. The GPU guard refuses without the eGPU and aborts if the model process isn't resident on it, with no CPU/iGPU fallback.

## Gate results

| Gate | Verdict | Artifact |
|---|---|---|
| Spec review | approved with notes (rev 3; PO amendment 1) | 02-spec-review.md |
| Bug hunt | round 1: 0 🔴 · 1 🟠 (fixed) → round 2: 0 🔴 · 0 🟠 | 05-bughunt-report.md |
| Real GPU run (AC14) | **passed on the final code**: 10.6 GiB resident, mean 1.8 s/call, 8/8 groups | 06-fixes.md round 4 |
| Project tests | green, 63 passed | — |
| Code review | 1: changes requested (R1–R4) → fixed; 2: R5 → **PARKED at cap**; interactive: 3: R6 → fixed; 4: **stopped by Joost**. Then PO amendment 2 removed the IBAN code that R5/R6 concerned. **The final code has no code-gate approval; Joost approved in chat.** | 07-code-review.md |

## Assumptions made (from the decision log)

1. Per-process VRAM check on top of the card check.
2. A spill gives a warning, not an abort.
3. A non-existent `--gebruiker` exits with a message.
4. `(geen naam)` on stdout for nameless groups.
5. Up to 3 sample lines per group (now full `datum · bedrag · omschrijving`, ≤ 1000 chars).
6. A partial CSV after an abort includes failed groups.
7. I/O-boundary tests live in `test_io.py`.
8. The review CSV is 0600.

**PO amendments:** (1) the zoekterm is the full counterparty name; (2) no IBAN masking, since the model is local.

## What to eyeball

1. **Your real run**, once `jan-claudian.service` is up (open Obsidian) and the Jan desktop app has no model loaded:
   `AI_SUGGEST_API_KEY=jan-local .venv/bin/python -m tools.ai_suggest --db saldoboek/data/database.db`
   Open the `ai_review_*.csv` next to the DB in LibreOffice and check the categories. The model still put a pharmacy under Boodschappen while `Zorg` existed; the review is where you catch that.
2. **Merge decision:** `feat/0002-ai-suggest` into `dev` (fork-only code, never upstream).

## Backlog candidates (capture via dev-po)

1. 🟡 **For the 0003 (apply) brief:** a counterparty with both income and expenses → two rows with the **same** zoekterm, and `categorisatie_regels` is `UNIQUE(zoekterm, gebruiker_id)`, so only one can become a rule. Overlapping uncategorised names in one run (`Test Garage` / `Test Garage Onderdelen`) aren't flagged against each other.
2. 🟡 An unwritable `--out` directory is only discovered after every model call.
3. 🟢 A null zoekterm in the model reply for a named group → `model-fout` although the zoekterm isn't used. Re-running with the same explicit `--out` overwrites a reviewed CSV. `zekerheid` 1.5 → 0,01 without a flag. Control characters in names go raw to stdout. `--sysfs-root` elsewhere skips the pre-check.
