# Reading the Project config block

Every project using this workflow has a `CLAUDE.md` at its root with a `## Project config`
section. All role skills depend on it.

## How to extract it

1. Read `CLAUDE.md` from the project root.
2. Locate the `## Project config` heading.
3. Parse the bullet list underneath until the next `##` heading.

## Expected fields

| Key | Required by | Example |
|-----|------------|---------|
| `Project name` | all | `DDJ Explorer` |
| `Mission` | all (the PO's mission check, every role's tiebreaker) | `Een eerlijk leesinstrument zijn …` |
| `Vault project note` | dev-po, dev-go (the DEV item's `Project` link) | `💼 Barnebies/Projects/CircleView.md` |
| `Tech stack` | informational | `Vanilla HTML/CSS/JS · Node` |
| `Run locally` | dev-bughunt, dev-go | `npm start` |
| `Test command` | dev-go (hard requirement for autonomous runs) | `npm test` |
| `Working branch` | dev-go (default `main`) | `main` |
| `Deploy` | dev-go Phase 8 (what merging means) | `push naar main → Railway bouwt automatisch` |
| `Merge policy` | dev-go (`auto-green` or `manual`) | `auto-green` |

## If the block is missing or incomplete

Stop. Tell the user to run `dev-init` (or add the block manually). Do not guess values; do not
fall back to session memory. Specifically:

- No `Test command` → `dev-go` refuses autonomous runs (interactive `dev-programmer` still works).
- No `Merge policy` → treat as `manual` (never auto-merge by default).
- No `Working branch` → `main`.
