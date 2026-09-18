# Pipeline contract — dev-go

Phases run in order; each phase commits its artifact before the next starts. **Artifacts are
checkpoints**: a run interrupted at any moment (usage limit, crash, closed laptop) resumes at
its first missing or incomplete artifact. A parked run is *not* in-flight — it has an
`08-signoff.md` and waits for Joost; never auto-resume it.

Feature directory: `docs/features/NNNN-<slug>/` — NNNN continues the existing sequence across
`docs/features/` **and** `queue/` (zero-padded), slug in kebab-case.

Artifacts: `00-brief.md` · `01-spec.md` · `02-spec-review.md` · `03-implementation-log.md` ·
`04-test-protocol.md` · `05-bughunt-report.md` · `06-fixes.md` · `07-code-review.md` ·
`08-signoff.md` · `09-retro.md`.

## Phase 0 — Intake & baseline

1. **Queue path (preferred):** take the lowest-numbered `queue/NNNN-<slug>.md`. The file IS the
   brief snapshot (dev-po wrote it at queue time) — `git mv` it to
   `docs/features/NNNN-<slug>/00-brief.md`. No vault needed.
   **Vault path (fallback):** resolve the DEV item note, require `dev_refinement = Refined`;
   allocate NNNN, snapshot the note body (the brief, without frontmatter/Log) verbatim into
   `00-brief.md` with frontmatter (`vault_item`, `date`, `priority`). Not refined → stop and
   say so (nothing has started; this is not a park).
2. Sanity-check the brief: testable acceptance criteria in Given/When/Then form, an
   Out-of-scope section, Ambiguity guidance. A brief that fails this check parks immediately
   with reason "brief not GO-ready" — building on a vague contract wastes the night.
3. Baseline on the working branch (config `Working branch`, default `main`): clean tree, latest
   pulled, **`Test command` green**. Red baseline → park with reason "baseline red"; never fix
   unrelated failures inside a feature run.
4. `git switch -c feat/NNNN-<slug>` · flip the DEV item's `dev_status: Doing` (skip silently if
   the vault MCP is unavailable — note it for the signoff) · commit the snapshot.

## Phase 1 — Spec

As `dev-programmer` (this context): read the actual code the feature touches, write `01-spec.md`
from its template. If the brief and the code contradict each other, record it in the spec's
"Open questions" — the gate will park it; never paper over it. Commit.

## Phase 2 — Spec gate (fresh context)

Spawn a subagent: *"Read `.claude/skills/dev-review/SKILL.md` and run spec mode on
`docs/features/NNNN-<slug>/`. Read only the artifacts, `CLAUDE.md`, and the code."* It writes
`02-spec-review.md` ending in exactly one machine-checkable line:
`Verdict: approved` · `Verdict: approved with notes` · `Verdict: changes requested` ·
`Verdict: park`.

- `changes requested` → revise the spec, append a revision note, re-run the gate. **Max 2
  revision cycles**, then park.
- `park` → park protocol.
- No subagent capability available → fallback: run the review in-session, but only after
  re-reading the artifacts from disk, and note `context: in-session (degraded)` in the file.

**Preflight stop:** if this run is `--preflight`, stop here. Report the verdict and a 5-line
spec summary in chat; commit everything. The next `GO next` resumes at Phase 3.

## Phase 3 — Build

Implement to the approved spec. Maintain `03-implementation-log.md` as you go: build notes plus
a **Decisions** table for every ambiguity hit. Hybrid policy:

- **Reversible** (naming, copy, layout detail, internal structure with no data/API consequence):
  the most conservative reading of the brief, logged with the rejected alternative.
- **Irreversible or scope-changing** (data model, stored formats, public API, anything the brief
  excludes): **park**. Check the brief's Ambiguity guidance first — Joost may have pre-delegated.

Commit small and conventionally, referencing `NNNN-<slug>` — work-in-progress commits on the
feature branch are encouraged (kill-safety); the final squash erases the noise. Never touch
files outside the spec's stated scope.

## Phase 4 — Test protocol + permanent tests (accretion)

Invoke `dev-test-protocol`. It produces TWO things, both mandatory:

1. **Permanent automated tests** in the project's suite (e.g. `test/`, Playwright specs) — one
   or more per acceptance criterion, plus regression-relevant cases. These stay forever: every
   future run's baseline check re-runs them. An AC that genuinely can't be automated is listed
   `manual: <reason>` in the protocol and lands in the signoff's "What to eyeball".
2. `04-test-protocol.md` — the browser/manual cases for the hunter, each row mapped to its
   automated test (or `manual`).

`Test command` must be green **including the new tests** before Phase 5. Commit.

## Phase 5 — Bug hunt (fresh context)

Start the app (`Run locally`). Spawn a subagent: *"Read `dev-bughunt/SKILL.md` and execute
`04-test-protocol.md` against <URL>; write `05-bughunt-report.md`."* The hunter never sees the
build conversation, and finishes with its **exploratory pass** (unscripted, timeboxed — see the
skill) after the protocol. Commit the report.

## Phase 6 — Fix loop (cap: 3 rounds)

Fix every 🔴 and 🟠 — nothing else; 🟡/🟢 go to the sign-off's backlog candidates. Append each
round to `06-fixes.md`. Every fix that catches a real bug gets a **regression test added to the
suite** in the same round (accretion applies to fixes too). Re-run `Test command` plus a
re-hunt scoped to affected cases. Still 🔴/🟠 open after round 3 → park.

## Phase 7 — Code gate (fresh context)

Spawn dev-review in **code mode**: full diff (`git diff <working-branch>...HEAD`) against spec,
brief acceptance criteria, `CLAUDE.md` architecture rules, **and AC→test coverage** →
`07-code-review.md`, same verdict line. `changes requested` → fix once, re-run gate; second
failure → park.

## Phase 8 — Close

Write `08-signoff.md` (template: `references/signoff-template.md`). Then decide:

**Ship** — requires ALL of: spec gate approved · every acceptance criterion in `00-brief.md`
verified (by its automated test, or eyeball-listed if `manual`) · zero open 🔴/🟠 ·
`Test command` green including the new tests · code gate approved · config
`Merge policy: auto-green`.

```
git tag pre-NNNN-<slug> <working-branch> && git push origin pre-NNNN-<slug>
git switch <working-branch> && git merge --squash feat/NNNN-<slug>
git commit   # one commit, message = feature headline + docs/features/NNNN-<slug>/
git push && git push origin --delete feat/NNNN-<slug>
```

Then flip the DEV item's `dev_status: Done` + one Log line under `## Log`:
`- YYYY-MM-DD Shipped: <headline> — docs/features/NNNN-<slug>/, commit <sha>, rollback pre-NNNN-<slug>`.
Vault unavailable → write `Vault: not updated — reconcile in morning review` in the signoff
instead. Deploy is whatever `Deploy` in config says merging means; verify the deploy came up if
the config names a URL.

**Park** — any gate failed, cap hit, irreversible ambiguity, baseline red, brief not GO-ready,
or `Merge policy: manual`: push the feature branch, set `Status: PARKED (<reason>)` (or
`READY FOR REVIEW` under manual policy) in `08-signoff.md`, DEV item Log line
`- YYYY-MM-DD Parked: <reason> — see docs/features/NNNN-<slug>/` (or the reconcile note); the
item's `dev_status` stays `Doing`. Never merge, never force-push, never delete the branch.

**Always:** append the ledger row to `docs/features/README.md`
(`NNNN · name · SHIPPED/PARKED/REVIEW · date · vault item · commit-or-branch`), commit, push.

## Phase 9 — Retro

Write `09-retro.md` (template: `references/retro-template.md`): friction in the **pipeline
itself** — gate false positives, template gaps, missing guidance, wasted loops — each as a
concrete proposed change to the Agents repo. Propose only; **never edit `.claude/skills/`**
(synced) and never push to the Agents repo from a night run. Joost approves upstream changes in
morning review. Nothing to report → write "No friction worth reporting" (honestly). Commit,
push, done.

## Vault budget per run

Queue path: **zero required** (flips/Log line best-effort, reconciled in the morning). Vault
path: one read · two frontmatter flips · one Log line. Anything more is a bug in the pipeline.
