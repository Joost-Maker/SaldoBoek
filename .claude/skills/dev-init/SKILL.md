---
name: dev-init
description: Scaffolds the dev-agent-team workflow into a new or existing software project. Creates CLAUDE.md (with the Project config block all roles parse), AGENTS.md, docs/features/ with its ledger, the sync-agents.sh script, and syncs the skills from the canonical Agents repo into .claude/skills/. Use when Joost says "set up the agent workflow here", "scaffold this project", "initialiseer de workflow", "init dev-agent-team", "nieuw project opzetten", or when starting any software project that should use the brief → GO pipeline.
---

# dev-init — Project scaffolder

Set up the dev-agent-team workflow inside a repo so the other skills (`dev-po`, `dev-go`,
`dev-programmer`, `dev-review`, `dev-test-protocol`, `dev-bughunt`) can operate. Run once per
project. If files already exist, don't overwrite — ask first.

## What it creates

```
<repo>/
  CLAUDE.md                 # project context + Project config block (parsed by all roles)
  AGENTS.md                 # workflow overview and role pointers
  docs/features/README.md   # the run ledger (one row per feature run)
  queue/.gitkeep            # snapshotted briefs waiting for the runner (dev-po Queue mode)
  scripts/sync-agents.sh    # pulls skills from the canonical Agents repo
  scripts/night-runner.sh   # token-aware queue drainer (copied from the Agents repo)
  .claude/skills/           # synced from Joost-Maker/Agents (committed, with .synced marker)
```

Sync the skills by copying `scripts/sync-agents.sh` from the Agents repo and running it (or, if
the Agents repo is checked out locally, rsync `skills/` → `.claude/skills/` and write the
`.synced` provenance file manually). **The skills are synced, never forked** — improvements go
to the Agents repo, then re-sync.

## Gather the config first

Ask one question at a time (don't batch): project name · one-line description · one-sentence
**Mission** (every role's tiebreaker) · tech stack · **Vault project note** (path of the
project's note in the Obsidian vault, e.g. `💼 Barnebies/Projects/<name>.md` — offer to create
it via the OBS Vault MCP if it doesn't exist yet) · `Run locally` command · **`Test command`** ·
what merging the working branch means (**`Deploy`**) · **`Merge policy`** (`auto-green`: green
nights ship and deploy themselves; `manual`: nights always end at a branch + sign-off package
for review).

Two of these deserve pushback rather than pass-through:

- **No test command?** Say plainly: without one, `dev-go` will refuse autonomous runs — the
  overnight promise rests on an automated test floor. Offer to set up a minimal suite as the
  project's first task.
- **`auto-green` on a project where merge = production deploy?** Confirm Joost understands a
  green 3am run goes live unseen (rollback tag always exists). His call, but an informed one.

Then fill `CLAUDE.md` from `references/claude-md-template.md` and `AGENTS.md` from
`references/agents-md-template.md`. Create `docs/features/README.md` with the ledger header:

```markdown
# Feature runs — ledger

| NNNN | Feature | Status | Date | Vault item | Commit / branch |
|---|---|---|---|---|---|
```

## After scaffolding, tell the user

1. What was created, and the sync provenance (`.claude/skills/.synced`).
2. **Backlog lives in the vault:** DEV items go in the vault-wide `DEV/` database (folder +
   `DEV.base` + `_fileClasses/DEV.md` — already set up, shared by all projects); only the
   project note named in `Vault project note` must exist.
3. **The OBS Vault MCP** is needed where `dev-po` runs (capture/refine/queue/reconcile);
   **nights can be vault-free** via the queue. Playwright must be available for `dev-bughunt`
   on browser-testable projects.
4. **Unattended operation:** schedule `scripts/night-runner.sh` (cron) on the machine where the
   `claude` CLI is logged in; it drains the queue, pauses on usage limits, auto-resumes when
   the plan refreshes, and pings `RUNNER_NOTIFY_URL` if set. For permissions, copy what they
   trust from the Agents repo's `scripts/settings-unattended.json` into the project's
   `.claude/settings.json` — explain the trade-off rather than silently installing it.
5. The loop from here: *capture → refine → queue → (runner drains overnight) → morning review.*
