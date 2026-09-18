---
vault_item: "DEV/SaldoBoek Knab CSV parser.md"
date: 2026-09-18
priority: Medium
---
# Feature Brief — Knab CSV import for SaldoBoek

**Date:** 2026-09-18
**Author:** Joost (PO)
**Priority:** Medium
**Scope:** One-night (buildable + verifiable in a single pipeline run)
**Repo:** fork `Joost-Maker/SaldoBoek` of `tubby1981/SaldoBoek`. Goes upstream later as a PR, after review.

---

## What and why

SaldoBoek imports only SNS and Rabobank CSVs. Joost banks with Knab. Add a `KnabParser` so a Knab export imports like the other banks, with debits negative and credits positive. This is the prerequisite for [[Local LLM bank transaction categorisation]], the GPU classifier that runs on SaldoBoek's database.

---

## User story

As Joost, I want to drop my Knab "Transactieoverzicht" CSV into SaldoBoek's import, so that my Knab transactions land in SaldoBoek with correct signs and dates, and I can budget and categorise them there.

---

## Knab export format (verified 2026-09-18 against a real export by Joost; the pipeline never reads real data)

- Encoding `utf-8-sig` (BOM). Delimiter `;`. **Every field double-quoted.** **Every line ends with a trailing `;`**, which gives pandas an empty 16th column.
- Header (15 columns): `Rekeningnummer;Transactiedatum;Valutacode;CreditDebet;Bedrag;Tegenrekeningnummer;Tegenrekeninghouder;Valutadatum;Betaalwijze;Omschrijving;Type betaling;Machtigingsnummer;Incassant ID;Referentie;Boekdatum;`
- Example row (anonymised):
  `"NL00KNAB0000000000";"17-09-2026";"EUR";"Afschrijvingen";"6,5";"NL00INGB0000000000";"DPG Media B.V.";"17-09-2026";"Periodieke incasso";"Donald Duck Junior termijnbetalingAbonr.00000000";"";"000000000000000";"NL00ZZZ000000000000";"XXXXXXXXXXXXXXXX";"17-09-2026";`
- Dates are `dd-mm-yyyy`. `Bedrag` has **no sign**, uses a decimal comma and no fixed decimals (`6,5` = 6.50). **`CreditDebet` is `Afschrijvingen` (debit) or `Bijschrijvingen` (credit)**, confirmed by Joost. Empty fields arrive as `""`.
- Default filename: `Knab Transactieoverzicht <rekeningnaam> <IBAN> - <van> - <tot>.csv`, so it contains `Knab`, not `KNAB` in capitals.

---

## Functional requirements

- [ ] New `saldoboek/core/parsers/knab_parser.py` with class `KnabParser` and the same interface as `RaboParser`: `parse_csv(filepath, account_type=None)`, returning a DataFrame with SaldoBoek's standard columns `datum, rekening, tegenrekening, naam, valuta, saldo_voor, bedrag, omschrijving, rekeningtype`.
- [ ] Mapping: `datum` ← `Transactiedatum` (`%d-%m-%Y`; `Boekdatum` if empty) · `rekening` ← `Rekeningnummer` · `tegenrekening` ← `Tegenrekeningnummer` · `naam` ← `Tegenrekeninghouder` · `omschrijving` ← `Omschrijving`, or `naam` if empty · `valuta` ← `Valutacode` · `saldo_voor` = `0.0` (Knab has no balance column) · `rekeningtype` from the argument, as the other parsers do it.
- [ ] `bedrag`: strip `.`, replace `,` with `.`, convert to float, then apply the sign: `Afschrijvingen` → negative, `Bijschrijvingen` → positive. **Any other `CreditDebet` value raises `ValueError` naming the value.** The error must propagate: it must not be swallowed into an empty DataFrame, and no rows may be imported with a guessed sign.
- [ ] Text columns never contain `NaN` or the string `"nan"`; empty fields become `""`. `Unnamed:*` columns are dropped.
- [ ] The header row is located by content: the first row that contains both `CreditDebet` and `Tegenrekeninghouder`. Any lines above it are skipped.
- [ ] Detection in `TransactionImporter.detect_bank_and_parse`: a filename containing `KNAB` (case-insensitive, same as the existing uppercasing) → `KnabParser`. **Also:** a file whose name matches no bank but whose header is Knab's → `KnabParser`. Existing SNS and RABO filename detection keeps priority and stays unchanged.
- [ ] Registered wherever the other parsers are registered (`core/parsers/__init__.py`, `config/bank_parsers.py`).
- [ ] README "Ondersteunde Banken" lists Knab.

## Out of scope (load-bearing — the pipeline may not cross this line)

- Anything LLM or GPU related. That's [[Local LLM bank transaction categorisation]].
- Storing `Betaalwijze`, `Type betaling`, `Machtigingsnummer`, `Incassant ID`, `Referentie` or `Valutadatum`. **No database schema changes.**
- Changes to `RaboParser`, `SNSParser`, `Categorizer`, the seed rules, or the GUI.
- Opening the upstream PR to `tubby1981/SaldoBoek`. The run ends at a reviewed branch in the fork; Joost opens the PR.
- **Reading Joost's real bank data** (`~/Code/Financien/*.csv` or any real export). Synthetic fixtures only.

---

## Acceptance criteria

Fixtures live under `tests/fixtures/knab/`, synthetic, with fake IBANs (`NL00KNAB0000000000` style) and fake names.

- [ ] Given a Knab fixture (BOM, all fields quoted, trailing `;`) with one `Afschrijvingen` row of `"6,5"` on `"17-09-2026"` and one `Bijschrijvingen` row of `"1234,56"`, when `KnabParser().parse_csv(path, "betaalrekening")` runs, then it returns 2 rows with `bedrag` `-6.5` and `1234.56`, `datum` 2026-09-17, `rekeningtype` `"betaalrekening"`, `saldo_voor` `0.0`, and no column whose name starts with `Unnamed`.
- [ ] Given a fixture row with `Bedrag` `"1.234,56"` and `Afschrijvingen`, when parsed, then `bedrag` is `-1234.56`.
- [ ] Given a fixture row with `CreditDebet` `"Onbekend"`, when parsed, then `ValueError` is raised and its message contains `Onbekend`. And when that file is imported through `TransactionImporter.import_transactions_with_categorization` into an empty temp database, then 0 transactions are stored.
- [ ] Given a fixture with an empty `Tegenrekeningnummer` (`""`) and an empty `Omschrijving`, when parsed, then `tegenrekening == ""` and `omschrijving` equals that row's `naam`. No text column contains `NaN` or `"nan"`.
- [ ] Given the same fixture with one extra non-CSV line above the header, when parsed, then the result equals the result without that line.
- [ ] Given a Knab fixture saved as `Knab Transactieoverzicht Test NL00KNAB0000000000 - 2026-01-01 - 2026-09-17.csv`, when `detect_bank_and_parse` runs, then `KnabParser` handles it. Given the same content saved as `export.csv`, then `KnabParser` handles it as well.
- [ ] Given a file named `RABO_test.csv`, when `detect_bank_and_parse` runs, then `RaboParser` is still used (regression).
- [ ] Given an empty temp SaldoBoek database, when the same Knab fixture is imported twice via `import_transactions_with_categorization`, then the first import stores N rows and the second stores 0 (duplicate check).
- [ ] `manual:` Joost imports his real Knab export through the SaldoBoek GUI. All rows import, and one month's income and expense totals match the Knab app to the cent. Only Joost does this; the pipeline never touches real data.

---

## Ambiguity guidance

- **Delegated (decide conservatively + log):** internal helper names, test file layout, exact error wording (as long as it contains the offending value), how the header search is implemented, pytest fixtures and conftest structure.
- **Must park:** any database schema change; any change to the behaviour of existing parsers, the categoriser or the GUI; any change to the importer beyond detection (one exception: letting the Knab `ValueError` surface to the existing `except ValueError` in `import_transactions_with_categorization`); anything that would need real bank data; adding dependencies beyond `pytest` as a dev dependency.

---

## Known constraints or dependencies

- `requires-python >= 3.8`: no `match`, no `X | Y` type unions, no 3.9+-only APIs.
- The existing parsers swallow exceptions with `except Exception: print(); return pd.DataFrame()`. `KnabParser` must **not** swallow the unknown-`CreditDebet` error (see the requirements).
- The repo has **no tests yet**. The pytest suite starts with this feature, so fixtures and test setup must not need a display or PySide6 (don't import `saldoboek.gui` in tests).
- Fork hygiene: dev-agent-team scaffolding (`CLAUDE.md`, `AGENTS.md`, `docs/`, `queue/`, `.claude/`) lives on the fork's working branch only. The later upstream PR branch carries only parser, tests, fixtures and the README line.

## Notes for Programmer

- Interface reference: `saldoboek/core/parsers/rabo_parser.py` (`_process_rabobank_data`, `_convert_dutch_currency`) and `core/importer.py`.
- Read with `sep=";"`, `quotechar='"'`, `dtype=str`, `encoding="utf-8-sig"`, and `csv`-module header detection. Don't use `decimal=","` on the raw column; do the conversion explicitly so the thousands `.` is handled.
