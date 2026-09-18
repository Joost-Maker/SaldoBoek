# Code Review: 0001 Knab CSV import

**Mode:** code gate (Phase 7)
**Reviewed:** `00-brief.md`, `01-spec.md` (rev 2), `02-spec-review.md`, `03-implementation-log.md`, `04-test-protocol.md` (coverage table), `05-bughunt-report.md` (rounds 1 and 2), `06-fixes.md`, `CLAUDE.md`, and the full diff `git diff dev...HEAD` (10 commits, 17 files). No real bank data, no `saldoboek/data/database.db` and no other `*.db` were opened. The only files used were synthetic probes written into a scratch temp dir with the suite's own `render_knab`/`knab_row` helpers.

**Test command (run by the gate):** `.venv/bin/python -m pytest -q` → **26 passed** in 1.11s (Python 3.12.3, pandas 3.0.6). This matches `06-fixes.md` ("26 passed"). All touched `.py` files also parse under `ast.parse(feature_version=(3, 8))`.

---

## 1. Contract: acceptance criteria against the built code

| AC | Verdict | Evidence |
|---|---|---|
| AC1: 2 rows, −6.5 / 1234.56, 2026-09-17, `betaalrekening`, 0.0, no `Unnamed` | met | `tests/test_knab_parser.py::test_basic_rows` also pins the exact column order and the mapped text values. Fixture: BOM, all fields quoted, trailing `;`, CRLF (`tests/conftest.py:61-72`) |
| AC2: `"1.234,56"` Afschrijvingen → −1234.56 | met | `test_thousands_separator` |
| AC3: `Onbekend` → `ValueError` containing `Onbekend`; import stores 0 | met | `test_unknown_creditdebet_raises` (parser). `test_knab_import.py::test_import_unknown_creditdebet_stores_nothing` (a real import into a temp DB, `total == 0` and `COUNT(*) == 0`). The check runs over the whole file before any frame exists (`knab_parser.py:182-188`) |
| AC4: empty `Tegenrekeningnummer` → `""`, empty `Omschrijving` → `naam`, no NaN/`"nan"` | met | `test_empty_fields` checks every text column |
| AC5: a preamble line gives an identical result | met | `test_preamble_is_ignored` uses `assert_frame_equal` |
| AC6: the default Knab filename and `export.csv` both → KnabParser | met | `test_detect_by_filename` and `test_detect_by_header` (spies). `test_detect_by_header_parses_for_real` covers the end-to-end path |
| AC7: `RABO_test.csv` → RaboParser | met | `test_rabo_filename_still_rabo`. The SNS/RABO branches are unchanged, and Knab comes after them (`importer.py:34-42`) |
| AC8: two imports → N then 0 | met | `test_import_twice_is_idempotent` (N=3, and it also pins the stored signed amounts) |
| AC9 `manual:` real export via the GUI, month totals to the cent | correctly manual | Only Joost has real data. See the sign-off notes below, which bear on it |

Functional requirements: the parser file/class/interface, the mapping including the `Boekdatum` fallback, the sign map with a hard `ValueError` and no `except Exception` wrapper, no NaN text, the header located by content, detection by filename and by header, registration in `core/parsers/__init__.py` and `config/bank_parsers.py`, and the README line are all present in the diff.

**Out of scope held:** no schema change, no GUI/Categorizer/seed-rule/Rabo/SNS change, no LLM work, no new dependency, no `.gitignore` change, and no `*.csv`/`*.db` committed. The importer change is exactly the detection change the brief allows (+1 import, +1 attribute, +2 `elif` branches). The brief's one sanctioned exception, a `ValueError` surfacing to the existing `except ValueError`, needed no importer code.

## 2. Spec fidelity and decision audit

- Decision 1 (fixtures generated into `tmp_path` rather than committed under `tests/fixtures/knab/`) is logged with the rejected alternative, as the spec gate required. The brief delegates test layout. OK.
- Decision 3 (`elif is_knab_file` placed before `else` rather than inside it) gives identical control flow. I verified it. OK.
- Decisions 2 and 4 are internal to the parser and reversible. OK.
- The round-1 fix (`KNAB_REQUIRED_COLUMNS`: the header must contain all 9 mapped columns, `knab_parser.py:17-27, 123-127`) is stricter than the spec's two-marker header rule. It's recorded in `06-fixes.md` with regression tests, it stays in the parser, it's reversible, and it closes the only 🔴. Acceptable.
- **E-1 PO decision:** the fix would change the importer's duplicate key or the schema, and the brief says both must park. Joost decided interactively (commit `73af795`) that E-1 is out of scope for 0001 and tracked as its own DEV item. That is a legitimate PO call on pre-existing importer behaviour, not a unilateral pipeline decision. OK. Its effect on AC9 is flagged below.
- No undocumented behavioural deviation from the spec was found. The residual gaps against spec steps 6 and 7 are listed as notes because they're triggered only by inputs outside the verified Knab format.

## 3. Findings (non-blocking, by severity)

- **🟡 Amount and date validation is looser than spec steps 6 and 7 promise** (`knab_parser.py:227-239`, `:196-205`). Gate probes on synthetic files: `Bedrag "-6,5"` + `Afschrijvingen` parses to **+6.5** (a sign flip), `Bedrag "NaN"` parses to a NaN amount with no error, `Transactiedatum "today"` imports with today's timestamp, and `"nan"` as a date raises a `ValueError` from `_print_import_summary`'s `strftime` rather than from the date check. The hunt found these too (round 1 E-3, round 2 R2-1). A real Knab export never produces them (the brief says it's unsigned, decimal comma, `dd-mm-yyyy`), so they aren't blocking. They sit on the exact high-stakes axis (sign and existence of rows), though. A strict regex on `Bedrag` and on the date text, plus `datum.isna()` → `ValueError`, closes all of them in a few lines. **Recommended before the upstream PR.**
- **🟡 Short rows are padded silently** (`knab_parser.py:143`, round-1 E-5). The spec allows it ("cut or padded"), so it's a backlog item.
- **🟢 Non-`ValueError` parse failures abort a multi-file import:** a duplicate header column gives `AttributeError` (E-6). `csv.Error` from `_read_rows` isn't converted either. Both are backlog items.
- **🟢 Dead branch:** `text()`'s `if column not in df.columns` fallback (`knab_parser.py:178-179`) can no longer be reached for any column it's called with, now that `KNAB_REQUIRED_COLUMNS` is enforced. Harmless.
- **🟢 `tests/__init__.py` (new, empty)** isn't in the spec's file list or the log. It exists so tests can do `from .conftest import knab_row`. That's delegated test layout, but importing helpers from `conftest.py` is a pytest anti-pattern. A `tests/helpers.py` would be cleaner. It doesn't matter for this merge.
- **🟢 Numbering mismatch in `06-fixes.md`:** it calls the header fix "E-3 (header part)" and the amount forms "E-3", while `05-bughunt-report.md` numbers them E-4 and E-3. The round-2 report already reconciles this. `06-fixes.md` predates round 2, so R2-1 is missing from its backlog list. Carry R2-1 into the sign-off backlog.

## 4. Diff hygiene

- Every commit references `0001-knab-csv-parser`, and the trail is clean: brief, spec, gate, feat, test, hunt, fix, PO decision, hunt round 2.
- There are no debug prints beyond the parser's summary output, which matches the other parsers. There's no dead code apart from the note above, and no files outside the spec scope apart from `tests/__init__.py`.
- The high-stakes output (the sign of `bedrag`) is declared in the spec and pinned by AC1, AC2, AC3 and AC8 (stored values). Existing Rabo/SNS output is untouched.
- Upstream hygiene: the code files contain no fork-only content. `tests/test_smoke.py` and `tests/__init__.py` came from or with the fork scaffold. Whether they go into the upstream PR is Joost's call.

## 5. Test accretion

Every automatable AC (AC1–AC8) has a committed permanent test, named in the `04-test-protocol.md` coverage table, and each named test exists in the diff and passes. AC9's `manual:` label is justified: it needs real bank data, which agents may not touch. Every fixed bug also has a regression test: BUG-1 ×2, E-4 header, E-2 ×2.

## Notes for sign-off (AC9, which only Joost runs)

- **E-1:** identical same-day transactions (same date, account, amount and description, e.g. two identical card payments) are dropped as duplicates by the existing importer key. If a month contains any, AC9's "totals match to the cent" will fail for that reason and not because of the parser. That's the separate DEV item.
- A Knab file skipped on `ValueError` shows only "0 imported" in the GUI. The reason goes to stdout (a known limitation in the spec). If the real export is rejected, run the import from a terminal to see why.
- The header now requires all 9 mapped columns. If a real export (e.g. from a savings account) uses a different header, it will be rejected loudly rather than imported wrongly.

Verdict: approved with notes
