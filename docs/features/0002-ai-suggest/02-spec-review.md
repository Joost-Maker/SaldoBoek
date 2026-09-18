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

*Rev 1 outcome: changes requested (R1). The verdict line was moved to the end of the file, after the re-review below.*

---

## Re-review (spec rev 2)

**Gate:** spec mode, re-review · **Reviewed:** `00-brief.md`, `01-spec.md` rev 2 (from commit `f29c865`; judged on the file, not the commit messages), `CLAUDE.md`, `saldoboek/core/database.py`, `saldoboek/core/categorization.py`, `saldoboek/config/categories.yaml`, and the layout of this machine's `/sys/class/drm` (listing only) · **Date:** 2026-09-18

### R1 (network confinement): resolved

- **Mechanism** (`01-spec.md:35`): `build_opener(ProxyHandler({}), NoRedirect())`, loopback-only `check_endpoint` with only the `http` scheme allowed, and 3xx → `LLMError`. **I verified this with the stdlib:** with `http_proxy`/`HTTP_PROXY`/`all_proxy` pointing at a dead port, the default opener fails (connection refused, so it did go through the proxy). The confined opener reaches a local server directly, and a subclass whose `redirect_request` raises turns a 302 into a `URLError`. `build_opener` drops its default `ProxyHandler` and `HTTPRedirectHandler` because instances of subclasses were passed in, so no default handler slips back in.
- **Ordering** (`:53`): `check_endpoint` runs first, before the GPU pre-check and before the DB is opened. That matches R1 item 2.
- **Tests** (`:81`): `test_ignores_proxy_env` (all three proxy variables), `test_redirect_refused`, and `test_non_loopback_endpoint_refused` (exit ≠ 0, 0 requests, DB never opened). This is a superset of what R1 asked for.

### Earlier notes: folded in

N2 (`:49`), N3 → Decision 6 (`:125`), N4 seed-rule deletion (`:38`), N5 (`:60`), N6 decimal comma (`:37`), N7 (`:60`), N8 (`:34`), N9 (`:32`; I checked that `as_uri()` gives `file:///tmp/a%20b%23c%3Fd%25e.db`), and N10 → Decisions 7 and 8 (`:126-127`) are all addressed. N1's distinct messages are in (`:48`). Two parts of the earlier notes aren't explicit in the spec and are repeated below as N11 and N12.

### Full pass against the brief

- **Coverage:** all 11 FRs, the network Out-of-scope line and all 15 ACs are mapped (`:74-104`), each with a named test or a manual route.
- **Creep:** none. The new behaviour is the proxy-free opener, the loopback check, the `zekerheid ongeldig` flag, the 300 s timeout and the decimal comma. Each of these either enforces the brief's Out-of-scope or mission, or falls under a delegated item (flag strings, timeout values). `--proc-root` is test plumbing for the Decision 1 check that the earlier review accepted. Nothing writes to the DB, and no dependency is added.
- **Open questions for PO:** none (`:141`).
- **Architecture:** CLAUDE.md rules hold. The code is fork-only under `tools/`, nothing changes in `saldoboek/`, the syntax is Python 3.8, tests import no GUI, and all data is synthetic. The rule-loading mirror still matches `categorization.py:12-37`. `categories.yaml` has only `inkomsten`/`uitgaven` sections, so the sign filter on `categorieen.type` is sound. The DB isn't WAL (no journal pragma in `database.py`), so opening it with `mode=ro` leaves no side files and the SHA-256 in AC10 is stable.
- **Testability:** each AC has a test that would fail if the criterion broke. Tests run offline with injected sysfs and proc roots and a stub server.

### Notes for the builder (no revision needed)

- **N11 (carried over from N4): stdout tests must capture only the tool's output.** The conftest builds the DB through `DatabaseManager`, which prints `[DEBUG] Gebruikte database: …` (`database.py:26`, `:202`) and `Gebruiker '…' actief…` (`:396`). Build the DB before `capsys`/`capfd` starts capturing, or clear the captured output first. Otherwise `test_stdout_has_no_descriptions` checks the wrong text. Also note that each new `DatabaseManager(...)` re-seeds the global rules (`database.py:141-147`), so build the DB once and delete the seeded rules afterwards.
- **N12 (carried over from N1):** the requirement mapping (`:98`) names only the two "VRAM low" exit-3 tests. Also cover the `model-proces niet gevonden` and `fdinfo onleesbaar` messages in `test_gpu.py` using the fake proc tree.
- **N13, stdout for groups with no `naam`:** when `naam` is empty, the group key is the `omschrijving` (brief FR grouping). The progress line `[i/n] <naam> …` (`:60`) and the summary must then **not** fall back to the key. Print a placeholder such as `(geen naam) #<groep>` instead, or the description reaches stdout, which the brief forbids ("no transaction contents on stdout beyond the counterparty name and totals"). Add an empty-`naam` group to `test_stdout_has_no_descriptions`. The CSV `sleutel`/`voorbeeld_omschrijving` columns are allowed per the brief.
- **N14, `check_endpoint` parsing:** compare `urllib.parse.urlsplit(url).hostname` exactly, not a string prefix. `http://127.0.0.1@evil.com:6767` has hostname `evil.com`, and `http://127.0.0.1.evil.com` must fail. Also pin down the port used by the per-process `--port` match when the URL has none (`urlsplit` gives `None`): either require an explicit port, or use 80 and log that choice.
- **N15, eGPU discovery:** `/sys/class/drm/card*` also matches connector entries (`card0-DP-5`, `card1-eDP-1`, …, seen on this machine). Their `device` link points at `../../card0`, not at the PCI device. They have no `mem_info_vram_total`, so the scan is harmless. Still, glob `card[0-9]*` without a `-`, or skip those entries explicitly, so that `basename(realpath(device))` is always a PCI address. Build the fake sysfs in the tests with at least one connector entry so this path is covered.
- **N16, enum hygiene:** remove `Ongecategoriseerd` from the allowed enum if a user happens to have a category row with that name (it isn't in `categories.yaml`, but the GUI can create categories). A proposal of "Ongecategoriseerd" is not a proposal. Also take the few-shot rows only from transactions whose `categorie` is neither NULL nor `Ongecategoriseerd`.
- **N17, cosmetic:** the Decisions list is numbered 1, 2, 3, 4, 6, 7, 8, 5 (`:120-128`). GPU-guard step 2b (`:48`) lists the messages before the procedure and repeats "not found → exit 3". Tidy both when writing the implementation log, so that the code gate can cite decisions by number without confusion.

Verdict: approved with notes
