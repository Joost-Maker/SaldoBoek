# Implementation log — Knab CSV import for SaldoBoek

**Spec:** 01-spec.md (rev 2, approved with notes 2026-09-18)

## Build notes

| Requirement | Status | Where | Note |
|---|---|---|---|
| FR: `KnabParser`, Rabo interface, standard columns | done | `saldoboek/core/parsers/knab_parser.py` | same account-type resolution (argument > constructor > prompt) |
| FR: mapping incl. `Boekdatum` fallback, `saldo_voor=0.0` | done | `knab_parser.py` `_process_knab_data` | |
| FR: sign from CreditDebet, unknown → `ValueError` | done | `knab_parser.py` `KNAB_SIGN`, `_process_knab_data` | checked on the whole file before any DataFrame is built; no `except Exception` wrapper |
| FR: no NaN/`"nan"`, `Unnamed` dropped | done | `knab_parser.py` `_read_knab_table` | csv module + `dtype=str`; empty-named header columns dropped |
| FR: header by content, preamble skipped | done | `knab_parser.py` `_is_header`, `_read_knab_table` | |
| FR: detection by `KNAB` filename + header | done | `saldoboek/core/importer.py` `detect_bank_and_parse` | after SNS/RABO, before the legacy loop |
| FR: registration | done | `core/parsers/__init__.py`, `config/bank_parsers.py`, `tests/test_smoke.py` | |
| FR: README | done | `README.md` "Ondersteunde Banken" | |
| Gate note: extra non-empty cells → error | done | `_read_knab_table` | only trailing empty cells are cut; a filled cell beyond the header raises `ValueError` with the line number |
| Gate note: guard period print on empty result | done | `_print_import_summary` | header-only file returns an empty DataFrame with the standard columns |

Sanity check on a synthetic `export.csv` (BOM, CRLF, quoted, trailing `;`, a thousands `.`): detected by header, −6.50 / +1234.56, an empty `Omschrijving` becomes `naam`.

## Decisions (ambiguities resolved without the PO)

| # | Ambiguity | Chose | Alternative rejected | Why reversible |
|---|---|---|---|---|
| 1 | Brief says fixtures "live under `tests/fixtures/knab/`", but `.gitignore:19` ignores `*.csv` repo-wide | Generate fixtures into `tmp_path` from Python data in `tests/conftest.py` (spec rev 2, gate-approved) | A narrow `!tests/fixtures/**/*.csv` negation in `.gitignore`, rejected because the `*.csv` rule is what keeps real bank exports out of git | Test layout only; switching to committed files later is a move plus a one-line `.gitignore` change |
| 2 | Encoding fallback order | `utf-8-sig`, then `cp1252` | Rabo's `iso-8859-1`-first order | Internal constant `KNAB_ENCODINGS` |
| 3 | Header detection placement | `elif is_knab_file(...)` directly after the `KNAB` branch, which behaves the same as "inside `else`, before the legacy loop" in the spec | Nesting inside `else` | Same control flow; purely structural |
| 4 | Unreadable amount or date | `ValueError` naming the value | Dropping the row (Rabo does `dropna`) | Local to the parser; the gate accepted this as stricter than the brief |

## Caught by phase 4 tests

- `test_extra_filled_cell_raises` went red against the build. A filled cell in the **unnamed 16th column** (the one the header's trailing `;` creates) was silently dropped, because the extra-cell check only looked past the header width. Fixed in `_read_knab_table`: cells in any dropped (empty-named) column now count as extra and raise. This is a real code bug, not a test bug.

## Deviations from the spec

None. Decision 3 is a structural equivalent of the spec's wording, not a behavioural change.

## Test command runs

| When | Command | Result |
|---|---|---|
| baseline (phase 0) | `.venv/bin/python -m pytest -q` | green (1 passed) |
| after build | `.venv/bin/python -m pytest -q` | green (1 passed in 0.21s) |
| phase 4, new tests (1st run) | `.venv/bin/python -m pytest -q` | red: 1 failed, 20 passed (the bug above) |
| phase 4, after fix | `.venv/bin/python -m pytest -q` | green (21 passed) |
