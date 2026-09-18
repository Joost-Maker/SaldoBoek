# Fixes — AI suggest (0002-ai-suggest)

## Round 1 (after 05-bughunt-report.md round 1)

| Bug | Severity | Fix | Files | Regression test |
|---|---|---|---|---|
| E2: `--out` pointing at the database (directly or through a symlink) replaced `database.db` with the CSV, silently, with exit 0 | 🟠 | `check_output()` runs before the eGPU check, before the DB is opened, and before any model call. It refuses when `realpath(--out) == realpath(--db)` and when `--out` isn't a `.csv` (exit 1, clear message). The default output path is always a new `ai_review_*.csv` next to the DB | `tools/ai_suggest/__main__.py` | `tests/ai_suggest/test_io.py::test_out_equal_to_db_refused`, `::test_out_via_symlink_to_db_refused`, `::test_out_must_be_csv` |

**Left for backlog (🟡/🟢, per pipeline rule):** F2 IBAN variants (double space, tab, NBSP, dashes, dots, glued `IBANNL…`) still reach the local model; E1 over-broad zoektermen (`b.v.`, `betaling`, `pinbetaling`) and the same term proposed for different categories aren't flagged, and collisions ignore other uncategorised groups; E3 an unwritable `--out` directory is only discovered after all model calls; F1 `zekerheid` 1.5 becomes 0,01 without a flag; E4 control characters in names go raw to stdout; E5 `--sysfs-root` pointing elsewhere skips the pre-check (one request before exit 3).

**AC14 (real GPU run) not executed in round 1:** the llama-server on `:6767` (`jan-claudian.service`) was stopped. It only runs while Obsidian is open. Starting it is Joost's call; see the sign-off.

Test command after round 1: `.venv/bin/python -m pytest -q` → green (56 passed).

## AC14: real GPU run (executed by the orchestrator, with Joost's explicit OK to start `jan-claudian.service`, 2026-09-18)

Synthetic DB from the round-1 hunt (8 fake counterparties, all names `Test …`). The service was started for the run and stopped afterwards; eGPU back to 367 MiB.

```
eGPU card0: 11.0/15.9 GiB in gebruik, model (pid 565027) 10.6 GiB resident
[1/8] Test Streaming (3×) → Abonnementen in 16.7 s     (cold load)
[2/8] Test Supermarkt B.V. (3×) → Boodschappen in 1.6 s
… 8 groups, mean 4.1 s/call, 32.9 s wall, exit 0, no spill warning
```

**Result: AC14 passes.** The model is resident on the RX 9060 XT (10.6 GiB, no spill), warm calls take ~1 s, and the proposals are plausible except one: `Test Apotheek Centrum` → Boodschappen (0.95), although `Zorg` exists. The review step catches that.

**Real-output confirmation of backlog E1:** the proposed zoektermen included generic words: `woning` (Huur), `salaris`, `de hoek`, `supermarkt`. They pass validation (a substring of every group text, no collisions in this DB), but as permanent rules they would over-match future transactions (e.g. `woning` ⊂ "woningverzekering"). Escalated to the PO in the sign-off.
