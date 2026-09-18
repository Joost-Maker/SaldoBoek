# Technical Spec — AI suggest: GPU category + rule proposals

**Date:** 2026-09-18
**Brief:** 00-brief.md (snapshot of `DEV/SaldoBoek AI suggest - GPU category and rule proposals.md`)
**Revision:** 3

---

## Interpretation of the brief

A fork-only CLI (`python -m tools.ai_suggest`) that opens SaldoBoek's SQLite DB **read-only**, groups one user's `Ongecategoriseerd` transactions by counterparty key and sign, and asks the local OpenAI-compatible endpoint (`llama-server` router on :6767, Qwen3-14B pinned to the eGPU) for one schema-constrained `{categorie, zoekterm, zekerheid}` per group. It validates each zoekterm deterministically, runs the collision and shadow checks with SaldoBoek's rule semantics, and writes a `;`/`utf-8-sig` review CSV for LibreOffice. A GPU guard refuses to run without the eGPU and aborts if the model isn't actually resident on it. No writes to the DB, no new dependencies, no traffic except the local endpoint.

---

## Pre-spec probe (2026-09-18, synthetic prompt, no real data)

One real call against `Qwen3-14B-Q4_K_M` on :6767 with a `json_schema` `response_format` and `chat_template_kwargs.enable_thinking=false`:
- **Grammar constraint works:** `categorie` came back from the enum.
- **`zekerheid` came back as `95`, not 0..1.** The schema must carry `minimum: 0, maximum: 1`, and the client normalises values in (1, 100] to /100 as defence.
- **The model's zoekterm wasn't a substring** of the transaction text (`"streaming abonnement"` vs `"… maandabonnement streaming"`), which confirms the deterministic validation and fallback are needed.
- **The card-level VRAM check in the brief is too weak on this machine.** Before the call, the eGPU already had 10.1 GB in use: the Jan desktop app's own router (port 62872) had `gpt-oss-20b` resident, 9.1 GiB, found via `/proc/<pid>/fdinfo` `drm-memory-vram`. Qwen then got only ~6.2 GiB on the card and ran at 1.9 tok/s, spilling to system memory. A check of `mem_info_vram_used ≥ 4 GiB` passes here even if Qwen were entirely off the eGPU. See *GPU guard* below.

---

## Proposed approach

### Files to create (all fork-only)
- `tools/__init__.py`: empty package marker.
- `tools/ai_common/__init__.py`, `tools/ai_common/grouping.py`: **the shared group-key helper** `group_key(naam, omschrijving) -> str` (lowercased, stripped `naam`, or `omschrijving` if `naam` is empty) and `sign_type(bedrag) -> "inkomsten"|"uitgaven"` (`> 0` → inkomsten, as SaldoBoek). The apply item (0003) must import these, not copy them.
- `tools/ai_suggest/__init__.py`
- `tools/ai_suggest/__main__.py`: argparse CLI (the brief's flags, plus hidden `--proc-root` for tests), orchestration and exit codes.
- `tools/ai_suggest/db.py`: read-only access: `sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)` (`as_uri` escapes spaces and `#`). Queries for users, a user's categories, `Ongecategoriseerd` transactions, all transactions (for collisions), few-shot rows, and active rules. The rules are loaded exactly as `Categorizer._load_rules`: global (`gebruiker_id IS NULL`) first, then user rules overriding the same lowercased term, and the insertion order is preserved (first match wins). **SaldoBoek's `DatabaseManager`/`Categorizer` aren't used**, because `DatabaseManager.__init__` writes (CREATE/seed) and would break read-only.
- `tools/ai_suggest/rules.py`: `validate_zoekterm(term, group_texts)` (lowercase, ≥ 4 chars, no digits, substring of every group text). **`choose_zoekterm(model_term, naam, group_texts)` (rev 3, PO amendment):** if `naam.strip()` has ≥ 4 chars → the zoekterm is `naam.strip().lower()`, digits allowed, and the model term is ignored (it's always a substring of every group text, because `rule_text` starts with the name and the group key is that name). Otherwise → the model term with `validate_zoekterm`, else `""` plus `zoekterm ongeldig`. There's no naam fallback any more, since the name was already tried first. `collisions(term, categorie, all_tx)`, `shadowed_by(group_texts, rules)`.
- `tools/ai_suggest/prompt.py`: Dutch system prompt, few-shot block, per-group user message; `scrub()` replaces IBANs with `[IBAN]` in every string that goes into a prompt. It matches case-insensitively and allows optional single spaces between characters, so it also catches `nl00 knab 0000 0000 00` and lowercase forms. The AC13 test pattern (`[A-Z]{2}\d{2}[A-Z]{4}\d{10}`) is a subset.
- `tools/ai_suggest/llm.py`: `LLMClient(endpoint, model, api_key, timeout)` with `suggest(messages, schema) -> dict`, stdlib `urllib.request`. **Network confinement:** the opener is built with `urllib.request.build_opener(ProxyHandler({}), NoRedirect())`, so it ignores `http_proxy`/`https_proxy`/`all_proxy`, and any 3xx raises `LLMError` (`NoRedirect` is a `HTTPRedirectHandler` subclass whose `redirect_request` raises). `check_endpoint(url)` accepts only the `http` scheme with host `127.0.0.1`, `::1` or `localhost`; anything else → exit 1 `endpoint moet lokaal zijn (127.0.0.1/::1/localhost)`, before the DB is opened and before any request. The body has `temperature: 0`, `chat_template_kwargs: {enable_thinking: false}` and `response_format: {type: json_schema, json_schema: {name, schema}}`. Any HTTP/URL error, timeout, non-JSON content, missing key or a `categorie` outside the enum raises `LLMError`. It normalises `zekerheid`.
- `tools/ai_suggest/gpu.py`: the GPU guard (below).
- `tools/ai_suggest/review.py`: CSV writer: `;`, `utf-8-sig`, the brief's exact column order, atomic (write `*.tmp` in the same dir, then `os.replace`). **Numbers use a decimal comma** (`totaal_bedrag` `-29,97`, `zekerheid` `0,85`), so Dutch-locale LibreOffice reads them as numbers. The apply item doesn't read these two columns.
- `tests/ai_suggest/__init__.py`, `tests/ai_suggest/conftest.py`: a synthetic-DB builder (via SaldoBoek's `DatabaseManager(db_path=tmp_path/…)` **in tests only**, then **delete the ~140 seeded global rules**, whose 2-letter terms like `da`/`ns` would match synthetic text first, then direct inserts of exactly the rules each test needs), a threaded stub OpenAI server (`http.server`) that records request bodies and returns scripted responses, and fake sysfs + proc trees in `tmp_path`.
- `tests/ai_suggest/test_*.py`: acceptance tests (mapping below).

### Files to modify
- None in `saldoboek/`. `tests/test_smoke.py` is untouched.

### GPU guard (`gpu.py`)
1. **Before any model call:** find the eGPU. It's the card in `<sysfs>/card*/device` with `mem_info_vram_total ≥ 8 GiB` (largest if several); its PCI address is `basename(realpath(device))`. No such card → exit **2**, `eGPU niet aangesloten — geen CPU/iGPU-fallback`, 0 requests.
2. **After the first successful model response:**
   a. brief check: that card's `mem_info_vram_used ≥ 4 GiB`, else exit **3** `model draait niet op de eGPU`;
   b. **per-process check (tightening, see Decisions):** distinct exit-3 messages: `model-proces niet gevonden op :<port>`, `fdinfo onleesbaar voor pid <n>`, and `model draait niet op de eGPU (<x> GiB resident)`. under `<proc>`, find the process whose cmdline has `--alias <model>` and whose parent's cmdline has `--port <endpoint port>`. Sum `drm-memory-vram` (KiB) over its `fdinfo` entries with `drm-pdev == <eGPU pci>`, deduplicated by `drm-client-id`. Below 4 GiB, or model process not found → exit **3** with the measured value. Only this check tells that Qwen is resident, rather than something else.
   c. **spill warning (not fatal):** if the model process holds < 90 % of its `.gguf` file size (the path comes from its `--model` arg), print a warning with the other top VRAM holders on the eGPU (pid, alias or binary name, GiB). It's **repeated in the final summary**. This is exactly today's situation with Jan desktop's gpt-oss-20b.
3. The report prints the eGPU reading: card used/total and the model process's GiB.

### Flow (`__main__.py`)
1. Parse args; `check_endpoint` (exit 1 if not loopback, nothing read or sent). The API key comes from the env var named by `--api-key-env` (missing → warning, no auth header).
2. GPU pre-check (exit 2).
3. Open the DB read-only; resolve the user (no `--gebruiker` and ≠ 1 user → exit 1 listing the users).
4. Load categories, rules, all of the user's transactions, and the few-shot rows.
5. Group the `Ongecategoriseerd` rows by `(group_key, sign_type)`. For each group: count, sum `bedrag` (2 decimals), up to 3 distinct sample `omschrijving`s, the display `naam`.
6. Sort groups by count desc, then key asc; number them `groep` 1..n.
7. Per group: allowed = the user's categories of that sign type (none → flag `geen categorieën voor <type>`, skip the model). Build messages and call the model. After the first success, run the post-check (exit 3). On `LLMError` → flag `model-fout`, blank the proposal; count consecutive failures; the 4th in a row → print `afgebroken na 4 opeenvolgende modelfouten`, write the CSV for the groups done so far, exit 1.
8. Zoekterm validation and fallback, collision, shadow → `vlaggen` (joined with ` | `). The collision check treats `categorie IS NULL` like `Ongecategoriseerd` (not a collision). Each group prints a progress line: `[i/n] <naam> (<aantal>×) → <categorie> in <s> s`.
9. Write the CSV (default path `<db dir>/ai_review_<YYYYmmdd-HHMMSS>.csv`) and print a summary (groups, calls, mean seconds per call, flag counts, eGPU reading, CSV path). Names and totals only.
10. Exit 0.

### Config changes
None (no `saldoboek/config` changes). Defaults are module constants in `__main__.py`.

### Data model / stored format changes
None for SaldoBoek. **New file format:** the review CSV, as the brief defines it. The 0003 apply item depends on it.

---

## Requirement mapping

| Brief requirement / acceptance criterion | Where it's handled |
|---|---|
| FR command, flags, defaults, `--gebruiker` rule | `__main__.py`; `test_cli.py::test_single_user_default`, `::test_multiple_users_requires_flag` |
| FR read-only (`mode=ro`) | `db.py`; `test_readonly.py::test_db_hash_unchanged`, `::test_connection_is_readonly` |
| FR grouping, one call per group | `ai_common/grouping.py`, `__main__.py`; `test_flow.py::test_two_groups_two_calls` |
| FR allowed categories by sign; mixed-sign split | `__main__.py` step 5/7; `test_flow.py::test_enum_by_sign`, `::test_mixed_sign_split` |
| FR constrained call (stdlib, schema, no-think, temp 0) | `llm.py`; `test_llm.py::test_request_body_shape` |
| Out-of-scope: no network except the local endpoint | `llm.py` opener + `check_endpoint`; `test_llm.py::test_ignores_proxy_env` (`http_proxy`/`https_proxy`/`all_proxy` → a dead port; the request still reaches the stub), `::test_redirect_refused`, `test_cli.py::test_non_loopback_endpoint_refused` (exit ≠ 0, stub gets 0 requests, DB never opened) |
| FR few-shot, no IBANs | `prompt.py`; `test_prompt.py::test_fewshot_limit_and_order`, `test_flow.py::test_no_iban_in_requests` |
| FR zoekterm validation + fallback | `rules.py`; `test_rules.py::*` |
| FR collision check | `rules.py`; `test_flow.py::test_collision_flag` |
| FR shadow check | `rules.py` + `db.py` rule order; `test_flow.py::test_shadow_flag` |
| FR GPU guard pre/post | `gpu.py`; `test_gpu.py::*` |
| FR review CSV format, atomic, default path | `review.py`; `test_review.py::*` |
| FR stdout summary, no descriptions | `__main__.py`; `test_flow.py::test_stdout_has_no_descriptions` |
| FR model failure handling, abort after 4 in a row | `__main__.py`; `test_flow.py::test_model_error_flag`, `::test_abort_after_four_failures_writes_partial` |
| AC1 5 tx / 2 groups → 2 calls, rows 3 and 2 | `test_flow.py::test_two_groups_two_calls` |
| AC2 invented category or free text → `model-fout` | `test_flow.py::test_model_error_flag` (both variants) |
| AC3 enum per sign | `test_flow.py::test_enum_by_sign` |
| AC4 (amended): naam wins (`woning` → `test woonstichting`); empty naam + `abonr.4163` → `zoekterm ongeldig`; empty naam + valid `maandhuur` → `maandhuur` | `test_rules.py::test_naam_always_wins`, `::test_nameless_invalid_model_term`, `::test_nameless_valid_model_term`, `::test_short_naam_uses_model_term`; `test_flow.py::test_generic_model_term_replaced_by_naam` |
| AC5 `sleutel` = shared helper | `test_flow.py::test_sleutel_matches_helper` |
| AC6 (amended): group `Test Garage` vs `Test Garage Onderdelen` in `Auto` → `botsing: 1 transacties in Auto` | `test_flow.py::test_collision_flag` |
| AC7 rule `bakker` → `al gedekt door regel 'bakker'` | `test_flow.py::test_shadow_flag` |
| AC8 no eGPU → exit 2, 0 requests | `test_gpu.py::test_no_egpu_exit_2_no_requests` |
| AC9 VRAM < 4 GiB after the first call → exit 3 | `test_gpu.py::test_card_vram_low_exit_3`, `::test_model_process_vram_low_exit_3` |
| AC10 DB SHA-256 unchanged, `mode=ro` | `test_readonly.py::*` |
| AC11 CSV header exact, `akkoord` empty | `test_review.py::test_header_and_empty_akkoord` |
| AC12 4 failures → abort + partial file | `test_flow.py::test_abort_after_four_failures_writes_partial` |
| AC13 no IBAN in request bodies | `test_flow.py::test_no_iban_in_requests` (the synthetic data deliberately contains fake IBANs in `omschrijving`) |
| AC14 `manual:` real GPU run on synthetic data | bug hunt (this laptop has the eGPU); the report shows the per-process VRAM line |
| AC15 `manual:` Joost's real run | sign-off "What to eyeball" |

---

## High-stakes output impact

No stored data changes (read-only). The high-stakes output is the **review CSV**, because Joost's approvals become rules in 0003. A wrong `sleutel` or a zoekterm that passes validation but over-matches would later mis-categorise. Mitigations: one shared key helper, deterministic validation (substring of every group text, ≥ 4 chars, no digits), a collision check over all of the user's transactions, and an enum-constrained category.

---

## Architecture notes

- [x] CLAUDE.md rules respected: no real data, Python 3.8 syntax, no GUI imports in tests, fork-only code outside `saldoboek/`.
- [x] No changes outside the files listed above.
- [x] Config over hardcoding: endpoint, model, API-key env, sysfs/proc roots and thresholds (8 GiB card, 4 GiB resident, 90 % spill, 4 failures, 300 s timeout) are module constants or flags.

**Decisions (reversible):**
1. **Per-process VRAM check added on top of the brief's card-level check**, justified by the probe: the card-level check alone can't tell Qwen from Jan desktop's gpt-oss. It only tightens the guard: no path allows a fallback, so this isn't the brief's must-park case. If the gate disagrees, it's one function to drop.
2. The spill case (< 90 % resident) is a **warning, not an abort**. The model still runs on the eGPU, just slower, and aborting would block Joost whenever the Jan app has a model loaded. The brief's hard line (< 4 GiB → exit 3) is kept.
3. `zekerheid` > 1 is normalised (/100 when ≤ 100), and the schema carries 0..1 bounds.
4. The abort after 4 consecutive failures uses exit code 1; the brief didn't specify one.
6. **The post-check runs after the first *successful* model response**; the brief says "after the first model response". A failed response (HTTP error or timeout) proves nothing about where the model sits, and the model may not even be loaded. Until a success, no proposals are produced, so nothing gets past the guard.
7. The HTTP timeout is **300 s** (not 120 s). A cold load of the 12.7 GiB model through the router, plus the first generation, took ~44 s in the probe, and far longer while spilling. Timeouts count as model failures.
8. `zekerheid` outside [0, 1] after normalisation (negative, > 100, non-numeric) → clamped to [0, 1] and the group gets the flag `zekerheid ongeldig`.
5. Rules are loaded by SQL mirroring `Categorizer._load_rules`, instead of importing `Categorizer`, because of read-only.

---

## Test scope

- All unit and acceptance tests run offline: stub HTTP server, fake sysfs and proc trees, synthetic DB. The suite never calls :6767 and never reads the real `/sys` or `/proc`, because the roots are injected.
- The bug hunt adds the manual AC14: a real run against a synthetic DB on this laptop's eGPU. The Jan desktop model should be unloaded first (or the spill warning observed and reported).

---

## Open questions for PO

(none)

---

## Revision notes

- Rev 2 (after `02-spec-review.md`, changes requested): **network confinement** (R1): a proxy-free, no-redirect opener, a loopback-only `--endpoint` checked before the DB is opened, and three tests. Logged the post-check-after-success deviation (Decision 6). Folded in the gate's notes: distinct exit-3 messages (N1), spill warning repeated in the summary (N2), seeded rules removed in the test DB builder (N4), NULL category ≠ collision (N5), decimal comma in the CSV (N6), per-group timing lines (N7), broader IBAN scrub (N8), `as_uri()` (N9), a `zekerheid` range flag and a 300 s timeout (N10).
- Rev 3 (PO amendment, Joost, 2026-09-18, during fix round 1, see `00-brief.md`): the zoekterm is the full lowercased counterparty name whenever the name has ≥ 4 chars; the model's zoekterm is used only for nameless or too-short-name groups. Triggered by AC14 real output (`woning`, `salaris`, `de hoek`). This is the second and last allowed spec revision cycle.
