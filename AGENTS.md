# SaldoBoek (Joost-Maker fork) — Agent Team Workflow

This project uses the **dev-agent-team** workflow. Skills are synced from the canonical repo
(https://github.com/Joost-Maker/Agents) into `.claude/skills/` — never edit them here; improve
upstream and re-run `scripts/sync-agents.sh`.

**The deal:** Joost talks to the PO (capture → refine, DEV items in the Obsidian vault). After "GO", the pipeline
runs unattended. The Feature Brief is the contract; every artifact is a markdown file in
`docs/features/NNNN-<slug>/`; every gate runs in a fresh context reading only those files.
Green on all gates → ship per the Merge policy in `CLAUDE.md`; anything less → parked branch +
morning report.

## The team

| Role | Skill | Human present? |
|------|-------|----------------|
| Product Owner | `dev-po` | **Yes — the only one** |
| Orchestrator (GO pipeline) | `dev-go` | No |
| Programmer | `dev-programmer` | Optional (interactive mode) |
| Gatekeeper (spec + code review) | `dev-review` | No — fresh context |
| Test Designer | `dev-test-protocol` | No |
| Test Executor (Playwright) | `dev-bughunt` | No — fresh context |

## The pipeline

```
dev-po: capture → refine → queue/NNNN-slug.md ("tonight" — brief snapshot, nights vault-free)
  │
  ▼  scripts/night-runner.sh (cron) → claude -p "/dev-go next" — pauses on usage limits,
  ▼  auto-resumes on refresh (artifacts are checkpoints)
  0  baseline green · queue file → 00-brief.md · branch feat/NNNN-slug
  1  01-spec.md
  2  GATE dev-review → 02-spec-review.md          (≤2 revisions, else park)
     └─ "GO --preflight" stops here for a 10-min human check, optional
  3  build + 03-implementation-log.md             (decisions logged; irreversible? → park)
  4  PERMANENT tests into the suite (accretion) + 04-test-protocol.md
  5  GATE dev-bughunt → protocol + exploratory pass → 05-bughunt-report.md
  6  fix 🔴/🟠 + regression tests → 06-fixes.md → re-hunt   (≤3 rounds, else park)
  7  GATE dev-review code mode (incl. AC→test coverage) → 07-code-review.md
  8  08-signoff.md → all green: tag pre-NNNN-slug · squash-merge · push · vault Done/reconcile
                  → else: branch pushed, PARKED
  9  09-retro.md — pipeline friction → proposed upstream skill changes (Joost approves)

morning: dev-po morning review — sign-offs, vault reconcile, retro approvals, backlog capture
```

## Hard rules

- **No implementation without an approved spec** (gate verdict in `02-spec-review.md`, or
  Joost's word in interactive mode).
- **The brief's Out-of-scope is law** — the pipeline never invents features at night.
- **Never ship non-green** — zero open 🔴/🟠, tests green, both gates approved, else park.
- **Every merge is one squash commit + a `pre-NNNN-<slug>` rollback tag.**
- **Vault budget per run:** 1 brief read · 2 frontmatter flips · 1 closing Log line.

## Quick reference

| I want to... | Say |
|--------------|-----|
| Get an idea into the backlog | "capture this idea" |
| Make a task buildable | "refine task X" |
| Load the pipeline for tonight | "queue task X" (repeat — they run serially) |
| Ship one now, unattended | "GO task X" (or "GO next" for queue top) |
| Sanity-check the aim before bed | "GO --preflight task X" (stops after the spec gate) |
| Drain the queue around the clock | schedule `scripts/night-runner.sh` (cron) |
| See what the night did | "morning review" |
| Build interactively instead | "pick up task X with me" |
