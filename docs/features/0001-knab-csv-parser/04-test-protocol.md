# Test Protocol
**Date (UTC):** 2026-09-18T09:30:00Z
**Feature:** Knab CSV import for SaldoBoek (0001-knab-csv-parser)
**Brief ref:** 00-brief.md · **Spec ref:** 01-spec.md (rev 2)
**Scope:** New `KnabParser` plus Knab detection (by filename and by header) in `TransactionImporter.detect_bank_and_parse`.
**Dependencies:** repo venv `.venv/bin/python` (pandas, pyyaml, pytest; **no PySide6**). No server, no browser UI. Everything runs headless through Python against a **temporary** `DatabaseManager(db_path=<tmp Path>)`.

> ⛔ **Hard rule:** never open real bank data. Nothing under `~/Code/Financien`, no real Knab export, no `saldoboek/data/database.db`. Every input you use is synthetic and written by you into a temp dir, with fake IBANs (`NL00KNAB0000000000`) and fake names.

---

## Acceptance criteria coverage

| Acceptance criterion (from 00-brief.md) | Automated test (file::case) | Manual case below |
|---|---|---|
| AC1: 2 rows −6.5 / 1234.56, 2026-09-17, betaalrekening, 0.0, no `Unnamed` | `tests/test_knab_parser.py::test_basic_rows` | 1.1 |
| AC2: `"1.234,56"` Afschrijvingen → −1234.56 | `tests/test_knab_parser.py::test_thousands_separator` | 1.2 |
| AC3: `Onbekend` → `ValueError` containing `Onbekend`; import stores 0 | `test_knab_parser.py::test_unknown_creditdebet_raises`, `test_knab_import.py::test_import_unknown_creditdebet_stores_nothing` | 1.3, 2.4 |
| AC4: empty tegenrekening → `""`, empty omschrijving → naam, no NaN/`"nan"` | `test_knab_parser.py::test_empty_fields` | 1.4 |
| AC5: preamble line → identical result | `test_knab_parser.py::test_preamble_is_ignored` | 1.5 |
| AC6: default Knab filename and `export.csv` → KnabParser | `test_knab_import.py::test_detect_by_filename`, `::test_detect_by_header`, `::test_detect_by_header_parses_for_real` | 2.1, 2.2 |
| AC7: `RABO_test.csv` → RaboParser | `test_knab_import.py::test_rabo_filename_still_rabo` | 2.3 |
| AC8: import twice → N then 0 | `test_knab_import.py::test_import_twice_is_idempotent` | 2.5 |
| AC9: real export via GUI, month totals match the Knab app | `manual:` needs Joost's real data, which agents may not touch; Joost only | — (sign-off "What to eyeball") |

---

## Functions to test

### 1. `KnabParser.parse_csv`
**Description:** reads a Knab Transactieoverzicht CSV and returns SaldoBoek's standard DataFrame with a signed `bedrag`.
**Location in code:** `saldoboek/core/parsers/knab_parser.py`, `KnabParser.parse_csv` / `_read_knab_table` / `_process_knab_data`

| # | Test case | Input / action | Expected result | Priority |
|---|---|---|---|---|
| 1.1 | Happy path | BOM + quoted + trailing `;` file: 1 Afschrijvingen `6,5`, 1 Bijschrijvingen `1234,56`, date `17-09-2026` | bedrag −6.5 / 1234.56, datum 2026-09-17, 9 standard columns, `saldo_voor` 0.0 | High |
| 1.2 | Thousands | Afschrijvingen `1.234,56` | −1234.56 | High |
| 1.3 | Unknown sign | a row with CreditDebet `Onbekend`; also `""`, `afschrijvingen` (lowercase), `Afschrijving` (singular) | `ValueError` naming the value; **never** a DataFrame | High |
| 1.4 | Empty fields | empty `Tegenrekeningnummer` and `Omschrijving` | `tegenrekening == ""`, `omschrijving == naam`, no NaN or `"nan"` anywhere | Normal |
| 1.5 | Preamble | one line `KNAB EXPORT` above the header | same DataFrame as without it | Normal |
| 1.6 | Edge: CRLF vs LF | same content with `\n` line endings | identical result | Normal |
| 1.7 | Edge: whitespace | CreditDebet `" Afschrijvingen "` | treated as Afschrijvingen (it's stripped) | Normal |
| 1.8 | Edge: header only | header, no rows | empty DataFrame, no crash (the "Periode" print is guarded) | Normal |
| 1.9 | Edge: mixed month | ~10 debits and credits with varied amounts (`0,01`, `10`, `99,9`, `1.000,00`) | every sign and amount exact; sum of debits and sum of credits match a hand calculation | High |
| 1.10 | Error: filled extra cell | a value in the 16th (unnamed) column, or beyond | `ValueError` "meer gevulde velden" | High |
| 1.11 | Error: bad amount / date | `abc` amount, `2026/09/17` date | `ValueError`, no row silently dropped | High |
| 1.12 | Error: quote in preamble | a preamble line with an unbalanced `"` (e.g. `Export van "Knab`) | report what happens. The csv module may swallow following lines, so the header isn't found and it should **error**, not import partial data. Wrong silent output = 🔴 | Normal |
| 1.13 | Encoding | the same file saved as cp1252 without BOM, with a name containing `é` | parses; the name survives | Low |

### 2. `TransactionImporter.detect_bank_and_parse` + `import_transactions_with_categorization`
**Description:** routes files to the right parser; stores parsed rows with a duplicate check.
**Location in code:** `saldoboek/core/importer.py`, `detect_bank_and_parse`, `import_transactions_with_categorization`

| # | Test case | Input / action | Expected result | Priority |
|---|---|---|---|---|
| 2.1 | Default Knab name | `Knab Transactieoverzicht Test NL00KNAB0000000000 - 2026-01-01 - 2026-09-17.csv` | KnabParser | High |
| 2.2 | Renamed Knab file | same content as `export.csv` | KnabParser (header detection) | High |
| 2.3 | Rabo priority | `RABO_test.csv` (any content); also a Knab-formatted file named `RABO_knab.csv` | RaboParser in both cases (SNS/RABO filenames win, as specified) | Normal |
| 2.4 | Unknown sign, full import | import a file with one `Onbekend` row among valid rows into a temp DB | 0 rows stored, the reason printed | High |
| 2.5 | Idempotent | import the same Knab file twice | N, then 0; row count stays N | High |
| 2.6 | Non-Knab `;` file | `export.csv` with a foreign `;` header | existing `ValueError("Onbekend bankformaat …")`, not treated as Knab | Normal |
| 2.7 | Two files at once | a valid Knab file plus a bad (`Onbekend`) Knab file in one `import_transactions_with_categorization` call | valid file imported, bad file skipped with a message | Normal |

---

## High-stakes output checks

| Output | Input values | Expected result | Formula / logic reference |
|---|---|---|---|
| `bedrag` sign | `Afschrijvingen`, `6,5` | `-6.5` | `KNAB_SIGN` × amount |
| `bedrag` sign | `Bijschrijvingen`, `1234,56` | `1234.56` | same |
| `bedrag` thousands | `Afschrijvingen`, `1.234,56` | `-1234.56` | strip `.`, `,` → `.` |
| `bedrag` small | `Bijschrijvingen`, `0,01` | `0.01` | same |
| rejected sign | `Onbekend` | ValueError, 0 rows stored | `_process_knab_data` |
| `datum` | `17-09-2026` | 2026-09-17 | `%d-%m-%Y` |

---

## Regression scope

- [ ] **Rabo / SNS import:** `detect_bank_and_parse` gained two branches; SNS/RABO must still win on filename (2.3).
- [ ] **Unknown-bank rejection:** the `else` path must still raise "Onbekend bankformaat" for non-Knab files (2.6).
- [ ] **Import loop:** the `ValueError` → skip-file behaviour for multiple files (2.7).

---

## Notes for tester

- App URL: none. Desktop GUI, and PySide6 isn't installed in `.venv`. Drive everything from Python: `from saldoboek.core import DatabaseManager, TransactionImporter`; `from saldoboek.core.categorization import Categorizer`; `db = DatabaseManager(db_path=Path(tmp)/"t.db")` (**must be a `Path`**, never the default); `imp = TransactionImporter(Categorizer(db, 1), db, 1)`.
- Always pass `account_type="betaalrekening"`. With `None`, the parser waits for interactive input.
- Test credentials: none needed.
- Fixture helpers: `tests/conftest.py` (`knab_row`, `render_knab`) produce the exact Knab format; reuse them for edge files.
- `DatabaseManager` prints `[DEBUG]` lines; that's normal.
- Known, out of scope: the GUI doesn't show *why* a file was skipped (the reason goes to stdout only); the legacy `BANK_PARSERS` fallback is non-functional. Don't report these as bugs from this feature.
