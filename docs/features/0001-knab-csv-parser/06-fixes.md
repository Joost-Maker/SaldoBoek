# Fixes — Knab CSV import for SaldoBoek

## Round 1 (after 05-bughunt-report.md round 1)

| Bug | Severity | Fix | Files | Regression test |
|---|---|---|---|---|
| BUG-1: preamble starting with an unbalanced `"` merges with the header; `rekening` silently becomes `""`; re-imports double-count | 🔴 | Header must contain every column the parser reads (`KNAB_REQUIRED_COLUMNS`), else `ValueError` naming the missing one(s). The merged header lacks `Rekeningnummer`, so the file is rejected | `saldoboek/core/parsers/knab_parser.py` (`_read_knab_table`) | `test_knab_parser.py::test_quoted_preamble_does_not_corrupt_header`, `test_knab_import.py::test_import_quoted_preamble_stores_nothing` |
| E-3 (header part): renamed/missing column becomes a silent `""` | 🟡 (covered by the same fix) | same as BUG-1 | same | `test_knab_parser.py::test_missing_required_column_raises` |
| E-2: row with empty `Transactiedatum` and `Boekdatum` becomes NaT, crashes the import halfway and aborts later files | 🟠 | Rows without any date → `ValueError` before a DataFrame is returned; the importer's existing `except ValueError` skips the file and continues with the next | `knab_parser.py` (`_process_knab_data`) | `test_knab_parser.py::test_row_without_any_date_raises`, `test_knab_import.py::test_import_row_without_date_skips_file_and_continues` |

**Not fixed in this run: E-1** (🟠, identical same-day transactions dropped as duplicates). Cause: the importer's pre-existing duplicate key `(datum, rekening, bedrag, omschrijving, gebruiker_id)`. A fix changes the importer or the schema, which the brief says must park, so it's escalated to the PO (see the sign-off).

**Left for backlog (🟡/🟢, per pipeline rule):** E-3 amount forms (`-6,5`, `6.50`, `NaN`, `inf`, `1e3`, none of which Knab emits); short rows padded instead of rejected; duplicate header column → `AttributeError`.

Test command after round 1: `.venv/bin/python -m pytest -q` → green (26 passed).
