# Test Protocol
**Date (UTC):** 2026-09-18T12:30:00Z
**Feature:** AI suggest: GPU category + rule proposals (0002-ai-suggest)
**Brief ref:** 00-brief.md (incl. PO amendment) · **Spec ref:** 01-spec.md (rev 3)
**Updated:** 2026-09-18 after code gate review 1 (PO amendment, IBAN/temp-file/NULL fixes)
**Scope:** New fork-only CLI `python -m tools.ai_suggest` (read-only DB, local LLM on the eGPU, review CSV).
**Dependencies:** repo venv `.venv/bin/python`. For the **real-GPU case (section 5)**: the llama-server router on `127.0.0.1:6767` (systemd, already running), the eGPU attached, and the API key in env `AI_SUGGEST_API_KEY` (the tester is given the value; it's never written into the repo).

> ⛔ **Hard rule:** never open real bank data. Nothing under `~/Code/Financien`, never `saldoboek/data/database.db`, no *.db you didn't create yourself in a temp dir. Every database is synthetic (build it like `tests/ai_suggest/conftest.py::SyntheticDB`), with fake names and fake IBANs only.

---

## Acceptance criteria coverage

| Acceptance criterion (from 00-brief.md) | Automated test (file::case) | Manual case below |
|---|---|---|
| AC1: 5 tx / 2 counterparties → 2 calls, rows 3 and 2 | `tests/ai_suggest/test_flow.py::test_two_groups_two_calls` | 1.1 |
| AC2: invented category / free text → `model-fout` | `test_flow.py::test_model_error_flag` | 1.4 |
| AC3: enum limited by sign | `test_flow.py::test_enum_by_sign`, `::test_mixed_sign_split` | 1.2 |
| AC4 (amended): named group → full name (`woning` → `test woonstichting`); empty name + `abonr.4163` → `zoekterm ongeldig`; empty name + valid `maandhuur` → `maandhuur` | `test_rules.py::test_naam_always_wins`, `::test_naam_with_digits_allowed`, `::test_nameless_invalid_model_term`, `::test_nameless_valid_model_term`, `::test_short_naam_uses_model_term`; `test_flow.py::test_generic_model_term_replaced_by_naam`, `::test_nameless_group_uses_valid_model_term` | 2.1 |
| AC5: `sleutel` = shared helper | `test_flow.py::test_sleutel_matches_helper` | 1.1 |
| AC6 (amended): group `Test Garage` vs `Test Garage Onderdelen` in `Auto` → `botsing: 1 transacties in Auto` | `test_flow.py::test_collision_flag`, `test_rules.py::test_collision_counts_other_categories_only` | 2.2 |
| AC7: rule `bakker` → `al gedekt door regel 'bakker'` | `test_flow.py::test_shadow_flag`, `test_rules.py::test_shadow_uses_first_rule_in_order` | 2.3 |
| AC8: no eGPU → exit 2, 0 requests | `test_gpu.py::test_no_egpu_exit_2_no_requests` | 3.1 |
| AC9: VRAM < 4 GiB after the first call → exit 3 | `test_gpu.py::test_card_vram_low_exit_3`, `::test_model_process_vram_low_exit_3` (+ `::test_model_process_not_found_exit_3`, `::test_fdinfo_unreadable_exit_3`) | 3.2 |
| AC10: DB SHA-256 unchanged, `mode=ro` | `test_io.py::test_db_hash_unchanged`, `::test_connection_is_readonly`, `::test_out_equal_to_db_refused`, `::test_out_via_symlink_to_db_refused`, `::test_out_must_be_csv`, `::test_tmp_symlink_to_db_cannot_overwrite` | 4.1 |
| AC11: CSV header exact, `akkoord` empty | `test_io.py::test_header_and_empty_akkoord` | 4.2 |
| AC12: 4 failures → abort + partial file | `test_flow.py::test_abort_after_four_failures_writes_partial` | 1.5 |
| AC13: **withdrawn by the PO** (amendment 2: local model, full transaction in the prompt) | `test_flow.py::test_full_description_reaches_prompt` (the description arrives unchanged) | — |
| AC14: `manual:` real GPU run on synthetic data | manual: needs the physical eGPU and the live model; not reproducible in CI | **5.1–5.4** |
| AC15: `manual:` Joost's real run | manual: real data, Joost only | — (sign-off) |
| FR input = only `Ongecategoriseerd` (NULL excluded) | `test_flow.py::test_null_category_not_grouped` | — |
| Review file private (bank data) | `test_io.py::test_review_file_is_private` (mode 0600) | 4.2 |
| Out-of-scope: network only to the local endpoint | `test_llm.py::test_ignores_proxy_env`, `::test_redirect_refused`, `test_io.py::test_non_loopback_endpoint_refused` | 4.3 |

Mutation check done during the build: removing the proxy block, the IBAN scrub, or the per-process VRAM check each turns its test red.

---

## Functions to test

### 1. Grouping and the model call flow
**Location:** `tools/ai_suggest/__main__.py` (`build_groups`, `main`), `tools/ai_common/grouping.py`

| # | Test case | Input / action | Expected result | Priority |
|---|---|---|---|---|
| 1.1 | Happy path | synthetic DB: 3× `Test Streaming B.V.` −9,99, 2× `Test Bakker` −4,50; stub LLM | 2 calls; CSV rows 3 then 2; `sleutel` `test streaming b.v.` / `test bakker`; `totaal_bedrag` `-29,97` | High |
| 1.2 | Sign split | the same counterparty with +10 and −10 | 2 rows (`inkomsten`, `uitgaven`), 2 calls, each enum only its own type | High |
| 1.3 | Nameless group | a transaction with empty `naam` and a description | stdout shows `(geen naam)`, **never** the description; CSV `naam` empty, `sleutel` = description key | High |
| 1.4 | Model garbage | the stub returns an invented category / non-JSON / missing keys / an HTTP 500 | `model-fout`, empty category; the run continues | High |
| 1.5 | Abort | 6 groups, the stub always fails | exit 1, `afgebroken na 4 opeenvolgende modelfouten`, a CSV with 4 rows | Normal |
| 1.6 | Multiple users | a DB with 2 users, no `--gebruiker` | exit 1 listing the users, 0 requests; with `--gebruiker 2` it works | Normal |

### 2. Rule safety
**Location:** `tools/ai_suggest/rules.py`, `prompt.py`

| # | Test case | Input / action | Expected result | Priority |
|---|---|---|---|---|
| 2.1 | Zoekterm (amended) | named group (≥ 4 chars), model proposes anything | zoekterm = full lowercased name; for a nameless or < 4-char-name group, the model term only if it's valid (≥ 4, no digits, in every text), else empty + `zoekterm ongeldig` | High |
| 2.2 | Collision | the proposed term also matches transactions in another category | `botsing: N transacties in <cats>`; `Ongecategoriseerd` and NULL don't count | High |
| 2.3 | Shadow | an existing active rule already matches the group | `al gedekt door regel '<term>'` (the first rule in Categorizer order) | Normal |
| 2.4 | Full transaction in prompt (PO amendment 2) | a description with an IBAN, invoice number and long text | arrives unchanged in the prompt (whitespace collapsed, ≤ 1000 chars); **never** on stdout | Normal |

### 3. GPU guard
**Location:** `tools/ai_suggest/gpu.py`

| # | Test case | Input / action | Expected result | Priority |
|---|---|---|---|---|
| 3.1 | No eGPU | fake sysfs without a ≥ 8 GiB card | exit 2, `eGPU niet aangesloten`, 0 requests, no CSV | High |
| 3.2 | Model not on the eGPU | card full from another process, model process 0 GiB | exit 3 with the resident GiB | High |
| 3.3 | Spill | model 6 of 13 GiB resident, another process at 9 GiB | warning twice (progress + summary), naming the other holder; exit 0 | Normal |

### 4. I/O boundaries
| # | Test case | Input / action | Expected result | Priority |
|---|---|---|---|---|
| 4.1 | Read-only | any run | DB SHA-256 unchanged; a write via the tool's connection raises | High |
| 4.2 | CSV | open the CSV | BOM, `;`, header exactly as in the brief, decimal commas, `akkoord` empty, no `.tmp` left | Normal |
| 4.3 | Network | `--endpoint http://example.com`, `http://127.0.0.1@evil.com:6767`, `https://127.0.0.1`; proxy env vars set to a dead port | refused before the DB is opened; proxy ignored; redirects refused | High |

### 5. Real GPU run (AC14, manual, this laptop)
Build a **synthetic** DB in a temp dir (reuse `SyntheticDB` from the conftest, or the same inserts): ~8 counterparties with realistic **fake** Dutch names and descriptions (e.g. `Test Supermarkt B.V.` "Pinbetaling boodschappen", `Test Energie N.V.` "Termijnbedrag stroom en gas", `Test Werkgever B.V.` "Salaris september", `Test Streaming` "Maandabonnement"), some already categorised for the few-shot. Then:
```
AI_SUGGEST_API_KEY=<given> .venv/bin/python -m tools.ai_suggest --db <tmp>/data/database.db --out <tmp>/review.csv
```

| # | Check | Expected | Priority |
|---|---|---|---|
| 5.1 | GPU line | `eGPU card0: … model (pid N) X GiB resident` with X ≥ 4; if the Jan desktop app holds a model, the spill warning names it. Report the actual numbers | High |
| 5.2 | Proposals | plausible Dutch categories from the synthetic DB's category list; zoektermen valid (naam-like, no digits) | High |
| 5.3 | Speed | per-group seconds in the progress lines; report them (cold first call vs warm) | Normal |
| 5.4 | CSV opens as intended | `;` columns, decimal commas (inspect the text; no LibreOffice needed) | Normal |

---

## High-stakes output checks

| Output | Input values | Expected result | Logic reference |
|---|---|---|---|
| `sleutel` | naam `Test Streaming B.V.` | `test streaming b.v.` | `group_key` |
| `sleutel` (nameless) | naam `""`, omschrijving `Iets Anders` | `iets anders` | `group_key` |
| `type` | bedrag `-0.01` / `0` / `0.01` | uitgaven / uitgaven / inkomsten | `sign_type` (> 0) |
| `zoekterm` | model `woning`, naam `Test Woonstichting` | `test woonstichting` | `choose_zoekterm` (name first) |
| `zoekterm` | model `abonr.4163`, naam empty | `""` + `zoekterm ongeldig` | `choose_zoekterm` |
| collision | group `Test Garage`, `Test Garage Onderdelen` in `Auto` | `botsing: 1 transacties in Auto` | `collision_flag` |

---

## Regression scope

- [ ] SaldoBoek itself is untouched (`git diff dev...HEAD -- saldoboek` must be empty).
- [ ] The existing suite (`tests/test_smoke.py`) still passes.

---

## Notes for tester

- No browser UI: everything is CLI and Python. The offline cases (1–4) are best driven through the same fixtures as `tests/ai_suggest/conftest.py` (`SyntheticDB`, `StubLLM`, `FakeHost`).
- `DatabaseManager` (used only to *build* synthetic DBs) prints `[DEBUG]` lines and seeds ~140 global rules. Delete them in your synthetic DB, or short rules like `da`/`ns` will shadow everything.
- The real-GPU run loads Qwen3-14B (~12.7 GiB). The first call can take 30–60 s (cold load).
- Known, out of scope: applying proposals (that's item 0003); the E-1 duplicate issue in SaldoBoek's importer.
