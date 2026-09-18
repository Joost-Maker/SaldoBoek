# SaldoBoek (Joost-Maker fork) — Claude Context

## About this project

**Project:** SaldoBoek (fork)
**Description:** Joost's fork of tubby1981/SaldoBoek, a Dutch open-source household budget app. Used to add Knab import and, later, local-GPU categorisation, with the reusable parts going back upstream.
**Developer:** Joost van Barneveld
**Tech stack:** Python ≥ 3.8, pandas, PyYAML, SQLite, PySide6 (GUI), pytest
**Status:** In progress

---

## What it does

SaldoBoek imports bank CSV exports (SNS, Rabobank; Knab being added), stores transactions in SQLite (`saldoboek/data/database.db`), categorises them with substring keyword rules (`categorisatie_regels`), and shows budgets, statistics and Excel exports in a PySide6 GUI. Multi-user (`gebruiker_id`), multiple accounts per user.

---

## Project config

<!-- Parsed by the dev-agent-team skills. Keep the exact keys. -->

- **Project name:** SaldoBoek (fork)
- **Mission:** Get Joost's Knab transactions into SaldoBoek correctly and categorised with a local GPU model, without bank data ever leaving the machine or being read by an agent, and send the generic parts upstream.
- **Vault project note:** DEV/Local LLM bank transaction categorisation.md
- **Tech stack:** Python ≥ 3.8, pandas, PyYAML, SQLite, PySide6, pytest
- **Run locally:** `.venv/bin/python main.py --gui` (needs PySide6, which the test venv doesn't install). There is no browser UI, so bug hunts exercise the import path headlessly: `TransactionImporter` / parsers against synthetic fixtures in a temp `DatabaseManager(db_path=...)`.
- **Test command:** `.venv/bin/python -m pytest -q`
- **Working branch:** dev
- **Deploy:** none. Merging into `dev` only updates the fork. Upstream contributions go as a PR from a clean branch off `upstream/main`, opened by Joost.
- **Merge policy:** manual

---

## Architecture

```
saldoboek/
├── core/
│   ├── database.py        # DatabaseManager(db_path) — SQLite schema, migrations, config seeding
│   ├── categorization.py  # Categorizer — substring rules, first match wins
│   ├── importer.py        # TransactionImporter — bank detection + import + duplicate check
│   └── parsers/           # one parser per bank → DataFrame with standard columns
├── config/                # categories.yaml, categorization_rules.yaml (seeds), bank_parsers.py
├── gui/                   # PySide6 MVVM app (main_window.py imports via TransactionImporter)
├── cli.py                 # legacy CLI
└── reports/               # Excel exports
tests/                     # pytest suite (fork-added; no GUI imports)
```

A parser's `parse_csv(filepath, account_type)` returns a DataFrame with `datum, rekening, tegenrekening, naam, valuta, saldo_voor, bedrag, omschrijving, rekeningtype`. `bedrag` is **signed**: negative means an expense. Inkomsten/uitgaven are decided purely on sign.

---

## Key concepts

- **Sign = income vs expense.** A wrong sign silently corrupts every statistic.
- **Rules are substrings** of `f"{naam} {omschrijving}".lower()`, and the first match wins. Short terms collide.
- **`Ongecategoriseerd`** is the category for transactions no rule matched.

---

## Development approach

- **The brief is the contract.** Scope never grows past it mid-build.
- **Specs before code.** The spec gate approves before implementation starts.
- **Config over hardcoding** · **don't touch unrelated modules**

Project-specific rules (the gates enforce these):
- **Never read real bank data.** No agent opens Joost's exports (e.g. `~/Code/Financien/*.csv`) or a real `database.db`. Tests and hunts use synthetic fixtures with fake IBANs (`NL00KNAB0000000000`) and fake names only.
- **Python 3.8 compatible:** no `match`, no `X | Y` unions.
- **Tests must not import `saldoboek.gui`** or need a display.
- **Upstream hygiene:** fork-only files (`CLAUDE.md`, `AGENTS.md`, `docs/`, `queue/`, `scripts/`, `.claude/`) never go into an upstream PR.

---

## Agent workflow

This project uses the **dev-agent-team** workflow (synced from
https://github.com/Joost-Maker/Agents — see `.claude/skills/.synced` for the version).

- **The Obsidian vault** holds only the backlog and Feature Briefs: DEV items in the vault's
  `DEV/` database, via the OBS Vault MCP (capture + refinement with `dev-po`).
- **Everything downstream lives in this repo:** each run writes
  `docs/features/NNNN-<slug>/00-brief.md … 08-signoff.md`; the ledger is
  `docs/features/README.md`.
- **`dev-go`** runs a refined task unattended: spec → gates → build → hunt → fix → close per
  the Merge policy above (manual: ends at a reviewed branch + sign-off). Morning ritual:
  `dev-po` morning review.

Workflow overview and role table: `AGENTS.md`.
