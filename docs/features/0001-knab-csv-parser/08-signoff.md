# Sign-off — Knab CSV import for SaldoBoek (0001-knab-csv-parser)

**Status:** READY FOR REVIEW (manual merge policy)
**Date (UTC):** 2026-09-18T10:45:00Z
**Vault item:** DEV/SaldoBoek Knab CSV parser.md
**Branch / commit:** `feat/0001-knab-csv-parser`, pushed to `Joost-Maker/SaldoBoek` (not merged into `dev`)
**Rollback:** nothing merged
**Vault:** updated (dev_status Doing; Log line added)
**Tests added (accretion):** 25 cases: 16 in `tests/test_knab_parser.py`, 9 in `tests/test_knab_import.py`; `tests/test_smoke.py` extended. This is SaldoBoek's first test suite.

## What shipped / state when parked

`KnabParser` (`saldoboek/core/parsers/knab_parser.py`) imports a Knab "Transactieoverzicht" CSV:
- `bedrag` gets its sign from `CreditDebet`: `Afschrijvingen` → negative, `Bijschrijvingen` → positive. Any other value rejects the whole file.
- The header is found by content, so a preamble line doesn't matter.
- The file is rejected if a mapped column is missing, or if a row has no date at all.

`TransactionImporter.detect_bank_and_parse` routes to it by filename (`Knab…`) or, for renamed files, by header. SNS/RABO filename priority is unchanged. The README lists Knab.

Everything is built and verified on synthetic data only. The run stops at a reviewed branch: merging to `dev` and opening the upstream PR are Joost's calls.

## Gate results

| Gate | Verdict | Artifact |
|---|---|---|
| Spec review | approved with notes (rev 2; rev 1 changes requested: `*.csv` in `.gitignore` would have dropped the fixtures) | 02-spec-review.md |
| Bug hunt | round 1: 1 🔴 · 2 🟠 · 3 🟡 · 1 🟢 → round 2: 0 🔴 · 0 🟠 · 1 🟡 · 0 🟢 | 05-bughunt-report.md |
| Project tests | green, 26 passed (`.venv/bin/python -m pytest -q`) | — |
| Code review | approved with notes | 07-code-review.md |

Round 1's second 🟠 (E-1, duplicate key) is pre-existing importer behaviour. **PO decision (Joost, 2026-09-18): out of scope for this feature**; tracked as DEV item "SaldoBoek duplicate check drops genuine identical transactions".

## Assumptions made (from the decision log)

1. Fixtures are generated into `tmp_path` by `tests/conftest.py`, not committed under `tests/fixtures/knab/`. The rejected alternative was a `.gitignore` negation, because the `*.csv` rule keeps real bank exports out of git.
2. Encoding fallback is `utf-8-sig` → `cp1252` (not Rabo's `iso-8859-1`-first).
3. Header detection is an `elif` right after the `KNAB` branch, not nested inside `else`; the behaviour is the same.
4. An unreadable amount or date raises `ValueError` instead of silently dropping the row (stricter than the brief; the gate accepted it).
5. Added in fix round 1: all 9 mapped header columns are required, which is stricter than the spec. This fixed the 🔴.

## What to eyeball

1. **AC9, your real export (only you can do this).** Import `~/Code/Financien/Knab Transactieoverzicht …csv` through the SaldoBoek GUI. That needs PySide6: `.venv/bin/pip install PySide6`, then `.venv/bin/python main.py --gui` on branch `feat/0001-knab-csv-parser`. Then check that one month's income and expense totals match the Knab app to the cent, **and compare the transaction count**. Because of E-1, identical same-day transactions (same amount and description) are dropped as duplicates, so a mismatch may be that bug and not the parser.
2. **When a file is rejected, the GUI only shows "0 geïmporteerd".** The reason (e.g. "Onbekende CreditDebet-waarde…", "mist kolom(men)…") is printed to the terminal, so start the GUI from a terminal and watch it. Also try an export from a Knab **savings** account if you have one: if its header differs, it's now rejected loudly instead of imported wrongly.
3. **Before the upstream PR:** the code gate recommends a strict format check on `Bedrag` and the dates (see backlog 1). A signed `-6,5` on a debit currently flips to +6.5. Knab never writes that, but a hand-edited file could, and upstream reviewers may try it.

## Backlog candidates (capture via dev-po)

1. 🟡 **Strict amount/date validation**: `-6,5` flips the sign, `6.50` reads as 650, `NaN`/`inf`/`1e3` are accepted; a date of `nan`/`NaT` crashes the import again, and `today` imports as today (bug hunt E-3, R2-1; code gate note). A few lines: a regex for `^\d{1,3}(\.\d{3})*(,\d+)?$|^\d+(,\d+)?$`, strict `dd-mm-yyyy`, and a post-parse NaT check. **Recommended before the upstream PR.**
2. 🟡 Short rows are padded instead of rejected; a truncated file imports a mangled last row (E-5).
3. 🟢 A duplicate header column (`AttributeError`) or a `csv.Error` isn't converted to `ValueError`, so it aborts a multi-file import (E-6).
4. 🟡 Upstream issue: the GUI doesn't show why the importer skipped a file (reason only on stdout).
5. 🟢 The legacy `BANK_PARSERS` fallback and the `saldoboek/parsers/` package are dead code (they call methods and modules that don't exist). Worth an upstream issue.
6. 🟢 Clean-up: a dead fallback branch in `text()` inside `_process_knab_data` (all used columns are now required); `06-fixes.md` numbers the findings differently from the bug hunt report (E-3 vs E-4).
7. Already filed: E-1 duplicate key → DEV item "SaldoBoek duplicate check drops genuine identical transactions".

**Upstream PR, when you're ready:** branch off `upstream/main`, cherry-pick only `saldoboek/`, `tests/` (conftest, `__init__`, the two Knab test files, and `test_smoke.py` if you want it upstream) and `README.md`. Never `CLAUDE.md`, `AGENTS.md`, `docs/`, `queue/`, `scripts/` or `.claude/`.

## Post-sign-off addition (PO request, 2026-09-18)

Joost's GUI check showed Knab missing from the import view's bank dropdown. At his request, "Knab" was added to `saldoboek/gui/views/import_view.py` (plus the matching comment in `import_viewmodel.py`). This is a display-only list: the selection is never wired to the importer (`set_bank_type` is never called), so detection stays automatic, as for Rabo/SNS. The brief had the GUI out of scope; the PO explicitly widened it for this one line. Tests: unchanged, 26 passed (no GUI tests; PySide6 isn't in the test venv).
