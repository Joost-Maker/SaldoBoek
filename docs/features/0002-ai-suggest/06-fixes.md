# Fixes — AI suggest (0002-ai-suggest)

## Round 1 (after 05-bughunt-report.md round 1)

| Bug | Severity | Fix | Files | Regression test |
|---|---|---|---|---|
| E2: `--out` pointing at the database (directly or through a symlink) replaced `database.db` with the CSV, silently, with exit 0 | 🟠 | `check_output()` runs before the eGPU check, before the DB is opened, and before any model call. It refuses when `realpath(--out) == realpath(--db)` and when `--out` isn't a `.csv` (exit 1, clear message). The default output path is always a new `ai_review_*.csv` next to the DB | `tools/ai_suggest/__main__.py` | `tests/ai_suggest/test_io.py::test_out_equal_to_db_refused`, `::test_out_via_symlink_to_db_refused`, `::test_out_must_be_csv` |

**Left for backlog (🟡/🟢, per pipeline rule):** F2 IBAN variants (double space, tab, NBSP, dashes, dots, glued `IBANNL…`) still reach the local model; E1 over-broad zoektermen (`b.v.`, `betaling`, `pinbetaling`) and the same term proposed for different categories aren't flagged, and collisions ignore other uncategorised groups; E3 an unwritable `--out` directory is only discovered after all model calls; F1 `zekerheid` 1.5 becomes 0,01 without a flag; E4 control characters in names go raw to stdout; E5 `--sysfs-root` pointing elsewhere skips the pre-check (one request before exit 3).

**AC14 (real GPU run) not executed in round 1:** the llama-server on `:6767` (`jan-claudian.service`) was stopped. It only runs while Obsidian is open. Starting it is Joost's call; see the sign-off.

Test command after round 1: `.venv/bin/python -m pytest -q` → green (56 passed).

## AC14: real GPU run (executed by the orchestrator, with Joost's explicit OK to start `jan-claudian.service`, 2026-09-18)

Synthetic DB from the round-1 hunt (8 fake counterparties, all names `Test …`). The service was started for the run and stopped afterwards; eGPU back to 367 MiB.

```
eGPU card0: 11.0/15.9 GiB in gebruik, model (pid 565027) 10.6 GiB resident
[1/8] Test Streaming (3×) → Abonnementen in 16.7 s     (cold load)
[2/8] Test Supermarkt B.V. (3×) → Boodschappen in 1.6 s
… 8 groups, mean 4.1 s/call, 32.9 s wall, exit 0, no spill warning
```

**Result: AC14 passes.** The model is resident on the RX 9060 XT (10.6 GiB, no spill), warm calls take ~1 s, and the proposals are plausible except one: `Test Apotheek Centrum` → Boodschappen (0.95), although `Zorg` exists. The review step catches that.

**Real-output confirmation of backlog E1:** the proposed zoektermen included generic words: `woning` (Huur), `salaris`, `de hoek`, `supermarkt`. They pass validation (a substring of every group text, no collisions in this DB), but as permanent rules they would over-match future transactions (e.g. `woning` ⊂ "woningverzekering"). Escalated to the PO in the sign-off.

## Round 1b: PO amendment, zoekterm = full counterparty name (spec rev 3, gate-approved)

| Change | Files | Tests |
|---|---|---|
| `choose_zoekterm`: when the stripped name has ≥ 4 chars, it's always the lowercased full name (digits allowed, and it bypasses `validate_zoekterm` by design, N18). Only for a nameless or too-short-name group is the model's term used, with the original validation; else `""` plus `zoekterm ongeldig`. The old name fall-back is gone | `tools/ai_suggest/rules.py` | `test_rules.py::test_naam_always_wins`, `::test_naam_with_digits_allowed`, `::test_nameless_invalid_model_term`, `::test_nameless_valid_model_term`, `::test_short_naam_uses_model_term`; `test_flow.py::test_generic_model_term_replaced_by_naam`, `::test_nameless_group_uses_valid_model_term`, `::test_collision_flag` (rewritten to the amended AC6 fixture, not loosened) |

Removed as obsolete (they described the dropped fall-back): `test_rules.py::test_digits_fall_back_to_naam`, `::test_invalid_when_fallback_fails`, `test_flow.py::test_digits_zoekterm_falls_back`.

Noted for the sign-off and the 0003 brief (N20/N21): rows marked `model-fout` or `geen categorieën` keep the zoekterm blank. A counterparty with both income and expense rows gives two rows with the **same** zoekterm, but `categorisatie_regels` is `UNIQUE(zoekterm, gebruiker_id)`, so at most one can become a rule.

Test command after round 1b: `.venv/bin/python -m pytest -q` → green (60 passed).

## Round 2: code gate review 1 (changes requested)

| Required change | Fix | Files | Regression test |
|---|---|---|---|
| 1. IBANs reached the prompt when padded (double space, tab, NBSP) or glued (`IBANNL…`) | Collapse whitespace **before** masking; the pattern has no leading word boundary and allows one space/dot/dash between characters | `tools/ai_suggest/prompt.py` | `test_flow.py::test_no_iban_in_requests_padded_and_glued` (incl. a few-shot row) |
| 2. `categorie IS NULL` was grouped and sent to the model (undocumented deviation) | Input restricted to `categorie == 'Ongecategoriseerd'`, as in the brief. NULL still doesn't count as a collision (N5). 0003 must look groups up with the same `UNCATEGORIZED` constant from `tools/ai_common` | `tools/ai_suggest/__main__.py` | `test_flow.py::test_null_category_not_grouped` |
| 3. A link at `<out>.tmp` could overwrite the DB (bug hunt R2-1) | The temp file comes from `tempfile.mkstemp` in the output directory (O_EXCL, fresh name), then `os.replace`; it's cleaned up on error. Side effect: the review CSV is mode 0600, which is right because it holds bank data | `tools/ai_suggest/review.py` | `test_io.py::test_tmp_symlink_to_db_cannot_overwrite`, `::test_review_file_is_private` |
| 4. `04-test-protocol.md` was stale | Updated to the amended AC4/AC6, case 2.1, the high-stakes rows, spec rev 3, and the new tests | `docs/features/0002-ai-suggest/04-test-protocol.md` | — |

Mutation check: with the old `prompt.py` and `review.py` restored, both new tests fail (2 failed); with the fixes, green.

Test command after round 2: `.venv/bin/python -m pytest -q` → green (64 passed).

## Round 3: after PARK, continued interactively with Joost's explicit OK ("ja maak af", 2026-09-18)

The run was parked at the code-gate cap (review 2: R5, over-masking from the round-2 IBAN fix). Joost chose to finish it interactively; his approval replaces the cap, and the next code gate still runs in a fresh context.

| Required change | Fix | Files | Regression test |
|---|---|---|---|
| R5: the IBAN pattern (no word boundaries) masked ordinary text, e.g. `Factuur 2026-00123 abonnement oktober` → `Factu[IBAN]` | The gate's pattern: boundaries on both sides, except a candidate directly after `IBAN` (glued form). **Plus a minimum-digit check found by the new negative test:** the gate's pattern still masked `AH to go 1418 Amsterdam` (`go 14` + `18 Amsterdam` fits the shape). A candidate is masked only if it has ≥ 10 digits; every real IBAN does (NL: 2 check + 10 account digits) | `tools/ai_suggest/prompt.py` | `tests/ai_suggest/test_prompt_scrub.py`: 10 IBAN forms masked (plain, lowercase, spaced, double-spaced, tab, NBSP, dashes, dots, glued `IBANNL…`, `iban: nl00…`), and **8 ordinary descriptions left exactly intact** (invoice numbers, "Termijn 3 van 12", "huur okt 2026 woning 12a", a 16-digit kenmerk, `Abonr.`, and pin descriptions like `AH to go 1418 Amsterdam`, `Jumbo 7042 Utrecht Centrum`) |

Mutation check: with the over-masking version, 7 of the 8 negative cases fail; with the fix, all 18 scrub tests pass.

Test command after round 3: `.venv/bin/python -m pytest -q` → green (82 passed).

### AC14 re-run on the final code (after round 3), with the service started and stopped again for the run

```
eGPU card0: 11.0/15.9 GiB in gebruik, model (pid 598593) 10.6 GiB resident
8 groups, mean 2.1 s/call (first 9.6 s, then ~1 s), exit 0, no flags, no spill warning
```
All 8 zoektermen are the full counterparty names (PO amendment works end to end). The review CSV is `-rw-------`. Same quality note as before: `Test Apotheek Centrum` → Boodschappen (0.95) although `Zorg` exists; the review step catches it. **AC14 passes on the final code.**

## Round 3b: code gate review 3, R6 (interactive, same PO approval)

| Required change | Fix | Files | Regression test |
|---|---|---|---|
| R6: with `re.sub`, a rejected earlier candidate (`AH 12`, `NS 20`, `nr 12`, `op 18`) could run into a spaced/dashed/dotted IBAN and hide its start, so the IBAN leaked whole (or partly, when the earlier candidate had ≥ 10 digits) | `_iban_spans()`: every start position is checked on its own with `IBAN_RE.match(text, i)`; spans with ≥ 10 digits are kept, overlapping spans are merged, then each is replaced with `[IBAN]`. The pattern is unchanged (the gate verified that changing the pattern alone can't fix this) | `tools/ai_suggest/prompt.py` | `test_prompt_scrub.py::test_iban_forms_are_masked`: 5 new cases, the gate's 4 leak strings plus two IBANs in one text; the existing `"0000" not in digits` check catches whole and partial leaks |

Mutation check: with the round-3 `prompt.py`, the 5 new cases fail; with the fix, all 23 scrub tests pass. Known and privacy-safe (N7): a candidate can swallow up to 30 following characters (`Huur op 18-09-2026 … NL00 …` → `Huur [IBAN]`).

Test command after round 3b: `.venv/bin/python -m pytest -q` → green (87 passed).

## Round 4: PO amendment 2, IBAN masking removed (interactive, 2026-09-18)

Code gate review 4 (on R6) was **stopped by Joost** before it produced a verdict. He then withdrew the IBAN requirement (see `00-brief.md`, PO amendment 2).

| Change | Files | Tests |
|---|---|---|
| Removed `IBAN_RE`, `IBAN_MIN_DIGITS`, `_iban_spans`, `_mask_ibans`; `scrub()` → `clean()` (collapse whitespace, cap at 1000 chars); the prompt carries up to 3 full sample lines `datum · bedrag · omschrijving` per group | `tools/ai_suggest/prompt.py`, `tools/ai_suggest/__main__.py` | removed `tests/ai_suggest/test_prompt_scrub.py` and `test_flow.py::test_no_iban_in_requests*`; added `test_flow.py::test_full_description_reaches_prompt` |

Check: `jan-claudian.service` has no verbose/log flags, and the journal holds 0 lines with prompt content after today's runs, so nothing on disk to redact.

Real GPU run on the final code (synthetic DB, service started for the run and stopped after): 10.6 GiB resident on the RX 9060 XT, mean 1.8 s/call, 8/8 groups, exit 0, no flags.

**Closure mode:** per Joost ("Licht: tests + jouw OK"), no further code gate. Final approval is Joost's word in chat (interactive mode). R1–R4 were approved by the code gate; R5/R6 are moot, since the code they concerned was removed.

Test command after round 4: `.venv/bin/python -m pytest -q` → green (63 passed).
