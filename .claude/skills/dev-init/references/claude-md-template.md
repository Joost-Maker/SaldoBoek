# CLAUDE.md template

Fill placeholders `{{...}}`. Keep the Project config keys exactly as written — every role
parses them.

---

```markdown
# {{PROJECT_NAME}} — Claude Context

## About this project

**Project:** {{PROJECT_NAME}}
**Description:** {{ONE_LINE_DESCRIPTION}}
**Developer:** Joost van Barneveld
**Tech stack:** {{TECH_STACK}}
**Status:** In progress

---

## What it does

{{ONE_PARAGRAPH — problem, key inputs and outputs}}

---

## Project config

<!-- Parsed by the dev-agent-team skills. Keep the exact keys. -->

- **Project name:** {{PROJECT_NAME}}
- **Mission:** {{ONE_SENTENCE_MISSION}}
- **Vault project note:** {{VAULT_PROJECT_NOTE_PATH}}
- **Tech stack:** {{TECH_STACK}}
- **Run locally:** `{{RUN_COMMAND}}`
- **Test command:** `{{TEST_COMMAND}}`
- **Working branch:** {{WORKING_BRANCH}}
- **Deploy:** {{WHAT_MERGING_THE_WORKING_BRANCH_MEANS}}
- **Merge policy:** {{auto-green | manual}}

---

## Architecture

<!-- Short: a folder tree, 2–3 sentences per key module. Keep current — the spec gate checks
     specs against this. -->

---

## Key concepts

<!-- 2–3 domain concepts a new contributor (human or Claude) must understand. -->

---

## Development approach

- **The brief is the contract** — scope never grows past it mid-build
- **Specs before code** — the spec gate approves before implementation starts
- **Config over hardcoding** · **don't touch unrelated modules**

<!-- Project-specific rules below — the gates enforce these. -->

---

## Agent workflow

This project uses the **dev-agent-team** workflow (synced from
https://github.com/Joost-Maker/Agents — see `.claude/skills/.synced` for the version).

- **The Obsidian vault** holds only the backlog and Feature Briefs — DEV items in the vault's
  `DEV/` database, via the OBS Vault MCP (capture + refinement with `dev-po`).
- **Everything downstream lives in this repo:** each run writes
  `docs/features/NNNN-<slug>/00-brief.md … 08-signoff.md`; the ledger is
  `docs/features/README.md`.
- **`dev-go`** runs a refined task unattended: spec → gates → build → hunt → fix → green-only
  close per the Merge policy above. Morning ritual: `dev-po` morning review.

Workflow overview and role table: `AGENTS.md`.
```
