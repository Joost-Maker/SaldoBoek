# Spec review: 0002-ai-suggest (spec rev 1)

**Gate:** spec mode · **Reviewed:** `00-brief.md`, `01-spec.md` rev 1, `CLAUDE.md`, `saldoboek/core/database.py`, `saldoboek/core/categorization.py`, `saldoboek/config/categorization_rules.yaml`, `pyproject.toml`, `tests/test_smoke.py` · **Date:** 2026-09-18

## Verified claims

- `DatabaseManager.__init__` writes on open: mkdir, CREATE TABLE, migrations, seed `INSERT OR IGNORE`, CREATE INDEX (`database.py:23-25`, `:79-151`, `:181-198`). The spec is right not to use it in the tool, and right to use it in tests only.
- Rule order in `Categorizer._load_rules` (`categorization.py:12-37`): global active rules first, in SQL natural order (no ORDER BY), then user rules. A user rule that has the same lowercased term overwrites the value but keeps the global's position in the dict. It's first match on `f"{naam} {omschrijving}".lower()` (`:39-47`). Spec Decision 5 describes this correctly. Keep the two queries without ORDER BY so that the order really matches.
- Sign rule `bedrag > 0` → inkomsten matches `categorization.py:286-293`. Categories are the user's own rows (`database.py:236-245`).
- `tools/` doesn't exist yet. No pytest config: `python -m pytest` from the repo root puts the cwd on `sys.path`, so `tools.ai_suggest` will import in tests.

## Coverage

All 11 functional requirements and all 15 acceptance criteria are mapped (`01-spec.md:73-103`). The **one** gap is a load-bearing Out-of-scope line that has no mechanism and no test. See R1.

## Decisions beyond the brief (judged against the Ambiguity guidance)

- **Decision 1, per-process VRAM check (`01-spec.md:48`, `:120`): accepted.** The GPU-guard design isn't on the delegated list. The only must-park line is *"a GPU-guard design that would allow a silent CPU/iGPU fallback"*. The probe (`:21`) shows that the brief's own card-level check, built literally, crosses that line on this machine: with Jan desktop holding about 9 GiB, `mem_info_vram_used ≥ 4 GiB` passes even if Qwen isn't on the eGPU at all. The extra check only adds abort paths, never a fallback path. It keeps the brief's exit code and message, and it's logged and reversible. It resolves the conflict in the conservative direction, so it's neither creep nor a park. The cost is a new false-abort mode that depends on llama-server router argv internals (`--alias`, the parent's `--port`) and on `fdinfo` being readable. That's loud, not silent, and the manual AC14 on the real eGPU exercises it. See N1.
- **Decision 2, spill warning, not an abort (`:49`, `:121`): accepted.** It's diagnostic output that extends the brief's "eGPU VRAM reading" report. It isn't silent, so it stays clear of the must-park line. The brief's hard line (< 4 GiB → exit 3) is kept, and the output contains no transaction data (pid, alias, GiB). Turning it into an abort would add a hard stop the brief didn't ask for, so a warning is the right conservative choice. See N2.
- Decisions 3 to 5 (`zekerheid` normalisation, exit 1 on abort, SQL-mirrored rules): within delegated latitude.
- **Not logged:** the post-check runs "after the first *successful* model response" (`:46`), but the brief says "after the first model response" (`00-brief.md:41`). This is harmless: no proposal ever reaches the CSV without passing the check. It still belongs in the Decisions table. See N3.

## Findings

### Required (changes requested)

- **R1: Network confinement isn't specified, and stdlib `urllib` leaks by default.** Brief Out-of-scope `00-brief.md:51` (*"Network traffic anywhere except the configured endpoint on 127.0.0.1"*) and the mission (*"bank data never leaves the machine"*). `llm.py` (`01-spec.md:35`) uses the default `urllib.request` opener, and that opener:
  - **honours `http_proxy`/`https_proxy` even for 127.0.0.1**, unless `no_proxy` happens to cover it. I checked this: with `http_proxy` set, `urllib.request.proxy_bypass('127.0.0.1')` returns `False`. So one exported proxy variable would send every prompt, with names, descriptions and few-shot rows, to the proxy host;
  - follows 3xx redirects to any host;
  - accepts any `--endpoint` host, including non-loopback ones.

  **Change:** add these three items to the spec:
  1. `LLMClient` builds its opener with `ProxyHandler({})` and a handler that refuses redirects.
  2. `--endpoint` is parsed at startup: the host must be `127.0.0.1`, `::1` or `localhost`. If it isn't, exit non-zero with a clear message before any request, and before the DB is read.
  3. Tests: `test_llm.py::test_ignores_proxy_env`, which sets `http_proxy` to a dead port and checks that the request still reaches the stub, and `test_cli.py::test_non_loopback_endpoint_refused`, which checks the exit code and that the stub received 0 requests.

  This enforces the brief rather than extending it.

### Notes (for the builder, no revision needed)

- **N1:** When the model process isn't found, or its `fdinfo` can't be read (EACCES, or no `drm-memory-vram` key), use an exit-3 message that is distinct from "resident < 4 GiB". Joost should see *why* the guard tripped, for example `model draait niet op de eGPU: modelproces niet gevonden onder --port 6767`. Test both variants with the fake proc tree.
- **N2:** Repeat the spill warning in the final summary, so that it isn't lost in the per-group progress output.
- **N3:** Log "first *successful* response" as a Decision, with the brief's literal reading as the alternative.
- **N4, seed-rule interference in fixtures:** `DatabaseManager` seeds about 140 global rules, including 2- and 3-character terms (`ww`, `ns`, `ret`, `bp`, `da` at `categorization_rules.yaml:42,56,64,67,75`). Globals come first in first-match order. A synthetic `omschrijving` such as "maandabonnement" contains `da`, so the shadow check reports `al gedekt door regel 'da'` and AC7's exact `'bakker'` expectation fails. Either delete or deactivate the seeded global rules in the tmp-DB builder, or check the fixture texts against the seed list. Also make sure every stdout-content test captures only the tool's output: `DatabaseManager` prints `[DEBUG]` lines (`database.py:25`, `:198`).
- **N5, `categorie IS NULL`:** SaldoBoek can set it (`database.py:577-586`). The brief selects only `'Ongecategoriseerd'`, so keep that. In the collision check, though, treat NULL as uncategorised rather than as a colliding category, and log the choice.
- **N6, CSV numbers:** Dutch-locale LibreOffice won't read `-29.97` or `0.95` as numbers. Decide on the decimal separator for `totaal_bedrag` and `zekerheid`, preferably a decimal comma, and log it. Delegated, but visible to Joost.
- **N7, stdout:** The brief asks for "time per call" as progress. Print per-call seconds in the per-group progress line, not only the mean in the summary.
- **N8, IBAN scrub:** `scrub()` catches the AC13 compact pattern only. Also catch spaced and lowercase forms (`NL00 KNAB 0000 0000 00`), which is the conservative choice for "no IBANs in the prompt".
- **N9:** Build the read-only URI with `Path(db).resolve().as_uri() + "?mode=ro"`, so paths that contain `?`, `#`, `%` or spaces still open correctly.
- **N10:** Clamp `zekerheid` outside 0..100, or treat it as `model-fout`, and pick one explicitly. The first call may include model load time under `--models-max 1`. Make sure the 120 s timeout covers a cold load of Qwen3-14B.

## Architecture / testability

- CLAUDE.md rules hold: fork-only code under `tools/`, no `saldoboek/` changes, no GUI imports, Python 3.8, config as flags and constants, no real data. The high-stakes output (the review CSV that feeds 0003) is declared at `01-spec.md:107-109`.
- The test scope catches each AC failing, provided N4 is handled. It's fully offline with injected sysfs and proc roots.
- Open questions for PO: none.

Verdict: changes requested
