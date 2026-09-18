---
name: dev-go
description: Autonomous delivery pipeline ("GO") for projects using the dev-agent-team workflow. Takes queued briefs (queue/) or refined DEV items from the Obsidian vault and drives them unattended through spec → spec gate → build (with permanent test accretion) → bug hunt → fixes → code gate → sign-off → retro, writing every artifact to docs/features/NNNN-<slug>/ in the repo. Merges and deploys only when every gate is green (per the project's Merge policy); otherwise parks the branch with a morning report. Kill-safe and resumable: artifacts are checkpoints, so a run interrupted by a usage limit or crash continues where it stopped. Use in Claude Code when Joost says "GO", "GO next", "GO task X", "GO --preflight", "ship task X", "run the pipeline", "draai de nacht", "overnight run", or when invoked by scripts/night-runner.sh.
---

# dev-go — Autonomous delivery pipeline

You are the orchestrator. After this skill starts, **Joost is gone** — assume he is asleep and
will read the results in the morning. Never wait for him, never ask him mid-run. Every decision
either follows the brief, follows the hybrid ambiguity policy, or parks the run.

Read `references/pipeline.md` now — it is the phase-by-phase contract, including gate rules,
iteration caps, the park protocol, and resume behavior. This file only covers orientation.

## Ground rules

1. **The Feature Brief is the contract.** It arrives snapshotted (queue) or gets snapshotted at
   intake; never re-read the vault after that. Anything the brief doesn't cover is handled by the
   ambiguity policy, not by invention.
2. **Gates run in fresh contexts.** Spec review, bug hunt, and code review are spawned as
   subagents that read only the artifact files and the code — never this conversation.
3. **Green-only shipping.** Merge/deploy only when every gate passed and the project's
   `Merge policy` is `auto-green`. `manual` policy or any non-green state → park protocol.
4. **Artifacts are the audit trail — and the checkpoints.** Every phase writes its numbered
   file in `docs/features/NNNN-<slug>/` and commits it before the next phase starts. Assume the
   session can be killed at any moment (usage limit, crash): commit work-in-progress often
   enough that a resume loses minutes, not hours.
5. **Tests accrete.** Phase 4 leaves permanent automated tests in the project's suite, not just
   a protocol. The floor rises every feature.
6. **Caps are hard.** Spec revisions ≤ 2, bughunt→fix rounds ≤ 3. Hitting a cap = park.

## Inputs and modes

- **`GO next` / bare `GO`** (what the night runner sends): first **resume** any in-flight run —
  a `docs/features/NNNN-<slug>/` containing `00-brief.md` but no `08-signoff.md` — at its first
  missing artifact. Otherwise take the lowest-numbered brief in `queue/`. Otherwise fall back to
  the top refined DEV item in the vault (`dev_refinement = Refined`, `dev_status = Todo`, highest
  priority). Nothing anywhere → say so and stop cleanly (exit success, no work).
- **`GO task X` / a vault item path** — run that specific item (queue first, then vault).
- **`GO --preflight [task]`** — run phases 0–2 only (intake, spec, spec gate), then **stop** and
  report the verdict and a 5-line spec summary in chat. The night continues from phase 3 on the
  next `GO next`. Use case: Joost spends 10 minutes before bed confirming the run is aimed
  right; the unattended hours start pre-gated.
- Multiple tasks → serial, each on its own branch, merged or parked before the next starts. If
  B depends on a parked A, park B immediately with reason "blocked by NNNN".
- `CLAUDE.md` `## Project config` must provide `Test command` and `Run locally`. No test
  command → refuse the autonomous run and say why. Missing config → point to `dev-init`.

## The vault is optional at night

Queued briefs make the run vault-free: if the OBS Vault MCP is unavailable (the normal case in
headless/cron sessions) or calls fail, skip the dev_status flips and closing Log line, record
`Vault: not updated — reconcile in morning review` in `08-signoff.md`, and carry on. Vault
problems never park a build.

## Outputs (what Joost finds in the morning)

- Shipped: working branch updated by one squash commit, `pre-NNNN-<slug>` rollback tag,
  permanent tests added to the suite, vault item `Done` (or a reconcile note), `08-signoff.md`
  with what shipped / what was assumed / what to eyeball / backlog candidates.
- Parked: feature branch pushed, `08-signoff.md` with `Status: PARKED`, reason, exact state,
  recommended next step; nothing merged.
- Always: `09-retro.md` (pipeline friction → proposed upstream skill improvements) and a ledger
  row in `docs/features/README.md`.

## Style

Commit messages follow the project's conventions and reference `NNNN-<slug>`. Keep the chat
transcript terse — the artifacts are the record. If the session is genuinely interactive
(Joost is present and replies), you may ask — but never block on the assumption that he might
be.
