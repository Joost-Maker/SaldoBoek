# Spec Review — 0001 Knab CSV import (spec rev 1)

**Mode:** spec gate (Phase 2)
**Reviewed:** `00-brief.md`, `01-spec.md` (rev 1), `CLAUDE.md`, and the code the spec touches (`saldoboek/core/importer.py`, `core/parsers/{__init__,rabo_parser}.py`, `config/bank_parsers.py`, `saldoboek/parsers/__init__.py`, `core/database.py`, `core/categorization.py`, `services/transaction_service.py`, GUI import path, `tests/test_smoke.py`, `.gitignore`, `pyproject.toml`, `README.md`). No real bank data or `*.db` files were opened.

---

## Claims verified against the code

- `detect_bank_and_parse` uppercases the basename, and SNS then RABO are explicit branches before the legacy `BANK_PARSERS` loop. Correct (`saldoboek/core/importer.py:30-42`). Adding `elif "KNAB"` after RABO keeps their priority unchanged.
- `import_transactions_with_categorization` catches `ValueError` from `detect_bank_and_parse`, prints it and `continue`s (`importer.py:64-68`). A propagating Knab `ValueError` therefore stores 0 rows with no importer change. Correct.
- `BANK_PARSERS` method names (`parse_rabo_csv`, `parse_sns_csv`) don't exist on `TransactionImporter`, and the loop is unreachable for RABO/SNS/KNAB filenames. The "legacy, consistency only" claim is correct (`config/bank_parsers.py:1-5`).
- The `RaboParser` interface and account-type resolution order (argument, then constructor, then interactive `_ask_account_type`) match `rabo_parser.py:24-46`. Output column order matches `rabo_parser.py:134-146`.
- `DatabaseManager(db_path=...)` needs a `Path` because it calls `db_path.parent.mkdir` (`database.py:19-23`). The spec's `tmp_path / "t.db"` is right. `Categorizer(db, 1)` matches `categorization.py:7`.
- The duplicate check keys on `datum, rekening, bedrag, omschrijving, gebruiker_id` (`importer.py:78-91`). Because a Knab `omschrijving` falls back to `naam`, it is deterministic, so AC8 is achievable.
- The GUI passes real file paths plus an explicit `account_type` to the importer (`services/transaction_service.py:199-209`, `gui/viewmodels/import_viewmodel.py:113`). Its bank dropdown is "display only, actual parsing auto-detects" (`gui/views/import_view.py:73-79`), so AC9 needs no GUI change. The spec is right to leave the GUI alone.
- README "🏦 Ondersteunde Banken" exists at `README.md:187-192`.
- `pytest>=7.0.0` is already an optional `dev` dependency (`pyproject.toml`), so no new dependency is needed.

## Findings (by severity)

### Required: the fixtures would be git-ignored and never committed
- `.gitignore:19` contains `*.csv`. `git check-ignore -v tests/fixtures/knab/knab_basic.csv` confirms that every planned fixture under `tests/fixtures/knab/` is ignored. As written, the tests would pass locally while the fixtures they need are never committed. That breaks test accretion, breaks the suite on any fresh checkout, and leaves the upstream PR without its fixtures (the brief says that PR "carries only parser, tests, fixtures and the README line").
- The spec must pick one approach and list the file it touches:
  - (a) add a narrowly scoped negation, e.g. `!tests/fixtures/**/*.csv`, to `.gitignore`. It must stay narrow: `*.csv` is what keeps real bank exports out of git, and CLAUDE.md's "never read real bank data" rule depends on that. With this option `.gitignore` joins "Files to modify" and the upstream PR contents.
  - (b) generate every fixture at test time from Python string templates in `conftest.py` or the test module, written into `tmp_path` with a BOM, full quoting and a trailing `;`. No `.csv` gets committed, and the spec says so explicitly because the brief says fixtures "live under `tests/fixtures/knab/`".
- Either option is inside the brief. Leaving the choice to the build is not acceptable, because the failure is silent.

### Required (small): the file list is inconsistent
- The requirement-mapping table says `test_smoke.py` is "extended with `KnabParser` import", but `tests/test_smoke.py` is missing from "Files to modify". The Architecture notes also claim "No changes outside the files listed above". Add it to the list.
- The brief says "the repo has no tests yet", but `tests/test_smoke.py` already exists (a baseline smoke test from the scaffold commit). That's harmless. Extending it is fine.

### Notes (non-blocking; the programmer should apply them during the build)
- **Legacy `saldoboek/parsers/` package:** `saldoboek/parsers/__init__.py:5-10` also reads `BANK_PARSERS` and derives `__all__` from its keys. It imports `.sns_parser` / `.rabo_parser`, which don't exist, so the package is already unimportable (`ModuleNotFoundError`). Adding `'KNAB'` changes nothing that works, and fixing that package would be out of scope. The spec should mention in its Decisions note that this dead "registration" site is deliberately left untouched, so the code gate doesn't flag it as a missed FR.
- **Interactive prompt in tests:** `detect_bank_and_parse(path)` with `account_type=None` reaches `_ask_account_type` → `input()`, which fails under pytest. The AC6/AC7 tests must pass `"betaalrekening"`, or use spies that never reach the real parser.
- **`csv` module file opening:** open with `newline=""`, as the `csv` docs require. Without it, CRLF handling and quoted fields containing newlines can break, and CRLF is already on the bug-hunt list.
- **`is_knab_file` looks at 20 rows while `parse_csv` searches the whole file.** That's acceptable (the header search is delegated), but a preamble longer than 19 lines would parse through a `KNAB` filename and still not be content-detected. Log it as a decision.
- **Stricter than the brief, and acceptable:** a `ValueError` on an unparsable amount or date, and on an empty or whitespace `CreditDebet`, instead of Rabo-style silent `dropna`. That's conservative and consistent with the high-stakes declaration. It is not creep.

## Gate checklist

1. **Coverage:** every FR and AC1–AC9 maps to a concrete location and test. AC9 is correctly `manual:`. OK.
2. **Creep:** none. The `cp1252` fallback, the `is_knab_file` helper and stricter errors all stay inside the parser and are delegated or conservative. No schema, GUI, categoriser or existing-parser changes. OK.
3. **Open questions:** none. OK.
4. **Architecture:** Python 3.8 syntax, no GUI import in tests, synthetic data only, constants at module level. The high-stakes impact on the sign of `bedrag` is explicitly declared with mitigations. OK, apart from the `.gitignore` interaction above, which also touches the real-data protection.
5. **Testability:** the tests as designed would catch every AC failing, but only if the fixtures exist in the repo. That is the blocking finding above.

## Required changes for rev 2
1. Resolve the `.gitignore` `*.csv` conflict with option (a) or (b) above, and list any touched file (`.gitignore` or `conftest.py`) in "Files to create/modify" and in the upstream-PR contents.
2. Add `tests/test_smoke.py` to "Files to modify".
3. (Recommended in the same revision) add the legacy `saldoboek/parsers/` package to the Decisions note as deliberately untouched.

Verdict: changes requested
