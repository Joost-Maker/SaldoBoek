# Implementation log — AI suggest: GPU category + rule proposals

**Spec:** 01-spec.md (rev 2, approved with notes 2026-09-18)

## Build notes

| Requirement | Status | Where | Note |
|---|---|---|---|
| Shared group key / sign / rule text | done | `tools/ai_common/grouping.py` | `rule_text` uses `or ''` for NULL name/description; the apply item must import these |
| Read-only DB | done | `tools/ai_suggest/db.py` | `Path.resolve().as_uri() + "?mode=ro"` (N9); rules in `Categorizer._load_rules` order; `Ongecategoriseerd` excluded from categories (N16) |
| Zoekterm validation, fallback, collision, shadow | done | `tools/ai_suggest/rules.py` | NULL category not a collision (N5) |
| Prompt, few-shot, IBAN scrub | done | `tools/ai_suggest/prompt.py` | case-insensitive IBAN regex with optional spaces (N8); few-shot skips uncategorised (N16) |
| Constrained LLM call, network confinement | done | `tools/ai_suggest/llm.py` | `ProxyHandler({})` + a redirect-refusing handler; `check_endpoint` compares `urlsplit().hostname` exactly and refuses userinfo; default port 80 when absent (N14) |
| GPU guard (pre, post card, post per-process, spill warning) | done | `tools/ai_suggest/gpu.py` | `card[0-9]*` plus an exact `card\d+` match skips connectors (N15); distinct exit-3 messages (N1) |
| Review CSV | done | `tools/ai_suggest/review.py` | decimal comma for `totaal_bedrag`/`zekerheid` (N6); atomic via `os.replace` |
| CLI flow, progress, summary, abort | done | `tools/ai_suggest/__main__.py` | per-group timing lines (N7); spill warning repeated in the summary (N2); stdout shows `(geen naam)`, never the description, for nameless groups (N13) |

Smoke check (no DB, no model): `check_endpoint` accepts `127.0.0.1`/`localhost`/`[::1]` and refuses `127.0.0.1@evil.com`, `https`, and `10.0.0.2`. `find_egpu('/sys/class/drm')` on this laptop → `card0`, pdev `0000:03:00.0`, 15.9 GiB. `--endpoint http://example.com` → exit 1 before anything else.

## Decisions (ambiguities resolved without the PO)

| # | Ambiguity | Chose | Alternative rejected | Why reversible |
|---|---|---|---|---|
| 1 | Per-process VRAM check beyond the brief's card check | Added (spec Decision 1, gate-approved) | Card check only, which passes on this machine even with Qwen off the eGPU | One function in `gpu.py` |
| 2 | Spill < 90 % | Warning in the progress output and the summary | Abort | One branch |
| 3 | `--gebruiker` with an id that doesn't exist | Exit via `SystemExit` with a message (code 1) | Silently choosing another user | CLI only |
| 4 | Group display name when `naam` is empty | `(geen naam)` on stdout; the CSV `naam` column stays empty, and `sleutel` holds the description key | Printing the key (it would leak the description to stdout) | Display only |
| 5 | Sample descriptions sent to the model | Up to 3 distinct, scrubbed and truncated to 120 characters | Full text | Constants in `prompt.py` |
| 7 | Test file layout: the spec named `test_cli.py`/`test_readonly.py`/`test_review.py`/`test_prompt.py`; those cases live in `tests/ai_suggest/test_io.py` | One I/O-boundaries file | Four small files | Moving tests is free; the protocol's coverage table names the real files |
| 6 | Groups in a partial file after an abort | Every group attempted so far, including the failed ones (flagged `model-fout`) | Only successful groups | `__main__.py` loop |

## PO amendment (spec rev 3)

The zoekterm is name-first (see `06-fixes.md` round 1b). The spec's "High-stakes output impact" section and the "FR zoekterm validation + fallback" row still describe validation of every zoekterm. Under rev 3, that validation applies only to nameless or short-name groups, while named groups always get their exact name. That's narrower than any model term, so the over-match risk the high-stakes section worries about goes down (N19).

## Deviations from the spec

None.

## Test command runs

| When | Command | Result |
|---|---|---|
| baseline (phase 0, `dev`) | `.venv/bin/python -m pytest -q` | green (1 passed) |
| phase 4, new suite | `.venv/bin/python -m pytest -q` | green (53 passed), first run |
| phase 4, mutation check | remove the proxy block / IBAN scrub / per-process VRAM check, one at a time | each makes its guarding test fail; restored and green again (53 passed) |
| fix round 1 (E2) | `.venv/bin/python -m pytest -q` | green (56 passed) |
| fix round 1b (PO amendment) | `.venv/bin/python -m pytest -q` | green (60 passed) |
