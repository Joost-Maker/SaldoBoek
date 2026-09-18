# Bug Hunt Report
**Date (UTC):** 2026-09-18T08:57:35Z
**Feature / scope:** Knab CSV import for SaldoBoek (0001-knab-csv-parser)
**Test protocol:** docs/features/0001-knab-csv-parser/04-test-protocol.md
**App URL:** none (desktop app, no browser UI; driven headless in Python)
**Round:** 1

---

## Environment
- Browser / driver: n/a. The app has no browser UI and PySide6 is not installed in `.venv`, so the skill's Playwright steps don't apply. Every case was driven headless with `.venv/bin/python` (3.12.3, pandas 3.0.6): `KnabParser().parse_csv(path, "betaalrekening")`, `TransactionImporter.detect_bank_and_parse` and `import_transactions_with_categorization` against a fresh temp `DatabaseManager(db_path=Path(<tmp>)/"t.db")` per case. Evidence per finding: exact input, the call, and the observed output (stands in for screenshots). "Console errors" = uncaught exceptions / tracebacks on stdout/stderr.
- App version / last commit: branch `feat/0001-knab-csv-parser` @ `19c7c9b`. Baseline: `pytest` 21 passed.
- Test data: 100% synthetic, generated in a `mktemp -d` scratch dir outside the repo with `tests/conftest.py` helpers (`knab_row`, `render_knab`) or hand-written bytes. Fake IBANs (`NL00KNAB0000000000`, `NL00INGB0000000000`), fake names. No real export, no `saldoboek/data/database.db`, nothing under `~/Code/Financien` was opened.

---

## Test results

Common harness (scratch dir, not the repo): `write(name, rows, preamble=…)` renders rows with `tests/conftest.py::render_knab` (BOM, all fields quoted, trailing `;`, CRLF) into a fresh temp dir; `parse(p) = KnabParser().parse_csv(str(p), "betaalrekening")`; `new_importer()` = `TransactionImporter(Categorizer(db,1), db, 1)` on `DatabaseManager(db_path=Path(mkdtemp())/"t.db")`. Default row = `knab_row()` (`NL00KNAB0000000000`, `17-09-2026`, `Afschrijvingen`, `6,5`, `NL00INGB0000000000`, `Test Uitgever B.V.`, `Testblad termijnbetaling`).

### 1. `KnabParser.parse_csv`

### 1.1 Happy path
- **Tested:** file bytes start `b'\xef\xbb\xbf"Rekeningnummer";"Transactiedatum";…'`; rows `knab_row("Afschrijvingen","6,5")`, `knab_row("Bijschrijvingen","1234,56", naam="Test Werkgever B.V.", omschrijving="Salaris")`; `parse(p)`.
- **Expected:** bedrag −6.5 / 1234.56, datum 2026-09-17, 9 standard columns, saldo_voor 0.0.
- **Actual:** columns `['datum','rekening','tegenrekening','naam','valuta','saldo_voor','bedrag','omschrijving','rekeningtype']`, bedrag `[-6.5, 1234.56]`, datum `[2026-09-17, 2026-09-17]`, saldo_voor `[0.0, 0.0]`, rekeningtype `betaalrekening` ×2, no `Unnamed` column.
- **Severity:** ✅ pass
- **Console errors:** none

### 1.2 Thousands separator
- **Tested:** `knab_row("Afschrijvingen","1.234,56")` → `parse`.
- **Actual:** bedrag `[-1234.56]`.
- **Severity:** ✅ pass

### 1.3 Unknown sign
- **Tested:** two-row files (valid row + one row with CreditDebet `Onbekend` / `""` / `afschrijvingen` / `Afschrijving`, bedrag `10`).
- **Expected:** `ValueError` naming the value, never a DataFrame.
- **Actual:** all four raise `ValueError: Onbekende CreditDebet-waarde(n) in …/k.csv: 'Onbekend'` (resp. `''`, `'afschrijvingen'`, `'Afschrijving'`). No DataFrame returned.
- **Severity:** ✅ pass

### 1.4 Empty fields
- **Tested:** `knab_row(tegenrekening="", omschrijving="")`.
- **Actual:** `tegenrekening == ''`, `omschrijving == 'Test Uitgever B.V.' == naam`; `df.isna().any().any() == False`; no cell equals `"nan"`.
- **Severity:** ✅ pass

### 1.5 Preamble line
- **Tested:** same 2 rows as 1.1 with and without `preamble="KNAB EXPORT"`.
- **Actual:** `a.equals(b) == True`.
- **Severity:** ✅ pass

### 1.6 CRLF vs LF
- **Tested:** same content with `\r\n` replaced by `\n`; bonus: CR-only (`\r`).
- **Actual:** both `equals` the CRLF result → `True`.
- **Severity:** ✅ pass

### 1.7 Whitespace around CreditDebet
- **Tested:** `knab_row(" Afschrijvingen ","6,5")`.
- **Actual:** bedrag −6.5.
- **Severity:** ✅ pass

### 1.8 Header only
- **Tested:** `render_knab([])` → `parse`.
- **Actual:** empty DataFrame with the 9 standard columns, prints `✓ k.csv succesvol gelezen: 0 transacties` with no "Periode" line, no crash.
- **Severity:** ✅ pass

### 1.9 Mixed month (12 rows)
- **Tested:** 12 rows, dates 01..12-09-2026: A `0,01`, B `10`, A `99,9`, B `1.000,00`, A `1.234,56`, B `0,01`, A `10`, B `99,9`, A `12.345.678,9`, B `2500`, A `0,1`, B `7,05` (A = Afschrijvingen, B = Bijschrijvingen). Hand calculation with `Decimal`.
- **Actual:** all 12 sign+amount pairs exact (`-0.01, 10.0, -99.9, 1000.0, -1234.56, 0.01, -10.0, 99.9, -12345678.9, 2500.0, -0.1, 7.05`). Debits: hand −12347023.47 = parser −12347023.47. Credits: hand 3616.96 = parser 3616.96. 12 rows in, 12 out.
- **Severity:** ✅ pass

### 1.10 Filled extra cell
- **Tested:** (a) data row ending `…"17-09-2026";"X"` (value in 16th, unnamed column); (b) row ending `…"17-09-2026";"";"Y";` (17th column); (c) control: `…;"";"";` (extra but empty cells).
- **Actual:** (a) and (b) `ValueError: Rij 2 in …/k.csv heeft meer gevulde velden dan de header`. (c) parses 1 row, which is correct.
- **Severity:** ✅ pass

### 1.11 Bad amount / date
- **Tested:** valid row + row with `bedrag="abc"`; valid row + row with `datum="2026/09/17"` (all three date columns); valid row + row with only Transactiedatum `2026/09/17` and Boekdatum `17-09-2026`.
- **Actual:** `ValueError: Onleesbaar bedrag in …: 'abc'`; `ValueError: Onleesbare datum in …: time data "2026/09/17" doesn't match format "%d-%m-%Y" …` for both date variants (the Boekdatum fallback applies only to *empty* Transactiedatum, as specified). Whole file rejected, no partial DataFrame. (The file-level skip in the import loop is covered in 2.4/2.7.)
- **Severity:** ✅ pass

### 1.12 Quote in preamble — silent wrong output (BUG-1)
- **Tested:** 3-row file (A `6,5` "een", B `1234,56` "twee", A `3` "drie") with three preambles:
  1. `Export van "Knab` (the protocol's example: quote mid-field) → 3 rows, `rekening == NL00KNAB0000000000`. Correct: the csv module treats a mid-field quote as a literal.
  2. `"Export van Knab` (quote at the start of the line, unbalanced)
  3. `"Export;van Knab`
- **Expected:** header found and correct output, or a `ValueError`. Never partial or wrong data.
- **Actual (2 and 3):** the csv module opens a quoted field on the preamble and closes it on the header's first `"`, so the preamble and the header merge into one csv row: `row0[:2] == ['Export van Knab\r\nRekeningnummer"', 'Transactiedatum']`. That row still contains `CreditDebet` and `Tegenrekeninghouder`, so `_is_header` accepts it as the header. The first column is now named `Export van Knab\r\nRekeningnummer"` instead of `Rekeningnummer`, so `text("Rekeningnummer")` falls back to `""` for every row. Parse reports success:
  ```
  ✓ k.csv succesvol gelezen: 3 transacties
         datum rekening   bedrag omschrijving
  0 2026-09-17             -6.50          een
  1 2026-09-17           1234.56         twee
  2 2026-09-17             -3.00         drie
  ```
  Import: `✓ 3 nieuwe transacties geïmporteerd`, and every stored row has `rekening = ''`. It gets worse: the rekening is part of the duplicate key, so importing the **same** rows again from a clean file stores them a second time. `first (quoted preamble): 3`, `second (same rows, clean): 3`, `total rows 6`, `SUM(bedrag)` 2450.12 instead of 1225.06. The same happens via `detect_bank_and_parse("export.csv")` (header detection path).
- **Severity:** 🔴 Critical. The protocol defines wrong silent output here as 🔴, and the result is silent corruption: the account IBAN is lost and re-imports double-count. **Realism caveat for the PO:** the brief says the real Knab export has no preamble at all. This only fires if a file has a preamble line starting with an unbalanced `"`. The root cause is broader than preambles, though: any header that contains the two marker columns is accepted, and any missing standard column silently becomes `""` (see exploratory E-3).
- **Console errors:** none (that is the problem)
- **Reproduction:**
  1. Write `'"Export van Knab\r\n' + render_knab(rows)[1:]` (or `render_knab(rows, preamble='"Export van Knab')`) to `k.csv`.
  2. `KnabParser().parse_csv("k.csv", "betaalrekening")["rekening"]` → all `''`.
  3. Import it into a temp DB, then import the same rows without the preamble → 2× rows stored.

### 1.13 Encoding cp1252
- **Tested:** `render_knab([knab_row(naam="Café Test B.V.", omschrijving="Crème brûlée €5")])` with the BOM stripped, encoded cp1252 (byte `\xe9` present), named `Knab Transactieoverzicht Test.csv`. Bonus: UTF-8 without a BOM.
- **Actual:** naam `'Café Test B.V.'`, omschrijving `'Crème brûlée €5'`, bedrag −6.5. UTF-8 without a BOM: `'Café Test B.V.'`.
- **Severity:** ✅ pass

### 2. `detect_bank_and_parse` + `import_transactions_with_categorization`

Routing was checked by patching `KnabParser/RaboParser/SNSParser.parse_csv` with recorders (`mock.patch.object(..., autospec=True)`), then re-run unpatched for real output.

### 2.1 Default Knab filename
- **Tested:** `Knab Transactieoverzicht Test NL00KNAB0000000000 - 2026-01-01 - 2026-09-17.csv`.
- **Actual:** routed to `['Knab']`. Unpatched: bedrag `[-6.5, 1234.56]`.
- **Severity:** ✅ pass

### 2.2 Renamed Knab file
- **Tested:** the same content as `export.csv`.
- **Actual:** routed to `['Knab']` via header detection. Unpatched: bedrag `[-6.5, 1234.56]`.
- **Severity:** ✅ pass

### 2.3 Rabo priority
- **Tested:** `RABO_test.csv` (content `whatever;content`); Knab-formatted `RABO_knab.csv`; bonus: Knab-formatted `SNS_knab.csv`.
- **Actual:** `['Rabo']`, `['Rabo']`, `['SNS']`. Unpatched, `RABO_knab.csv` goes through the existing RaboParser: `Fout bij lezen van …RABO_knab.csv: Ontbrekende kolommen: ['Datum', 'Bedrag', 'IBAN/BBAN']` → empty DataFrame (existing Rabo swallow behaviour, as specified).
- **Severity:** ✅ pass

### 2.4 Unknown sign, full import
- **Tested:** `Knab Transactieoverzicht Bad.csv` = [valid, `Onbekend 10`, `Bijschrijvingen 5`] imported into an empty temp DB.
- **Actual:** stdout `! Onbekende CreditDebet-waarde(n) in …Bad.csv: 'Onbekend'`; return `0`; `COUNT(*) = 0`.
- **Severity:** ✅ pass

### 2.5 Idempotent import
- **Tested:** 3-row Knab file imported twice into the same temp DB.
- **Actual:** first `3` (count 3), second `0` with `! 3 duplicaten overgeslagen` (count 3). Stored rows correct (−6.5, 1234.56, −12.95; rekening `NL00KNAB0000000000`).
- **Severity:** ✅ pass (but see exploratory E-1: the same duplicate key also drops *genuine* identical transactions)

### 2.6 Non-Knab `;` file
- **Tested:** `export.csv` with the header `"Datum";"Naam";"Rekening";"Bedrag";"Af Bij"`.
- **Actual:** `ValueError: Onbekend bankformaat in bestandsnaam: EXPORT.CSV`. Not treated as Knab.
- **Severity:** ✅ pass

### 2.7 Two files at once
- **Tested:** [bad (`Onbekend`), good (3 rows)] in one call, in both orders, each into a fresh temp DB.
- **Actual:** in both orders the bad file prints `! Onbekende CreditDebet-waarde(n) … 'Onbekend'` and is skipped; the good file imports 3; return 3, count 3.
- **Severity:** ✅ pass

### High-stakes output checks
| Output | Input | Expected | Observed | |
|---|---|---|---|---|
| bedrag sign | Afschrijvingen `6,5` | −6.5 | −6.5 (1.1) | ✅ |
| bedrag sign | Bijschrijvingen `1234,56` | 1234.56 | 1234.56 (1.1) | ✅ |
| bedrag thousands | Afschrijvingen `1.234,56` | −1234.56 | −1234.56 (1.2, 1.9) | ✅ |
| bedrag small | Bijschrijvingen `0,01` | 0.01 | 0.01 (1.9) | ✅ |
| rejected sign | `Onbekend` | ValueError, 0 stored | ValueError, count 0 (1.3, 2.4) | ✅ |
| datum | `17-09-2026` | 2026-09-17 | 2026-09-17 (1.1) | ✅ |

### Regression scope
- [x] Rabo/SNS filename priority holds (2.3).
- [x] Unknown-bank rejection still raises "Onbekend bankformaat" (2.6).
- [x] Import loop skips a ValueError file and continues (2.7).

---

## Exploratory pass

**Timebox:** ~15 min of unscripted runs (same harness) · **Focus areas tried:** make it import a wrong sign (signed, dot-decimal, NaN/inf/exponent/unicode-digit amounts); make it lose a row (identical transactions, empty dates, truncated/cut files, unbalanced quotes inside data rows, shifted columns, concatenated exports, blank lines); make it accept garbage (missing/renamed/duplicate header columns, 0-byte, BOM-only, UTF-16, binary, 25-line preamble); volume (20 000 random rows, exact `Decimal` cross-check; 3 000-row import with DB total cross-check).

### [exploratory] E-1 Genuine identical transactions in one file are silently dropped as "duplicates"
- **Tested:** one file with 4 genuine rows: two coffees `Afschrijvingen 3,2` at `Test Koffiebar` (empty omschrijving, so omschrijving = naam) with different `Referentie` (`REF…1`/`REF…2`), and two `Bijschrijvingen 10` "Tikkie etentje" from **different** people (`Test Persoon A` / `NL00INGB0000000001`, `Test Persoon B` / `NL00INGB0000000002`). All on 17-09-2026. Imported into an empty temp DB.
- **Expected:** 4 rows stored; the brief's AC9 says "All rows import … totals match the Knab app to the cent".
- **Actual:** parser returns 4 rows (sum 13.6), but the import prints `✓ 2 nieuwe transacties geïmporteerd` / `! 2 duplicaten overgeslagen`; count 2, stored sum 6.8. Persoon B's €10 and the second coffee are gone. The duplicate key in `import_transactions_with_categorization` is `(datum, rekening, bedrag, omschrijving, gebruiker_id)`. It ignores `naam`/`tegenrekening`, and Knab's only unique field (`Referentie`) is deliberately not stored.
- **Severity:** 🟠 High. Silent loss of real transactions under plausible conditions (same-day, same-amount, same-text payments), and it defeats AC9. The dedupe code predates this feature, but Knab data is especially exposed: empty Omschrijving falls back to naam, and Referentie is dropped. The fix touches the importer or schema, which the brief says must park, so it needs a PO decision.
- **Console errors:** none (silent)
- **Reproduction:** 1. Build the 4 rows above with `knab_row(...)` (set `row[13]` for Referentie). 2. `import_transactions_with_categorization([p], 1, "betaalrekening")` into a temp DB. 3. `SELECT COUNT(*)` → 2.

### [exploratory] E-2 A row with empty Transactiedatum and Boekdatum passes the parser as NaT, then crashes the import halfway (partial import)
- **Tested:** `NoDate.csv` = [r1 valid, r2 valid, r3 `datum="", boekdatum=""`, r4 valid] plus a second valid file `Other.csv`, in one `import_transactions_with_categorization` call.
- **Expected:** per the parser's contract ("onleesbare datum → ValueError, geen deelresultaat"), a `ValueError` before any row is stored, the file skipped, and `Other.csv` still imported.
- **Actual:** `pd.to_datetime("", format="%d-%m-%Y", errors="raise")` returns `NaT` instead of raising, so the parser returns 4 rows (`datum=['2026-09-17', 'NaT']` in the 2-row variant). The import loop then fails outside its `try`:
  ```
  File ".../saldoboek/core/importer.py", line 84
      datum_str = row["datum"].strftime("%Y-%m-%d")
  ValueError: NaTType does not support strftime
  ```
  The exception escapes `import_transactions_with_categorization`. Stored: `['r1', 'r2']`, count 2. r4 is lost and `Other.csv` is never processed. (If *every* row lacks a date, the same `ValueError` comes from `_print_import_summary` instead, so the file is skipped with the unhelpful message `NaTType does not support strftime`.)
- **Severity:** 🟠 High. The specified error path doesn't hold for empty dates: a partial import plus an uncaught exception that aborts the rest of a multi-file import. The trigger is uncommon (both date fields empty), which is why this isn't 🔴.
- **Console errors:** traceback above, verbatim.
- **Reproduction:** `knab_row(datum="", boekdatum="")` between valid rows → import → count = number of rows before it, exception raised.

### [exploratory] E-3 Amount parsing accepts non-Knab number forms, including a pre-signed amount that flips the sign
- **Tested:** single `Afschrijvingen` rows with various `Bedrag` values → `parse`.
- **Actual:**
  | Bedrag | bedrag out | note |
  |---|---|---|
  | `-6,5` | **+6.5** | debit becomes a credit (sign × sign) |
  | `6.5` / `6.50` | −65.0 / −650.0 | dot-decimal read as thousands separator, ×10 / ×100 |
  | `1,234.56` | −1.23456 | English format silently ÷1000 |
  | `NaN` / `nan` | NaN | stored as SQL `NULL`; re-importing the file stores it **again** every time (`NULL = NULL` never matches the duplicate check): count 3 → 4 |
  | `inf` / `-inf` | −inf / +inf | stored `inf`; `SUM(bedrag)` becomes `inf` |
  | `1e3`, `1_000` | −1000.0 | |
  | `٦,٥`, `６,５` (Arabic-Indic/full-width digits) | −6.5 | |
  | `1.2.3,4` | −123.4 | |
  `6,5 EUR`, `€6,5`, `6,,5`, `""`, `(6,5)` are correctly rejected.
- **Expected:** "never import a guessed sign / unreadable amount → ValueError". Knab's `Bedrag` is unsigned `\d{1,3}(\.\d{3})*(,\d+)?`, so anything else should be rejected.
- **Severity:** 🟡 Medium. The brief says real Knab exports are unsigned with a decimal comma, so a clean export never hits this. But a hand-edited or spreadsheet-re-saved file silently imports wrong signs and ×100 amounts, which is the failure this parser was built to prevent. `float()` is the permissive step: a strict regex check before converting would close all of it.
- **Console errors:** none
- **Reproduction:** `parse(write("k.csv",[knab_row("Afschrijvingen","-6,5")]))["bedrag"]` → `[6.5]`.

### [exploratory] E-4 Header acceptance only checks the two marker columns; a missing or renamed `Rekeningnummer` silently becomes `""`
- **Tested:** header variants with one column removed (and its field removed from the row), or renamed.
- **Actual:** missing `Rekeningnummer` → parses, `rekening=['']`. Renamed to `Rekening nummer` → parses, `rekening=['']`. Missing `Valutacode`/`Tegenrekeningnummer`/`Boekdatum`/`Transactiedatum` → silently `""`/fallback. Missing `Bedrag` or renamed `Bedrag (EUR)` → correct `ValueError: Onleesbaar bedrag …: ''` (by accident, via the empty-string path). Missing both date columns → `ValueError: NaTType does not support strftime` (see E-2). This is the same root cause as BUG-1: `_is_header` accepts any row with `CreditDebet` + `Tegenrekeninghouder`, and `text()` returns `""` for absent columns. An empty `rekening` also breaks later dedupe (BUG-1 shows the double count).
- **Severity:** 🟡 Medium. It needs a changed or damaged header, but the output is silently wrong. Requiring the full set of mapped columns (`Rekeningnummer`, `Transactiedatum`, `CreditDebet`, `Bedrag`, `Tegenrekeninghouder`, …) in `_is_header`, or right after it, fixes this and BUG-1 together.
- **Reproduction:** `render_knab([row_without_col0], header=KNAB_HEADER[1:])` → `parse` → `rekening == ''`.

### [exploratory] E-5 Short rows are silently padded: a truncated file imports a mangled last row, and re-importing the full file double-counts it
- **Tested:** (a) file cut mid-field inside the last row's naam (`…"NL00INGB0000000000";"Test `), imported, then the complete file imported into the same DB. (b) A data row whose Omschrijving has an unbalanced leading quote (`"A1;"";"000…`). (c) A row truncated after 6 fields.
- **Actual:** (a) cut import: `3` rows, the last one stored with naam `Test`, omschrijving `Test`. Full re-import: `✓ 1 nieuwe transacties` (the −3.00 again, now with omschrijving `C3`). The DB has 4 rows and `SUM = 7.5`, where the true total is 10.5. (b) Parses 3 rows, row 1 omschrijving `A1;";000000000000000"` (fields merged, later fields lost). (c) Parses, naam/omschrijving `''`. By contrast, shifted-left/right rows, a missing CreditDebet and concatenated exports are all rejected correctly.
- **Expected:** a row with fewer fields than the header (Knab always writes 15 + trailing `;`) is corruption and should raise, like the "meer gevulde velden" check does for too many.
- **Severity:** 🟡 Medium. It needs a truncated or malformed file, but the result is silent and leads to double counting on re-import.
- **Reproduction:** `cut = full[:full.rfind('"Test Winkel"')+6]` → import cut → import full → 4 rows, sum 7.5.

### [exploratory] E-6 Duplicate header column name crashes the whole import with an uncaught AttributeError
- **Tested:** header with `Boekdatum` renamed to a second `Bedrag` (value `999`), imported together with a valid file.
- **Actual:** `AttributeError: 'DataFrame' object has no attribute 'str'` escapes `import_transactions_with_categorization` (only `ValueError` is caught). Count 0, and the valid second file is not imported.
- **Severity:** 🟢 Low. Garbage header, very unlikely from Knab, but it should be a `ValueError` so the import loop skips the file.
- **Reproduction:** `h=list(KNAB_HEADER); h[14]="Bedrag"` → `render_knab([r], header=h)` → import with a second file.

### No-issue observations (exploratory)
- 20 000 random rows (amounts 0,01 … 5.000,00, mixed signs): parse 0.13 s, **0** per-row amount mismatches vs `Decimal`, total 805151.44 exact. 3 000-row import: DB total −27976.48 = hand total (import 13.4 s, from the importer's existing per-row duplicate queries; not new).
- Correctly rejected: dates `17-09-26`, `31-02-2026`, `17-09-2026 10:00`, `2026-09-17`, `17.09.2026`, `00-09-2026`, `17-13-2026`; concatenated exports (second header → `'CreditDebet'` rejected); shifted columns; 0-byte / BOM-only / UTF-16 / binary files (all a clean `ValueError`, skipped). Accepted but harmless: `17-9-2026`, `1-1-2026`. Accepted and odd: `17-09-0026`, `17-09-9999` (year not range-checked).
- Embedded `;` and CRLF inside quoted Omschrijving, blank lines, and a properly escaped `""` quote all parse correctly.
- `is_knab_file` only scans 20 rows: a 25-line preamble under a generic name gives "Onbekend bankformaat" (safe failure). The same file with `Knab` in the name parses fine.

---

## Summary

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | BUG-1 (1.12): preamble starting with an unbalanced `"` merges into the header; parse "succeeds" with `rekening=''` on every row, and re-importing the clean file double-counts | 🔴 | `knab_parser.py` `_read_knab_table` / `_is_header` / `text()` fallback |
| 2 | E-1: genuine identical same-day transactions (even from different counterparties) silently dropped as duplicates; defeats AC9 | 🟠 | `importer.py` duplicate key (pre-existing; fix needs PO decision) |
| 3 | E-2: empty Transactiedatum + Boekdatum → NaT passes the parser; import crashes mid-file (partial import, later files skipped) | 🟠 | `knab_parser.py` `_process_knab_data` (`pd.to_datetime` on `""`) |
| 4 | E-3: amount parser accepts `-6,5` (sign flips to +), `6.50` (→ 650), `NaN`, `inf`, `1e3`, unicode digits | 🟡 | `knab_parser.py` `_convert_dutch_currency` |
| 5 | E-4: header accepted with only the 2 marker columns; missing/renamed `Rekeningnummer` → silent `''` | 🟡 | `knab_parser.py` `_is_header` / `text()` |
| 6 | E-5: short/truncated rows padded silently; mangled row imported, full re-import double-counts | 🟡 | `knab_parser.py` `_read_knab_table` |
| 7 | E-6: duplicate header column → uncaught `AttributeError` aborts the whole multi-file import | 🟢 | `knab_parser.py` `_process_knab_data` |

**Headline counts:** 1 🔴 · 2 🟠 · 3 🟡 · 1 🟢
**Protocol coverage:** all cases 1.1–1.13 and 2.1–2.7 run, plus the high-stakes table and all 3 regression items. 19 of 20 protocol cases pass; 1.12 fails. The adaptations: no browser/Playwright (headless Python instead, per the protocol's own tester notes); "console errors" = uncaught exceptions/tracebacks; no screenshots (exact input, call and output recorded instead). AC9 (real data) is not runnable by agents, by design. Report not committed (caller instruction: no commits).

---

## Recommended next steps

1. 🔴 BUG-1 + 🟡 E-4 (one fix): make header acceptance require every mapped column (`Rekeningnummer`, `Transactiedatum`, `CreditDebet`, `Bedrag`, `Tegenrekeninghouder`, `Omschrijving`, `Valutacode`, …) as exact, stripped names, and raise `ValueError` if any is missing, instead of falling back to `""`. Add the `'"Export van Knab'` preamble and the missing-`Rekeningnummer` header as permanent tests.
2. 🟠 E-2: treat empty or `NaT` dates as unreadable: after `pd.to_datetime`, `if datum.isna().any(): raise ValueError(...)` naming the row. Add a test for a row with both dates empty that asserts 0 rows are stored.
3. 🟠 E-1: PO decision needed. The duplicate key `(datum, rekening, bedrag, omschrijving)` drops genuine identical transactions. Options: include `naam`/`tegenrekening` in the key, count occurrences per key within a file, or store Knab's `Referentie` (a schema change, parked by the brief). At minimum, Joost should know about this before the AC9 real-data check: identical same-day payments will make the month totals differ.
4. 🟡 E-3: validate `Bedrag` strictly against `^\d{1,3}(\.\d{3})*(,\d+)?$|^\d+(,\d+)?$` before `float()`, so signed, dot-decimal, NaN/inf, exponent and non-ASCII digits raise `ValueError`.
5. 🟡 E-5: reject data rows with fewer fields than the header (mirror of the "meer gevulde velden" check), apart from fully blank lines.
6. 🟢 E-6: catch non-`ValueError` parse failures (or check for duplicate header names) so a malformed file is skipped rather than aborting the import loop.
