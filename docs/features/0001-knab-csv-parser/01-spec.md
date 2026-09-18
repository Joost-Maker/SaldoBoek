# Technical Spec — Knab CSV import for SaldoBoek

**Date:** 2026-09-18
**Brief:** 00-brief.md (snapshot of `DEV/SaldoBoek Knab CSV parser.md`)
**Revision:** 1

---

## Interpretation of the brief

Add a `KnabParser` that turns a Knab "Transactieoverzicht" CSV into SaldoBoek's standard parser DataFrame. The key points: `bedrag` gets its sign from `CreditDebet`, and an unknown `CreditDebet` value is a hard `ValueError` that makes the importer skip the whole file. Wire the parser into `TransactionImporter.detect_bank_and_parse` by filename (`KNAB`), and by header content when the filename names no bank. SNS/RABO filename detection keeps priority. Everything is verified with synthetic fixtures in a new pytest suite. No schema, GUI, categoriser or existing-parser changes.

---

## Proposed approach

### Files to create
- `saldoboek/core/parsers/knab_parser.py`: `KnabParser` with `parse_csv(filepath, account_type=None)` (same signature and account-type resolution as `RaboParser`: argument > constructor > interactive `_ask_account_type`). Also a module-level helper `is_knab_file(filepath) -> bool` for header detection by content.
- `tests/test_knab_parser.py`: parser-level acceptance tests.
- `tests/test_knab_import.py`: detection and import-into-temp-DB acceptance tests.
- `tests/fixtures/knab/*.csv`: synthetic fixtures (BOM, all fields quoted, trailing `;`, fake IBANs `NL00KNAB0000000000` / `NL00INGB0000000000`, fake names).

### Files to modify
- `saldoboek/core/importer.py`:
  - import `KnabParser` and instantiate it in `__init__` as `self.knab_parser` (same pattern as SNS/Rabo);
  - in `detect_bank_and_parse`, add `elif "KNAB" in filename` **after** the SNS and RABO branches, so their priority stays unchanged (brief). The filename is already uppercased, so `Knab …` matches;
  - in the `else` branch, before the legacy `BANK_PARSERS` loop, return the Knab parser's result when `is_knab_file(filepath)` is true. **Why:** the brief requires content detection for files whose name names no bank (e.g. `export.csv`).
  - No other importer change. A `ValueError` from `KnabParser` propagates out of `detect_bank_and_parse` into the existing `except ValueError` in `import_transactions_with_categorization`, which prints and `continue`s. The file is skipped and 0 rows are stored. This is the brief's one sanctioned exception, and it needs no code in the importer.
- `saldoboek/core/parsers/__init__.py`: export `KnabParser`. **Why:** the brief says to register it wherever the others are.
- `saldoboek/config/bank_parsers.py`: add `'KNAB': 'parse_knab_csv'`. **Why:** the brief asks for registration there too. Note: this map is legacy. Its method names don't exist on `TransactionImporter`, and it's only reached for filenames that match none of the explicit branches, which a `KNAB` filename always does. The entry is consistency only; see the Decisions note below.
- `README.md` "🏦 Ondersteunde Banken": add `- **Knab** - Transactieoverzicht CSV`.

### Parser design
1. **Read:** open with `encoding="utf-8-sig"` (strips the BOM); on `UnicodeDecodeError`, retry with `cp1252`. Parse with `csv.reader(f, delimiter=";", quotechar='"')` so quoted fields are handled correctly.
2. **Header location:** the first row containing both `CreditDebet` and `Tegenrekeninghouder`; rows above it are ignored (the preamble case). No such row → `ValueError("Geen Knab-header gevonden in <file>")`.
3. **Trailing `;`:** the header row ends with an empty cell. Drop columns whose header name is `""` after `strip()`; this is the csv-module equivalent of pandas' `Unnamed:*`. Data rows are cut or padded to the header length.
4. **Build DataFrame** from the rows below the header with `dtype=str`. Every cell stays a string; empty stays `""`, never NaN. Fully empty rows are skipped.
5. **Sign:** map `CreditDebet` with `{"Afschrijvingen": -1, "Bijschrijvingen": 1}` after `strip()`. Any value outside that map → `ValueError` whose message lists the offending value(s) and the file. This check runs on the whole file **before** any DataFrame is returned, so no partial result can exist.
6. **Amount:** `str.replace(".", "")`, then `str.replace(",", ".")`, then `float`, then × sign. An unparsable amount → `ValueError` naming the value; no silent NaN drop, because a lost transaction is as wrong as a wrong sign.
7. **Date:** `pd.to_datetime(Transactiedatum, format="%d-%m-%Y")`; where `Transactiedatum` is empty, use `Boekdatum` (same format). Unparsable → `ValueError`.
8. **Mapping** exactly as in the brief: `rekening`, `tegenrekening`, `naam`, `omschrijving` (`naam` if empty after strip), `valuta`, `saldo_voor = 0.0`, `rekeningtype`.
9. **Output columns:** `datum, rekening, tegenrekening, naam, valuta, saldo_voor, bedrag, omschrijving, rekeningtype`, in the same order as `RaboParser`.
10. **Error handling:** unlike Rabo/SNS, `parse_csv` does **not** wrap the whole thing in `except Exception`. Format errors are `ValueError`s and propagate (brief constraint). `FileNotFoundError` also propagates; the importer checks existence first anyway. Prints the same kind of summary as the other parsers (`✓ <file> succesvol gelezen: N transacties`, period).

`is_knab_file(filepath)`: reads the first 20 csv rows with the same reader and encoding fallback, and returns `True` if any row contains both marker columns. Any read error returns `False`, so detection never crashes on foreign files.

### Config changes
- `bank_parsers.py` entry (above). No YAML changes.

### Data model / stored format changes
None. No schema change; Knab-only columns (`Betaalwijze`, `Type betaling`, `Machtigingsnummer`, `Incassant ID`, `Referentie`, `Valutadatum`) are read but not returned.

---

## Requirement mapping

| Brief requirement / acceptance criterion | Where it's handled |
|---|---|
| FR: `KnabParser` in `knab_parser.py`, Rabo interface, standard columns | `knab_parser.py` steps 8–9; `test_knab_parser.py::test_basic_rows` |
| FR: field mapping incl. `Boekdatum` fallback, `saldo_voor=0.0`, `rekeningtype` | step 7–8; `test_basic_rows`, `test_boekdatum_fallback` |
| FR: sign from CreditDebet, unknown → `ValueError` that propagates | steps 5, 10; `test_unknown_creditdebet_raises`, `test_import_unknown_creditdebet_stores_nothing` |
| FR: no NaN / `"nan"` in text, `Unnamed` dropped | steps 3–4; `test_empty_fields`, `test_basic_rows` (column check) |
| FR: header located by content, preamble skipped | step 2; `test_preamble_is_ignored` |
| FR: detection by `KNAB` filename + by header; SNS/RABO priority unchanged | `importer.py` branches; `test_knab_import.py::test_detect_by_filename`, `test_detect_by_header`, `test_rabo_filename_still_rabo` |
| FR: registered in `parsers/__init__.py`, `bank_parsers.py` | those files; `test_smoke.py` extended with `KnabParser` import |
| FR: README lists Knab | `README.md` |
| AC1: 2 rows, −6.5 / 1234.56, 2026-09-17, betaalrekening, 0.0, no `Unnamed` | `test_basic_rows` on `knab_basic.csv` |
| AC2: `"1.234,56"` Afschrijvingen → −1234.56 | `test_thousands_separator` |
| AC3: `Onbekend` → `ValueError` containing `Onbekend`; import stores 0 | `test_unknown_creditdebet_raises`, `test_import_unknown_creditdebet_stores_nothing` |
| AC4: empty tegenrekening → `""`, empty omschrijving → naam, no NaN/"nan" | `test_empty_fields` |
| AC5: preamble line → identical result | `test_preamble_is_ignored` (DataFrame equality vs. no-preamble fixture) |
| AC6: default Knab filename and `export.csv` both → KnabParser | `test_detect_by_filename`, `test_detect_by_header` (fixture copied under both names in `tmp_path`) |
| AC7: `RABO_test.csv` → RaboParser | `test_rabo_filename_still_rabo` (spy on the parsers; the fixture content is irrelevant, the dispatch is what's checked) |
| AC8: import twice into temp DB → N then 0 | `test_import_twice_is_idempotent` with `DatabaseManager(db_path=tmp_path / "t.db")` |
| AC9 `manual:` real export via GUI, month totals match | not automatable by design (no real data); goes to sign-off "What to eyeball" |

---

## High-stakes output impact

**Yes. The sign of `bedrag` decides income vs expense** in every SaldoBoek statistic, and the parser also decides which rows exist at all. Mitigations: an explicit two-value map with a hard error on anything else; no silent NaN row drops (unparsable amount or date → error); AC1/AC2/AC3 pin exact values. Existing Rabo/SNS output is untouched (AC7 guards the dispatch).

---

## Architecture notes

- [x] CLAUDE.md architecture rules respected: Python 3.8 syntax only, tests don't import `saldoboek.gui` and need no display, synthetic fixtures only, no real bank data.
- [x] No changes outside the files listed above.
- [x] Config over hardcoding: the CreditDebet map and marker columns are module-level constants in `knab_parser.py`.

**Decisions note (delegated, reversible):** the `bank_parsers.py` entry mirrors the existing (legacy, non-functional) pattern because the brief requires it. Making that legacy fallback functional would be a change to the importer beyond detection, which the brief says must park, so it stays as is. Flagged as a backlog candidate.

**Known limitation (out of scope, sign-off item):** when the importer skips a file on `ValueError`, the reason only goes to stdout. The GUI shows 0 imported without the reason. GUI changes are out of scope; this goes to backlog candidates.

---

## Test scope

- New pytest suite files as mapped above; one or more tests per AC. All fixtures are synthetic, and each is created as a file under `tests/fixtures/knab/` or written into `tmp_path` from a shared template. The BOM and trailing `;` are present in every fixture.
- Import tests use `DatabaseManager(db_path=<tmp_path Path>)`, `Categorizer(db, 1)` and `TransactionImporter(cat, db, 1)`, and count rows in `transacties` afterwards.
- Bug hunt (headless, no browser UI): run the import path with extra hand-made synthetic edge files: CRLF line endings, a file with only a header, whitespace around `CreditDebet`, a mixed debit/credit month, and a non-Knab `;` file named `export.csv` (must not be detected as Knab and must raise the existing "Onbekend bankformaat").

---

## Open questions for PO

(none)
