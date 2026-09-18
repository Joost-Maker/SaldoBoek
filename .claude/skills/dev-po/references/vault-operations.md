# Vault operations — minimal surface

The Obsidian vault holds the **backlog and the briefs**, nothing else. The repo holds
everything downstream (`docs/features/NNNN-<slug>/`). Total vault traffic for a full pipeline
run: one brief read, two frontmatter flips, one closing Log line — and **queued runs need
zero**: dev-po's Queue mode snapshots the brief into `queue/` while the vault is at hand, the
night runs vault-free, and morning review reconciles (batch dev_status flips + closing Log entries
for every signoff that says `Vault: not updated`). If a flow wants more vault access than
listed here, the flow is wrong.

## The DEV database

Dev items live in the vault's root-level **`DEV/`** folder — one markdown note per item,
membership via `base: "[[DEV.base]]"` frontmatter, dropdowns defined by the Metadata Menu
fileClass `_fileClasses/DEV.md`. This is vault-wide and already set up; it is deliberately
separate from Joost's personal tasks (`💼 Barnebies/Barnebies Tasks/`). Access is through the
**OBS Vault MCP connector** (filesystem tools rooted at `/opt/obsidian-vault-repo`; in Claude
Code the tools appear as `mcp__claude_ai_OBS_Vault__*`). A server-side timer commits and syncs
the vault to Gitea — never run git against the vault.

New DEV item note (filename = short imperative item name):

```yaml
---
base: "[[DEV.base]]"
dev_type: Feature            # Feature | Test | Bug | Chore
dev_status: Todo             # Todo | Doing | Done | Blocked | Archived
dev_refinement: Brain dump   # Brain dump | Refined
dev_priority: Medium         # Low | Medium | High
Project: []                  # [ "[[<Vault project note>|<name>]]" ] from Project config
Agent: ""                    # role/session that created it, e.g. "dev-po"
Related Task: []             # optional link to a Barnebies Task that spawned this
Created time: <ISO timestamp>
---
## Description

- <one-liner at capture; replaced by the Feature Brief at refinement>

## Log
```

**Namespaced enum keys (2026-07-17):** the four enum properties use `dev_*` keys
(`dev_type` / `dev_status` / `dev_refinement` / `dev_priority`) so their value pools don't
collide with the vault-global `Status`/`Type`/`Priority` shared by ~14 other bases. `DEV.base`
maps them back to the display headers Type / Status / Refinement / Priority via `displayName`,
so the table looks unchanged. **Always read and write the `dev_*` keys**, never bare `Status:`.

`dev_status` mapping from the old Notion flow: `Todo` = Not started · `Doing` = In progress ·
`Blocked` = paused/waiting · `Done` · `Archived`.

## Who touches the vault, and how

| Actor | Operation | Tools |
|---|---|---|
| dev-po Capture | create the item note (frontmatter above; body = one-liner) | `write_file` |
| dev-po Triage | list `DEV/`, read frontmatter of the project's items | `list_directory`, `read_text_file` |
| dev-po Refine | write the Feature Brief into the note body, flip `dev_refinement: Refined`, set `dev_priority` | `edit_file` / `write_file` |
| dev-go Phase 0 | read the note body (the brief) once; flip `dev_status: Doing` | `read_text_file`, `edit_file` |
| dev-go Phase 8 | flip `dev_status: Done` (shipped only) + one Log line | `edit_file` |

The closing Log line is appended under `## Log`, one line:
`- YYYY-MM-DD Shipped: <headline> — docs/features/NNNN-<slug>/, commit <sha>, rollback pre-NNNN-<slug>`
or `- YYYY-MM-DD Parked: <reason> — see docs/features/NNNN-<slug>/`.

**Nobody else writes to the vault.** Specs, reviews, protocols, bug reports, fix notes and
sign-offs are repo files. The note body contains only the Feature Brief (plus the Log), always.

## Error handling

1. Show vault MCP errors verbatim; retry once, not more.
2. Inside a pipeline run, a persistently failing vault call must not park the build: finish the
   repo-side work, note the failed call in `08-signoff.md` (`Vault: not updated`), let Joost
   reconcile in the morning. Headless/cron sessions often have no vault MCP at all — that is
   the normal case the queue exists for.
3. Never fabricate a vault path; reference items as `DEV/<name>.md` exactly as they exist.
4. Frontmatter flips are surgical `edit_file` calls on the exact `dev_status:` / `dev_refinement:`
   line — never rewrite a note wholesale to change one field.
