# Code review: 0002-ai-suggest

**Gate:** code mode · **Diff:** `git diff dev...HEAD` (`fc4fae9..f51b7b4`, 14 commits, 25 files, +2684) · **Reviewed:** `00-brief.md` (with the PO amendment), `01-spec.md` rev 3, `02-spec-review.md`, `03-implementation-log.md`, `04-test-protocol.md`, `05-bughunt-report.md` (rounds 1 and 2), `06-fixes.md` (rounds 1 and 1b plus AC14), `CLAUDE.md`, all of `tools/` and `tests/ai_suggest/`, `saldoboek/core/database.py:577-586` · **Date:** 2026-09-18

## Honesty spot-check

- `.venv/bin/python -m pytest -q` → **60 passed** (22.3 s). This matches the log's last entry (round 1b, 60 passed).
- `git diff dev...HEAD -- saldoboek` is empty. Every commit subject references `0002-ai-suggest`.
- I reproduced the two open bug-hunt findings that matter below with synthetic values only (no DB, no endpoint): `scrub('Overboeking NL00  RABO  0000  0000  04 huur')` → `'Overboeking NL00 RABO 0000 0000 04 huur'`, and `build_groups` puts a `categorie = NULL` transaction into a group.

## Hard lines

| Line | Status | Evidence |
|---|---|---|
| Read-only DB | **Held on the normal path, with one side door (R3)** | `db.py:24` uses `as_uri() + "?mode=ro"`. `DatabaseManager` is not used in `tools/`. AC10 tests pass. `check_output` (`__main__.py:104-111`) runs before the GPU check and before the DB is opened. `write_review` opens `<out>.tmp` by name, and that open follows links (R3). |
| No network except loopback | Held | `check_endpoint` (`llm.py:30-46`) matches `urlsplit().hostname` exactly and rejects userinfo and non-`http` schemes. It runs first in `main` (`__main__.py:130-134`). The opener is `ProxyHandler({})` plus `_NoRedirect`. `llm.py` is the only module that imports network code. The hunt's strace saw loopback connects only. Tests: `test_ignores_proxy_env`, `test_redirect_refused`, `test_non_loopback_endpoint_refused`. |
| No data on stdout | Held | Progress and summary print `display_name(naam)` (`(geen naam)` for nameless groups), counts, category, seconds, the GPU line and the path. Model error texts are fixed strings. Tested by `test_stdout_has_no_descriptions`. Control characters in `naam` (E4) are the brief-allowed name, printed raw: cosmetic. |
| No CPU/iGPU fallback | Held | Exit 2 before any request unless there's a ≥ 8 GiB amdgpu card (`gpu.py:38-62`), connector entries skipped. After the first success, the card check is followed by the per-process fdinfo check (`gpu.py:156-172`). Every failure is exit 3 with its own message. No code path picks a device or retries elsewhere. AC14 real run: 10.6 GiB resident on `card0`, no spill. |
| No real data in the public repo | Held | Every IBAN in the diff is a zero-filled `NL00…` fake. All counterparty names in the fixtures are `Test …`. Amounts are synthetic. The docs mention only synthetic names (plus public brand examples like `KPN`/`Hema` as test strings) and local temp paths. |

## Contract: acceptance criteria (as amended)

| AC | Met? | Test |
|---|---|---|
| 1 | yes | `test_flow.py::test_two_groups_two_calls` |
| 2 | yes | `test_flow.py::test_model_error_flag` (invented category and free text) |
| 3 | yes | `test_flow.py::test_enum_by_sign`, `::test_mixed_sign_split` |
| 4 (amended) | yes | `test_rules.py::test_naam_always_wins`, `::test_nameless_invalid_model_term`, `::test_nameless_valid_model_term`, `::test_short_naam_uses_model_term`, `::test_naam_with_digits_allowed`; e2e `test_flow.py::test_generic_model_term_replaced_by_naam`, `::test_nameless_group_uses_valid_model_term` |
| 5 | yes | `test_flow.py::test_sleutel_matches_helper` |
| 6 (amended) | yes | `test_flow.py::test_collision_flag` (asserts the exact `botsing: 1 transacties in Auto`) |
| 7 | yes | `test_flow.py::test_shadow_flag` |
| 8 | yes | `test_gpu.py::test_no_egpu_exit_2_no_requests` (0 requests, no CSV) |
| 9 | yes | `test_gpu.py::test_card_vram_low_exit_3`, `::test_model_process_vram_low_exit_3` (plus not-found and fdinfo variants) |
| 10 | yes | `test_io.py::test_db_hash_unchanged`, `::test_connection_is_readonly` |
| 11 | yes | `test_io.py::test_header_and_empty_akkoord` |
| 12 | yes | `test_flow.py::test_abort_after_four_failures_writes_partial` |
| 13 | yes for the tested forms; **the FR behind it fails for padded input (R1)** | `test_flow.py::test_no_iban_in_requests` |
| 14 `manual:` | executed, passed | `06-fixes.md` AC14. Justified: it needs the physical eGPU and the live model. |
| 15 `manual:` | for sign-off | Justified: real data, Joost only. |

Out-of-scope check: nothing writes to the DB on the normal path, no categories are created (enum from `categorieen`, `Ongecategoriseerd` removed), no llama-server start/stop, loopback only, `saldoboek/` untouched, nothing runs automatically after an import.

Test accretion: every automatable AC has a committed permanent test, and both `manual:` labels are justified by hardware or real data. **The protocol's coverage table is stale, though (R4).**

## Findings

### Required (changes requested)

- **R1: IBANs in padded or glued forms still reach the prompt. This breaks the FR "No IBANs in the prompt".** `prompt.py:27-28` runs `IBAN_RE.sub` *before* `" ".join(text.split())`. `IBAN_RE` (`prompt.py:12`) allows at most one space between characters. So `NL00  RABO  0000  0000  04` (double spaces, tabs, NBSP) passes the regex and is then collapsed into exactly the spaced IBAN form. I reproduced this above. Bank exports often pad fields with runs of spaces, so this is realistic input, not a contrived one. The glued form `IBANNL00RABO0000000007` has no `\b` before `NL`, so it passes too, and it **matches the AC13 regex literally** (hunt F2). The few-shot path goes through the same `scrub`. The traffic stays on loopback, so this isn't a network breach. It is a demonstrated failure of a brief FR, and the fix is two lines. **Change:** collapse whitespace before the substitution, and let the pattern start after a letter prefix (e.g. `(?<![0-9])` or `(?<![A-Z0-9])` after stripping a leading `IBAN`). Dash and dot separators are optional. Add the double-space, tab, NBSP and glued cases to `test_flow.py::test_no_iban_in_requests`, including one in a few-shot row.
- **R2: `categorie IS NULL` transactions are part of the input. This is an undocumented deviation.** The brief's input FR is `categorie = 'Ongecategoriseerd'`. Spec step 5 says "Group the `Ongecategoriseerd` rows". Spec review N5 said explicitly: *"The brief selects only 'Ongecategoriseerd', so keep that"*, and treat NULL as uncategorised **only** in the collision check. `build_groups` filters with `is_uncategorized` (`__main__.py:59` → `grouping.py:28-29`, `None or 'Ongecategoriseerd'`). As a result, NULL-category transactions are grouped, sent to the model, and counted in `aantal`/`totaal_bedrag`. `03-implementation-log.md` says "Deviations from the spec: None". This matters beyond this item: 0003 finds a group's transactions again by `sleutel`, so the two tools must agree on which rows are input. **Change (either one):** (a) restrict the input to `tx.categorie == UNCATEGORIZED`, as the brief says, and keep `is_uncategorized` for collisions and few-shot; or (b) keep it and add a Decision row. The rationale would be that SaldoBoek's `uncategorize_transaction` sets NULL (`database.py:577-586`), with the brief-literal predicate as the rejected alternative, plus a note that 0003 must import the same predicate from `tools/ai_common`. Either way, add a test that pins the chosen behaviour.
- **R3: the review temp file can write into the database.** This is the brief's first hard line (*"The tool never writes to it"*). `review.py:29-30` does `open(f"{path}.tmp", "w")`, which follows a symlink and truncates a hardlinked inode. `check_output` only checks `realpath(--out)`. Hunt round 2 (R2-1) reproduced the result: exit 0, and `database.db` is overwritten with CSV bytes, when `<out>.tmp` is a symlink or hardlink to the DB, or when the DB itself is named `<out>.tmp`. The precondition is unlikely, but the outcome is total loss of the one file the brief protects, and the fix is small. **Change:** create the temp file with `tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")` (O_EXCL, never reuses an existing name), write through `os.fdopen(fd, "w", encoding="utf-8-sig", newline="")`, then `os.replace`. Clean up the temp file if the write fails. Add a regression test in `test_io.py`: a symlink at `<out>.tmp` pointing to the DB, and after the run the DB's SHA-256 is unchanged.
- **R4: `04-test-protocol.md` doesn't match the tests.** The coverage table's AC4 row (`:19`) names three tests that round 1b deleted (`test_digits_fall_back_to_naam`, `test_invalid_when_fallback_fails`, `test_digits_zoekterm_falls_back`), and it still describes the pre-amendment AC. The AC6 row (`:21`), case 2.1 (`:56`) and the high-stakes rows for `zoekterm` and collision (`:99-100`) also describe pre-amendment behaviour. The header still cites spec rev 2 (`:4`). The sign-off and the 0003 author rely on this table. **Change:** update the AC4 and AC6 rows to the amended wording and to the tests listed in `06-fixes.md` round 1b, update 2.1 and the high-stakes rows, set the spec ref to rev 3, and add the tests that come out of R1 to R3.

### Notes (no change required)

- **N1, `03-implementation-log.md`:** the header says "rev 2". The Decisions table runs 1-5, 7, 6. "Deviations: None" has to change if R2 goes route (b). The `__main__.py:7` docstring refers to `tools.ai_apply`, which doesn't exist yet (it's item 0003). This is harmless, but keep it in mind.
- **N2, decision audit:** every logged decision is reversible and within delegated latitude or already gate-accepted: the per-process VRAM check, spill as a warning, `zekerheid` normalise and clamp, exit 1 on abort, post-check after the first success, 300 s timeout, the `(geen naam)` display, 120-char samples, the test-file layout, and failed groups kept in the partial file. The round-1 `check_output` fix only adds refusals. Nothing irreversible was decided unilaterally.
- **N3, backlog, carry into the sign-off (hunt E3):** an unwritable or wrong `--out` directory is only discovered after all the model calls, and the run ends in a traceback. A cheap pre-check next to `check_output` would be welcome in the R3 change, but it isn't required.
- **N4, for the sign-off and the 0003 brief:** E1 residue (prefix overlap between rows of one review file, generic model terms for short-name and nameless groups) and N21 (a mixed-sign counterparty gives two rows with the **same** zoekterm, and `UNIQUE(zoekterm, gebruiker_id)` means only one can become a rule). None of this is flagged in the CSV. R2-3 (re-running with the same explicit `--out` overwrites a reviewed file) belongs in the same list.
- **N5, low:** R2-2 (a named group loses a valid category when the unused model zoekterm is null; GBNF prevents this when the model is live), F1 (`zekerheid` 1.5 → 0,01 with no flag, per spec Decision 3), E4 (control characters in the printed name). `--sysfs-root` (E5) is a flag the brief itself requires, so it isn't a finding. The post-check runs once per run, not per call, which is what the spec says.

Review 1 outcome: changes requested (R1 to R4). See the re-review below.

## Re-review (after fix round)

**Diff:** `git diff dev...HEAD` (now through `5a77b1f`, 26 files, +2846). The fix commit `5a77b1f` touches `prompt.py`, `review.py`, `__main__.py`, two test files and three docs. `saldoboek/` is still untouched. The commit subject references `0002-ai-suggest`. **Date:** 2026-09-18.

**Honesty spot-check:** `.venv/bin/python -m pytest -q` → **64 passed** (25.4 s), which matches `06-fixes.md` round 2.

### Required changes from review 1

| # | Resolved? | Evidence |
|---|---|---|
| R1 IBAN padded/glued | **Yes for the IBAN cases, but the fix broke something else (R5)** | `prompt.py:33-34` now collapses whitespace before it masks. `IBAN_RE` (`prompt.py:14`) allows ` `, `.` and `-` between characters and has no leading boundary. `test_flow.py::test_no_iban_in_requests_padded_and_glued` covers double space, tab, NBSP, dashes, dots, glued `IBANNL…`, and a padded IBAN in a few-shot row. I checked the few-shot path: `fewshot_examples` uses the same `scrub`. |
| R2 NULL category as input | Yes, via route (a) | `__main__.py:60` uses `tx.categorie != UNCATEGORIZED`. `is_uncategorized` is still used for collisions (`rules.py:50`) and few-shot (`prompt.py:48`), as spec review N5 intended. `test_flow.py::test_null_category_not_grouped` inserts a real NULL through `conftest.py:52-60`, then asserts 0 requests and 0 rows. "Deviations: None" in the log is accurate again. |
| R3 `<out>.tmp` link into the DB | Yes | `review.py:35-47` uses `mkstemp` in the output directory (O_EXCL, random name), `os.fdopen`, then `os.replace`, and unlinks the temp file on any exception. `os.replace` swaps a directory entry, so even a hardlinked `--out` can't reach the DB inode. `test_io.py::test_tmp_symlink_to_db_cannot_overwrite` asserts the DB's SHA-256 is unchanged and the symlink is untouched. The side effect is a 0600 review file, logged as Decision 8 and pinned by `test_review_file_is_private`. It's reversible and sensible for a file that holds bank data. |
| R4 stale protocol | Yes | `04-test-protocol.md` now cites spec rev 3 and the amended brief. Its AC4/AC6 rows name the round-1b tests, which exist. Case 2.1, case 2.4 and the high-stakes rows describe the amended behaviour. The AC10 and AC13 rows and two new FR rows list the new tests. I checked every test name in the table against `tests/ai_suggest/`, and all of them exist. |

### New finding

- **R5 (required): the new `IBAN_RE` over-masks ordinary descriptions and wipes the model's context.** Dropping the leading boundary (`prompt.py:14`), allowing `.`/`-`, and leaving no trailing boundary means the pattern matches wherever the last two letters of *any* word are followed by a number and ~11 more alphanumeric characters. The pattern then eats up to 30 characters. I ran `scrub` on synthetic strings (no DB, no endpoint):
  - `Factuur 2026-00123 abonnement oktober` → `Factu[IBAN]`
  - `Termijn 3 van 12 maanden huur` → `Termijn 3 v[IBAN]`
  - `Omschrijving: huur okt 2026 woning 12a` → `Omschrijving: huur o[IBAN]`
  - `Kenmerk 1234567890123456 Test Energie` → `Kenme[IBAN]`

  The pre-fix pattern left all four intact. Any description or name with a year, invoice number or kenmerk after a word loses most of its text. That is exactly the text the model needs to pick a category, and it's how the model picks a zoekterm for nameless groups. No hard line is crossed (masking more is privacy-safe), but it silently degrades the feature's main output. AC14's plausibility check ran on the pre-fix code, so nothing has caught this. **Change:** restore the boundaries without losing the glued case. For example, `(?:(?<=IBAN)|(?<![A-Z0-9]))[A-Z]{2}[ .\-]?\d{2}(?:[ .\-]?[A-Z0-9]){11,30}(?![A-Z0-9])` with `re.IGNORECASE`. I checked that exact pattern: it still masks all seven variants in `test_no_iban_in_requests_padded_and_glued` plus `iban: nl00knab0000000000`, and it leaves the four strings above unchanged. Any equivalent pattern is fine. Add a permanent test (e.g. `test_prompt`-style, in `test_flow.py` or `test_io.py`) that asserts `scrub` keeps those non-IBAN strings intact, so the IBAN tests can't be satisfied by masking everything. Add a row to `06-fixes.md` and the protocol's 2.4 row.

### Rest of the diff

- No other regressions from the fix round. `build_groups`, `check_output`, the GPU guard, loopback confinement and stdout hygiene are unchanged, and the hard-lines table from review 1 still holds. Stdout never goes through `scrub`, so R5 affects only prompt quality.
- **N6 (note):** in `review.py:36-47`, if `os.fdopen` itself raised, the raw fd would leak. That's negligible for a one-shot CLI and not a finding. The Decisions table lists row 8 between rows 3 and 4 (cosmetic, like N1).
- Notes N3 to N5 from review 1 stay open for the sign-off and the 0003 brief. N3 (an unwritable `--out` directory is only discovered at the end) is still true: `mkstemp` now raises at write time, after all the model calls.

Review 2 outcome: changes requested (R5). See re-review 3 below.

## Re-review 3 (after interactive round 3)

**Diff:** `git diff dev...HEAD` (through `2565bde`, 30 files, +3044). Since review 2, the only code change is `a2503dc`: `tools/ai_suggest/prompt.py` (+20/-5) and the new `tests/ai_suggest/test_prompt_scrub.py`. The rest of that commit and `2565bde` are docs. `saldoboek/` is still untouched, and every commit subject references `0002-ai-suggest`. The PO's interactive continuation (`06-fixes.md` round 3) replaces the cap. The `PARKED` status in `08-signoff.md` and the ledger is not held against the code. **Date:** 2026-09-18.

**Honesty spot-check:** `.venv/bin/python -m pytest -q` → **82 passed** (24.9 s). This matches `06-fixes.md` round 3 (64 + 10 + 8 new parametrised scrub cases). Every probe below used synthetic strings only: no DB, no endpoint, no source changes. The probe scripts are in the session scratchpad, not the repo.

### R5 (over-masking): resolved for the cases it named

- `prompt.py:15-18` restores boundaries on both sides, with the `(?<=IBAN)` exception for the glued form. That's the pattern review 2 proposed. `_mask_iban` (`prompt.py:24-28`) masks a candidate only if it has ≥ 10 digits.
- `test_prompt_scrub.py` checks 10 IBAN forms positively and 8 ordinary descriptions for exact equality (`06-fixes.md` and the log say "9" and "7/9"; the list has 8, which is cosmetic). All four R5 strings are intact again. The negative side means masking everything can no longer pass the IBAN tests.
- **The ≥ 10-digit rule on its own is sound.** Every real IBAN has at least 10 digits: NL has 12 (2 check + 10 account), NO, the shortest, has 13, BE 14, and DE, GB and FR more. When an IBAN is the leftmost candidate, the greedy match always contains the whole IBAN, because its own end is a valid boundary. So the threshold can't reject an IBAN that starts its own match. I confirmed compact and spaced NO, BE, GB and DE IBANs are masked.
- **Ordinary Dutch bank text mostly stays intact.** The 8 test strings stay intact, and so do the formats I tried in addition: `BEA NR:… 18.09.26/12.34 AH TO GO 1418 AMSTERDAM,PAS 123`, `Pasvolgnr: 012 18-09-2026 12:34 Transactie: … Term: …`, `CCV*Test Bakkerij 18-09-2026 12:34 PAS 012`, `Apple Pay AH 1234 Amsterdam NLD`, `Termijn 3 van 12 in 2026 zorgverzekering`, and `/TRTP/…/IBAN/<iban>/BIC/…/NAME/…`, where only the IBAN is masked. The remaining over-masking is listed as N7 below.

### New finding

- **R6 (required): a spaced, dashed or dotted IBAN can reach the prompt whole or in part. This breaks the brief FR "No IBANs in the prompt" (`00-brief.md:37`).** The cause is how the pattern and the substitution interact, not the threshold on its own. `IBAN_RE` allows a separator before each of up to 30 characters, so a candidate can **start at an earlier 2-letter word followed by 2 digits** (`AH 12`, `NS 20`, `nr 12`, `op 18`) and run across the following words into the IBAN. There it backtracks to a separator *inside* the IBAN. `re.sub` then continues after that match, so the IBAN's own start (`NL00`) is used up and never checked again. What happens next depends on the digit count of that early candidate:
  - **Below 10 digits, `_mask_iban` rejects it and the whole IBAN leaks** (round 3 made this worse):
    - `Retour AH 12 boodschappen teruggestort NL00 ABNA 0000 0000 01` → unchanged
    - `NS 20 euro retour graag naar NL00 INGB 0000 0000 01` → unchanged
    - `nr 12 van Test Energie via NL00-ABNA-0000-0000-01` → unchanged
  - **10 digits or more, it's masked, but the account digits after the cut leak.** This part was already present in the pattern review 2 proposed, so the gate shares responsibility for it:
    - `Huur op 18-09-2026 overgemaakt naar NL00 ABNA 0000 0000 01` → `Huur [IBAN] 0000 0000 01`

  User-typed transfer descriptions with a spaced IBAN ("terugbetalen naar NL.. …") are exactly where spaced forms occur, and a short word followed by a number just before them is ordinary Dutch. This is the same category of break as review 1's R1. Compact IBANs aren't affected, because a match can't end inside them.

  **Change:** check every candidate start on its own, so that one candidate can never hide another. Then mask the **union** of the accepted spans. Example: for each position `i`, `m = IBAN_RE.match(text, i)`; if it has ≥ `IBAN_MIN_DIGITS` digits, record `(m.start(), m.end())`; merge overlapping spans and replace each merged span with `[IBAN]`. The lookbehinds still see the text before `i`. I tested that sketch with the current `IBAN_RE` unchanged:
  - all 18 existing scrub cases pass;
  - all five strings above, plus `AB 12 Test Energie Amsterdam NL00 ABNA 0000 0000 01`, `nr 12 3456 NL00 ABNA 0000 0000 01` and `nr 12 345678 9012 NL00 ABNA 0000 0000 01`, come out with no IBAN digits left.

  Any equivalent fix is fine; a pattern tweak alone isn't enough. For example, a variant I tried with 4-character groups still lost `NL00` to a preceding candidate when the word lengths happened to line up. Add these leak strings to `test_prompt_scrub.py::IBANS`. The existing assertion (`"0000"` not among the output digits) already catches both the whole leak and the partial one. Update the `06-fixes.md` row and protocol row 2.4.

### Notes (no change required)

- **N7, remaining over-masking.** It's privacy-safe, so it's fine to fold into the R6 change but not required. A candidate takes up to 30 characters, **including the words that follow**:
  - Words after a real IBAN are lost: `Overboeking NL00ABNA0000000001 Test Energie huur` → `Overboeking [IBAN]`, and `… IBAN: <iban> BIC: ABNANL2A …` → `[IBAN]: ABNANL2A`.
  - A 2-letter word before a long number takes the number and the words after it:
    - `Tikkie ID 000012345678 Test Pizza avond` → `Tikkie [IBAN]`
    - `Betaald op 18-09-2026 om 12.34 uur` → `Betaald [IBAN]`
    - `Fact nr 2026001234 dd 18-09-2026` → `Fact [IBAN]`
  - A SEPA creditor ID (`NL00ZZZ…`) is masked too.

  Punctuation (`,` `:` `/`) stops the greed, and the structured ING/ABN/Tikkie exports use it, so the practical loss is usually a label. Still, the positive tests only check that `[IBAN]` appears. Asserting the surrounding text as well (e.g. `scrub("Overboeking NL00ABNA0000000001 okt") == "Overboeking [IBAN] okt"`) would pin this down if it's ever tightened. One design I tried keeps every string in this note intact and closes all the R6 leaks: a compact pass with no separators, then a separated pass where each chunk after the bank code must contain a digit. It still needs the union step from R6 to be safe, so the union step is the required part.
- **N8:** the round-3 docs are otherwise accurate. The `06-fixes.md` round-3 row and protocol 2.4 match the code, the log's test-run table has the round-3 line, and the AC14 re-run on `2565bde`'s code is recorded (10.6 GiB resident, no spill, 0600 CSV). R6 only affects the text inside prompts, so it doesn't change the AC14 result, and after the R6 fix only the masking of spaced IBANs differs from the code AC14 ran. A new GPU run isn't needed for R6.
- **Rest of the diff:** unchanged since review 2 (`git diff 91d7a71..HEAD` touches no other code). The hard-lines table from review 1, R1 to R4 as resolved in review 2, and the AC→test table all still hold. AC13 now also maps to `test_prompt_scrub.py`. Notes N1 and N3 to N6 stay open for the sign-off and the 0003 brief.

Verdict: changes requested
