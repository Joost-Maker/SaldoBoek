# Fixes — AI suggest (0002-ai-suggest)

## Round 1 (after 05-bughunt-report.md round 1)

| Bug | Severity | Fix | Files | Regression test |
|---|---|---|---|---|
| E2: `--out` pointing at the database (directly or through a symlink) replaced `database.db` with the CSV, silently, with exit 0 | 🟠 | `check_output()` runs before the eGPU check, before the DB is opened, and before any model call. It refuses when `realpath(--out) == realpath(--db)` and when `--out` isn't a `.csv` (exit 1, clear message). The default output path is always a new `ai_review_*.csv` next to the DB | `tools/ai_suggest/__main__.py` | `tests/ai_suggest/test_io.py::test_out_equal_to_db_refused`, `::test_out_via_symlink_to_db_refused`, `::test_out_must_be_csv` |

**Left for backlog (🟡/🟢, per pipeline rule):** F2 IBAN variants (double space, tab, NBSP, dashes, dots, glued `IBANNL…`) still reach the local model; E1 over-broad zoektermen (`b.v.`, `betaling`, `pinbetaling`) and the same term proposed for different categories aren't flagged, and collisions ignore other uncategorised groups; E3 an unwritable `--out` directory is only discovered after all model calls; F1 `zekerheid` 1.5 becomes 0,01 without a flag; E4 control characters in names go raw to stdout; E5 `--sysfs-root` pointing elsewhere skips the pre-check (one request before exit 3).

**AC14 (real GPU run) not executed in round 1:** the llama-server on `:6767` (`jan-claudian.service`) was stopped. It only runs while Obsidian is open. Starting it is Joost's call; see the sign-off.

Test command after round 1: `.venv/bin/python -m pytest -q` → green (56 passed).
