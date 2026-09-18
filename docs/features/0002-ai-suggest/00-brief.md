---
vault_item: "DEV/SaldoBoek AI suggest - GPU category and rule proposals.md"
date: 2026-09-18
priority: Medium
---
# Feature Brief — AI suggest: GPU category + rule proposals for SaldoBoek

**Date:** 2026-09-18
**Author:** Joost (PO)
**Priority:** Medium
**Scope:** One-night (buildable + verifiable in a single pipeline run)
**Repo:** fork `Joost-Maker/SaldoBoek`, working branch `dev`, **fork-only** (`tools/ai_suggest/`, never upstream)

---

## What and why

Transactions that SaldoBoek's keyword rules don't recognise sit in `Ongecategoriseerd`. A local model on the RX 9060 XT reads them and proposes, per counterparty, **a category and a new zoekterm (rule)**. The output is a review CSV Joost checks in LibreOffice. This item is **read-only** towards SaldoBoek's database. Writing approved rules is the follow-up item [[SaldoBoek AI apply - reviewed rules into SaldoBoek]].

Running on the GPU is the point of the project (Joost). Privacy is the other reason: bank data never leaves the laptop, and no agent (Claude) reads the real data.

---

## User story

As Joost, I want to run one command after importing my Knab export, so that I get a review file with a proposed category and a safe rule for each group of uncategorised transactions, computed on my own GPU, and can approve them in LibreOffice.

---

## Functional requirements

- [ ] Command: `.venv/bin/python -m tools.ai_suggest --db <path> [--gebruiker <id>] [--out <csv>] [--model Qwen3-14B-Q4_K_M] [--endpoint http://127.0.0.1:6767] [--api-key-env AI_SUGGEST_API_KEY]`. Defaults: `--db saldoboek/data/database.db`, model `Qwen3-14B-Q4_K_M`, endpoint `http://127.0.0.1:6767`, API key from env var (Joost's server uses a fixed key; it's never hardcoded in the repo). `--gebruiker` may be omitted only if the database has exactly one user; otherwise it exits with a list of users.
- [ ] **Read-only:** the database is opened with SQLite URI `mode=ro`. The tool never writes to it.
- [ ] Input: all `transacties` of that user with `categorie = 'Ongecategoriseerd'`. **Grouped by counterparty** (lowercased, stripped `naam`; if `naam` is empty, `omschrijving`), with **one model call per group**, not per transaction.
- [ ] Allowed categories = that user's rows in `categorieen`, filtered by the sign of the group: `bedrag > 0` → `inkomsten`, else `uitgaven` (SaldoBoek's own rule). A group with mixed signs is split into two groups.
- [ ] Model call: OpenAI-compatible `POST /v1/chat/completions` via the Python stdlib (`urllib`, no new dependencies). **Constrained output** via `response_format` JSON schema: `{categorie: enum(allowed), zoekterm: string, zekerheid: number 0..1}`. Qwen3 thinking off (`chat_template_kwargs: {enable_thinking: false}`). Temperature 0.
- [ ] Prompt: Dutch system prompt plus **few-shot examples** taken from that user's already-categorised transactions (up to 15, one per distinct `naam`, most recent first). The group's `naam`, up to 3 sample `omschrijving`s, the count and the sign go in the user message. **No IBANs** in the prompt (not needed).
- [ ] **Zoekterm validation** (deterministic, in code, after the model): lowercase; ≥ 4 characters; **no digits**; must be a substring of `f"{naam} {omschrijving}".lower()` of **every** transaction in the group. If the model's term fails, fall back to the lowercased `naam` if that passes; otherwise leave the zoekterm empty and flag `zoekterm ongeldig`.
- [ ] **Collision check** (deterministic): run each proposed zoekterm over **all** of the user's transactions. Any match whose `categorie` is neither `Ongecategoriseerd` nor the proposed category → flag `botsing: N transacties in <categorieën>`.
- [ ] **Shadow check:** if an existing active rule (global or user) already matches the group's text → flag `al gedekt door regel '<zoekterm>'` (the group only needs a hercategorisatie in SaldoBoek, not a new rule).
- [ ] **GPU guard, before any model call:** the eGPU must be present (an amdgpu card in `/sys/class/drm/card*/device` with `mem_info_vram_total` ≥ 8 GiB). Otherwise exit code 2 with `eGPU niet aangesloten — geen CPU/iGPU-fallback`, and no model call. **After the first model response:** that card's `mem_info_vram_used` must be ≥ 4 GiB, otherwise abort (exit 3, `model draait niet op de eGPU`). The sysfs root is configurable (`--sysfs-root`, default `/sys/class/drm`) for tests.
- [ ] **Review CSV:** `;`-separated, `utf-8-sig` (so LibreOffice with a Dutch locale opens it correctly). One row per group, columns: `groep`, `sleutel`, `naam`, `voorbeeld_omschrijving`, `aantal`, `totaal_bedrag`, `type`, `categorie`, `zoekterm`, `zekerheid`, `vlaggen`, `akkoord`, `opmerking`. `sleutel` is the group key (lowercased, stripped `naam`, or `omschrijving` if `naam` is empty). It comes from **one shared helper**, because [[SaldoBoek AI apply - reviewed rules into SaldoBoek]] uses it to find the group's transactions again. `akkoord` is empty (Joost fills in `j`/`n`). Sorted by `aantal` descending. Default path: next to the database, as `ai_review_<YYYYmmdd-HHMMSS>.csv`. Written atomically (temp file + rename).
- [ ] Progress and summary on stdout: groups, model calls, time per call, number of flags, and the eGPU VRAM reading. **No transaction contents on stdout** beyond the counterparty name and totals.
- [ ] A model call failing (timeout, HTTP error, invalid JSON) marks that group `model-fout` and the run continues. More than 3 consecutive failures → abort with a clear message; a partial review file is still written.

## Out of scope (load-bearing — the pipeline may not cross this line)

- **Any write to `database.db`**: no rules, categories or transactions. That's the apply item.
- Creating new categories: the model picks only from `categorieen`.
- Starting or stopping `llama-server` or loading or unloading models: the tool only calls the running endpoint (the router loads the model on demand).
- Network traffic anywhere except the configured endpoint on `127.0.0.1`.
- Changes to SaldoBoek itself (`saldoboek/`), the GUI, or the Knab parser.
- Running automatically after an import.
- **Reading Joost's real bank data or real `database.db`.** Synthetic databases only.

---

## Acceptance criteria

All tests use a **synthetic** SaldoBoek database built with `DatabaseManager(db_path=tmp_path/...)` (fake IBANs and names), a **fake LLM endpoint** (a local stub HTTP server in the test) and a **fake sysfs tree** in `tmp_path`.

- [ ] Given a synthetic DB with 5 `Ongecategoriseerd` transactions from 2 counterparties (3× `Test Streaming B.V.` −9,99, 2× `Test Bakker` −4,50) and a stub endpoint, when the tool runs, then it makes exactly **2** model calls and writes a review CSV with 2 rows, `aantal` 3 and 2, in that order.
- [ ] Given the stub returns a category that isn't in `categorieen` (or free text instead of JSON), when the tool runs, then that group is flagged `model-fout` and no invented category appears in the CSV.
- [ ] Given a group of negative transactions, when the request is sent, then the schema's `categorie` enum contains only `uitgaven` categories. For a positive group, only `inkomsten`.
- [ ] Given the stub proposes the zoekterm `abonr.4163` (digits), when validated, then it's replaced by the lowercased `naam` (`test streaming b.v.`); if that fails too, the zoekterm is empty and flagged `zoekterm ongeldig`.
- [ ] Given the CSV, then each row's `sleutel` equals the shared group-key helper applied to that group's transactions (`test streaming b.v.`, `test bakker`).
- [ ] Given the stub proposes `test` for `Test Bakker` while the DB has `Test Garage` transactions already in `Auto`, when checked, then the row is flagged `botsing` with the count (1+) and `Auto`.
- [ ] Given an existing active rule `bakker` → `Boodschappen`, when the `Test Bakker` group is processed, then the row is flagged `al gedekt door regel 'bakker'`.
- [ ] Given a fake sysfs with no ≥ 8 GiB amdgpu card, when the tool runs, then it exits with code 2, prints `eGPU niet aangesloten`, and the stub endpoint received **0** requests.
- [ ] Given a fake sysfs whose eGPU `mem_info_vram_used` stays < 4 GiB after the first call, when the tool runs, then it exits with code 3 (`model draait niet op de eGPU`).
- [ ] Given any run, when it finishes, then the synthetic `database.db`'s SHA-256 is **unchanged** and the DB was opened `mode=ro` (a write attempt through the tool's connection raises).
- [ ] Given the CSV output, when read back with `csv` (`;`, `utf-8-sig`), then the header matches the specified columns exactly and `akkoord` is empty on every row.
- [ ] Given the stub fails 4 times in a row, when the tool runs, then it aborts with a clear message and still writes the review file for the groups done so far.
- [ ] Given the request body sent to the stub, then it contains no string matching an IBAN pattern (`[A-Z]{2}\d{2}[A-Z]{4}\d{10}`).
- [ ] `manual:` **real GPU run on synthetic data.** The bug hunter (or Joost) runs the tool against a synthetic DB with the real endpoint and model on this laptop. The eGPU VRAM visibly rises (reported by the tool), and the proposals are plausible Dutch categories. Needs the physical eGPU.
- [ ] `manual:` **Joost's real run.** Only Joost runs it on his real `database.db` and judges the review file. No agent sees that output.

---

## Ambiguity guidance

- **Delegated (decide conservatively + log):** prompt wording, few-shot selection details, the internal module layout under `tools/ai_suggest/`, CSV row order ties, timeout values, how the stub server is built in tests, the exact flag strings (as long as the ones named above appear as specified).
- **Must park:** anything that writes to the database; any new third-party dependency; network targets other than the configured local endpoint; a GPU-guard design that would allow a silent CPU/iGPU fallback; anything needing real bank data.

---

## Known constraints or dependencies

- Local LLM server: llama-server router on `127.0.0.1:6767` (systemd, preset `~/.config/jan-claudian/router.preset.ini`), `--models-max 1`, and **every model preset pinned to `device = Vulkan1` = RX 9060 XT**. `Vulkan0` is the Intel iGPU, a known trap. Model id `Qwen3-14B-Q4_K_M`, ctx 16384, ~12.7 GiB VRAM when loaded. Fixed API key, passed via env var.
- eGPU = the amdgpu card with ~16 GiB `mem_info_vram_total` (currently `card0`, but don't hardcode the index).
- SaldoBoek schema: see `CLAUDE.md` and `saldoboek/core/database.py`. Rule semantics are in `saldoboek/core/categorization.py` (lowercased substring over `f"{naam} {omschrijving}"`, first match wins, global rules first, then user rules).
- Python ≥ 3.8, stdlib + pandas only. Tests don't import `saldoboek.gui`.
- The fork is **public**: no real names, IBANs or amounts anywhere in code, tests, fixtures or docs.

## Notes for Programmer

- `llama-server` supports `response_format: {type: "json_schema", json_schema: {schema: …}}` → a GBNF grammar, so an enum on `categorie` really constrains the output.
- A self-reported `zekerheid` is a hint, not a calibrated probability. It's shown to Joost, not used for gating.
- Keep the LLM client behind a small interface (`suggest(prompt, schema) -> dict`), so the tests inject the stub endpoint URL and nothing else changes.

---

## PO amendment — zoekterm = full counterparty name (Joost, 2026-09-18, during fix round 1)

The real GPU run (AC14) showed the model proposing generic zoektermen (`woning`, `salaris`, `de hoek`). As permanent rules those would over-match future transactions. Decision: **when the group has a counterparty name, the zoekterm is always that full name** (lowercased, stripped). The model only picks the category.

- Replaces the zoekterm FR: if `naam` is non-empty and ≥ 4 characters, zoekterm = lowercased stripped `naam` (digits allowed here, because Knab writes the same name every time). Otherwise (empty or too-short `naam`), the model's zoekterm is used, with the original validation (≥ 4, no digits, substring of every group text); if it fails, it's empty and flagged `zoekterm ongeldig`.
- AC4 becomes: given naam `Test Woonstichting` and a model zoekterm `woning`, the zoekterm is `test woonstichting`. Given an **empty** naam and a model zoekterm `abonr.4163`, the zoekterm is empty and flagged `zoekterm ongeldig`. Given an empty naam and a valid model zoekterm `maandhuur` (in every text), the zoekterm is `maandhuur`.
- AC6 becomes: given an uncategorised group `Test Garage` while `Test Garage Onderdelen` is already `Auto`, and the model proposes `Boodschappen`, the row is flagged `botsing: 1 transacties in Auto` (the name-derived zoekterm `test garage` also matches the other one).
