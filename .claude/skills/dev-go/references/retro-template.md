# Retro template

`docs/features/NNNN-<slug>/09-retro.md` — written by dev-go after close (shipped AND parked).
Subject: the **pipeline**, not the feature. This is how the skillset learns: friction observed
during the run becomes a proposed change to the canonical Agents repo, which Joost approves (or
rejects) in morning review. Propose only — a night run never edits skills or pushes upstream.

```markdown
# Retro — NNNN-<slug>

**Run outcome:** SHIPPED | PARKED (<reason>)
**Phases with friction:** [e.g. 2, 6 — or "none"]

## What cost time or tokens that shouldn't have

| Phase | What happened | Root cause |
|---|---|---|
| | | |

## Proposed upstream changes (Agents repo)

| # | File (in Joost-Maker/Agents) | Change | Why |
|---|---|---|---|
| 1 | skills/.../SKILL.md | [one-line concrete edit] | [the friction it removes] |

## Worked well (keep)

[1–3 bullets — so good patterns don't get "improved" away.]
```

Rules: concrete edits only ("add X to the spec template"), never vibes ("communication could be
better"). If a gate gave a false positive/negative, quote the exact verdict line and what the
truth was. Empty retro is fine when true — a fabricated improvement pollutes the upstream
backlog.
