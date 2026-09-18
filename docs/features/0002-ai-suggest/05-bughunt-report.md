# Bug Hunt Report
**Date (UTC):** 2026-09-18T09:44:39Z
**Feature / scope:** AI suggest: GPU category + rule proposals (0002-ai-suggest)
**Test protocol:** docs/features/0002-ai-suggest/04-test-protocol.md
**App URL:** n/a — headless CLI `python -m tools.ai_suggest`
**Round:** 1

---

## Environment
- Driver: headless, `.venv/bin/python` (Python 3.12.3); no browser UI exists for this feature. Offline cases (sections 1–4) driven through the fixtures in `tests/ai_suggest/conftest.py` (`SyntheticDB`, `StubLLM`, `FakeHost`) from scratch scripts in a `mktemp -d` dir outside the repo. Section 5 was meant to run against the real llama-server router on `127.0.0.1:6767` and the real eGPU. The router was down, so it's **blocked, not run** (see the section 5 status).
- App version / last commit: `cc937e4` on `feat/0002-ai-suggest`
- Test data: synthetic only (fake names `Test …`, fake IBANs `NL00…`). No real bank data or real `database.db` opened.
- Baseline: `.venv/bin/python -m pytest -q` → `53 passed in 20.10s`. `git diff dev...HEAD -- saldoboek` → empty (regression scope OK).

---

## Test results

> **How the offline cases were run.** Scratch harness `h.py` in the temp dir (outside the repo) that imports `SyntheticDB`, `StubLLM`, `FakeHost`, `read_review` from `tests/ai_suggest/conftest.py` and calls `tools.ai_suggest.__main__.main([...])` with `--db <tmp>/data/database.db --out <tmp>/review.csv --endpoint <stub url> --sysfs-root <fake> --proc-root <fake>`, capturing stdout. Each case is a small script `cNN.py` run as `cd <tmp> && .venv/bin/python cNN.py`. "Console errors" = Python tracebacks/stderr; "Network errors" = what the stub (or a listener) saw.

### 1.1 Happy path (High)
- **Tested:** 3× `Test Streaming B.V.` "Maandabonnement" −9.99, 2× `Test Bakker` "Brood" −4.50; default stub.
- **Expected:** 2 calls; CSV rows 3 then 2; `sleutel` `test streaming b.v.` / `test bakker`; `totaal_bedrag` `-29,97`.
- **Actual:** exit 0, stub saw 2 requests. Rows: `groep 1, sleutel 'test streaming b.v.', aantal 3, totaal_bedrag '-29,97', type uitgaven` and `groep 2, sleutel 'test bakker', aantal 2, totaal_bedrag '-9,00'`. `sleutel` = `group_key(naam, omschrijving)`.
- **Severity:** ✅ pass
- **Console errors:** none · **Network errors:** none

### 1.2 Sign split (High)
- **Tested:** `Test Vriend` +10.00 "Terugbetaling etentje" and −10.00 "Etentje voorgeschoten".
- **Expected:** 2 rows (inkomsten, uitgaven), 2 calls, each enum only its own type.
- **Actual:** 2 calls. Request enums: `['Salaris']` (Type: inkomsten) and `['Abonnementen', 'Auto', 'Boodschappen']` (Type: uitgaven). CSV: 2 rows, both `sleutel 'test vriend'`, types inkomsten/uitgaven, totals `10,00` / `-10,00`. `Ongecategoriseerd` is correctly left out of the enum.
- **Severity:** ✅ pass (see exploratory E1: both rows got the same zoekterm `test vriend` with different categories, and nothing flags that)
- **Console errors:** none

### 1.3 Nameless group (High)
- **Tested:** naam `""` and naam `"   "` with omschrijving "Geheime Omschrijving Kosten Pakket" (−3.00 each); naam `NULL` with "Andere Geheime Tekst".
- **Expected:** stdout `(geen naam)`, never the description; CSV `naam` empty, `sleutel` = description key.
- **Actual:** stdout lines `[1/2] (geen naam) (2×) → Abonnementen` / `[2/2] (geen naam) (1×) → …`; `grep -i geheime|andere` on stdout: no match. CSV: `naam` empty, `sleutel` `geheime omschrijving kosten pakket` / `andere geheime tekst`, the empty and whitespace-only naam land in one group (aantal 2). The stub's term `(geen naam)` fails validation, the naam fallback is empty → `zoekterm ongeldig` (correct).
- **Severity:** ✅ pass
- **Console errors:** none

### 1.4 Model garbage (High)
- **Tested:** 7 groups, the stub answered in sequence: valid · `{"categorie":"Verzonnen Categorie",…}` · free text `Dit is gewoon vrije tekst, geen JSON` · `{"categorie":"Auto"}` (missing keys) · HTTP 500 · (second run) `categorie "Salaris"` for an uitgaven group · a JSON array `["Abonnementen"]` · `zekerheid: 1.5` · `zekerheid: "hoog"`.
- **Expected:** `model-fout`, empty category, run continues.
- **Actual:** every bad answer → row with empty `categorie`/`zoekterm` and `vlaggen 'model-fout'`; stdout gives the reason (`categorie buiten de toegestane lijst`, `antwoord is geen geldige JSON`, `zoekterm ontbreekt`, `HTTP 500`). The wrong-sign `Salaris` is also rejected. No invented category ever reaches the CSV. The run continues when a good answer breaks the run of failures. `zekerheid "hoog"` → `0,00` + `zekerheid ongeldig`. `zekerheid 1.5` → see finding F1.
- **Severity:** ✅ pass (one 🟢 side-finding, F1)
- **Console errors:** none

#### F1 — `zekerheid` 1.5 silently becomes 0,01 with no flag · 🟢 Low
- **Input:** stub returns `(200, {"categorie": "Auto", "zoekterm": "test ffff", "zekerheid": 1.5})`.
- **Command:** `cd <tmp> && .venv/bin/python c14b.py`
- **Observed:** CSV row `categorie 'Auto', zoekterm 'test ffff', zekerheid '0,01'`, `vlaggen` empty.
- **Expected:** 1.5 is outside the schema's 0..1 range: flag `zekerheid ongeldig` (as `"hoog"` gets), or at least clamp to 1. `normalize_zekerheid` reads every value in (1, 100] as a percentage, so 1.5 → 1.5 % → 0.015. llama.cpp's GBNF doesn't enforce `minimum`/`maximum` on numbers, so the model can produce this. It's only a hint to Joost, so Low.
- **Location:** `tools/ai_suggest/llm.py::normalize_zekerheid`

### 1.5 Abort (Normal)
- **Tested:** 6 groups, the stub always returns HTTP 500.
- **Expected:** exit 1, `afgebroken na 4 opeenvolgende modelfouten`, CSV with 4 rows.
- **Actual:** exactly that: 4 requests, the stdout line `afgebroken na 4 opeenvolgende modelfouten`, the summary `groepen: 6 (in bestand: 4)`, CSV 4 rows all `model-fout`, no `.tmp` left. (With no successful answer the GPU post-check never runs. That's fine because no proposal is produced.)
- **Severity:** ✅ pass

### 1.6 Multiple users (Normal)
- **Tested:** DB with users `Test Gebruiker` (1) and `Test Partner` (2), no `--gebruiker`; then `--gebruiker 2`; then `--gebruiker 99`.
- **Expected:** exit 1 listing the users, 0 requests; `--gebruiker 2` works.
- **Actual:** `Kies een gebruiker met --gebruiker: 1=Test Gebruiker, 2=Test Partner`, exit 1, 0 requests, no CSV. `--gebruiker 2` → only user 2's `Test Garage` row. `--gebruiker 99` → `SystemExit('Gebruiker 99 bestaat niet.')` (exit 1 on the CLI, message on stderr).
- **Severity:** ✅ pass

### 2.1 Bad zoekterm (High)
- **Tested (c21.py):** stub proposals per group: `abonr.4163` for `Test Streaming B.V.` (digits); `bak` for `Test Bakker` (< 4 chars); `kleding` for `Test Winkel` whose two texts are "Aankoop kleding" / "Aankoop schoenen" (not in every text); `ns 12` for naam `NS 12` (model and fallback both invalid); `"  TEST KAPPER  "` (padding/case).
- **Expected:** fallback to the lowercased naam when valid, else empty + `zoekterm ongeldig`.
- **Actual:** `test streaming b.v.`, `test bakker`, `test winkel` (fallbacks); `NS 12` → empty zoekterm + `zoekterm ongeldig`; `"  TEST KAPPER  "` → `test kapper`. High-stakes row `abonr.4163` → `test streaming b.v.` ✅.
- **Severity:** ✅ pass (over-matching terms that *do* pass validation: see exploratory E1)

### 2.2 Collision (High)
- **Tested (c22.py):** uncategorised `Test Bakker` ×2 (plus `Test Ander` in `Ongecategoriseerd`, `Test Null` with `categorie NULL`); categorised `Test Garage` ×2 in `Auto`, `Test Salarisbureau` in `Salaris`, `Test Zelfde` in `Boodschappen`. The stub proposes `test` → `Boodschappen` for every group.
- **Expected:** `botsing: N transacties in <cats>`; `Ongecategoriseerd` and NULL don't count.
- **Actual:** `botsing: 3 transacties in Auto, Salaris` (2 Auto + 1 Salaris). `Ongecategoriseerd`, NULL and the same-category `Boodschappen` row aren't counted. The high-stakes row (`test`, `Test Garage` in `Auto`) gives `botsing: 1 transacties in Auto` in the permanent test and the same logic here.
- **Severity:** ✅ pass

### 2.3 Shadow (Normal)
- **Tested (c23.py):** (a) global `bakker`→Boodschappen, user `brood`, user `test b`, an inactive global `akker`; (b) global `brood`→Auto, global `bakker`, then user `brood` overriding the global one.
- **Expected:** `al gedekt door regel '<term>'`, the first rule in Categorizer order.
- **Actual:** (a) `al gedekt door regel 'bakker'` (inactive `akker` ignored); (b) `al gedekt door regel 'brood'`: the user override keeps the global's position, the same dict-insertion semantics as `Categorizer._load_rules`.
- **Severity:** ✅ pass

### 2.4 IBAN scrub (High)
- **Tested (c24.py):** 14 groups whose omschrijving/naam holds an IBAN in different forms. The protocol forms (plain `NL00RABO0000000001`, lowercase `nl00rabo0000000001`, spaced `nl00 rabo 0000 0000 02`, spaced upper) plus extra real-world forms. Then every request body is grepped for the IBAN digits.
- **Expected:** no IBAN (in any of those forms) in any request body.
- **Actual:** the protocol's forms (plain, lowercase, single-spaced, BE) and `IBAN:`/`/IBAN/…/` are replaced by `[IBAN]` ✅. Six other forms reach the model: see F2.
- **Severity:** 🟡 (F2)

#### F2 — IBANs with double spaces, tabs, NBSP, dashes/dots or a glued prefix reach the model · 🟡 Medium
- **Input (omschrijving of an `Ongecategoriseerd` tx; one group each):**
  `"Overboeking NL00  RABO  0000  0000  04 huur"` (double spaces) · `"Overboeking NL00\tRABO\t0000\t0000\t05 huur"` (tabs) · `"Overboeking NL00 RABO 0000 0000 10 huur"` (NBSP) · `"Overboeking NL00-RABO-0000-0000-06 huur"` · `"Overboeking NL00.RABO.0000.0000.11 huur"` · `"Overboeking IBANNL00RABO0000000007 huur"`; and a **categorised** few-shot tx `"Van NL00  INGB  0000  0000  14"`.
- **Command:** `cd <tmp> && .venv/bin/python c24.py` (stub records the bodies; grep for `0000`)
- **Observed (verbatim from request bodies):**
  ```
  LEAK: 'n- Overboeking NL00 RABO 0000 0000 04 huur'
  LEAK: 'n- Overboeking NL00 RABO 0000 0000 05 huur'
  LEAK: 'n- Overboeking NL00 RABO 0000 0000 10 huur'
  LEAK: 'n- Overboeking NL00-RABO-0000-0000-06 huur'
  LEAK: 'n- Overboeking NL00.RABO.0000.0000.11 huur'
  LEAK: 'n- Overboeking IBANNL00RABO0000000007 huur'
  LEAK: 'n- Test Voorbeeld | Van NL00 INGB 0000 0000 14 | uitgaven → Boo'
  AC13 pattern hits: ['NL00RABO0000000007']
  ```
- **Why:** `prompt.scrub()` runs `IBAN_RE.sub` **before** it collapses whitespace (`" ".join(text.split())`). The regex allows only one optional space (` ?`) between blocks, so a double-spaced/tab/NBSP IBAN slips through and is then *normalised into exactly the single-spaced form the protocol bans*. Bank exports often pad fields with runs of spaces, so the whitespace case is the realistic one. The glued form `IBANNL00…` has no `\b` before `NL`, and it matches the literal AC13 regex. Dash/dot separators aren't handled at all.
- **Impact:** the traffic stays on loopback (the model is local), so nothing leaves the laptop. But the brief's "No IBANs in the prompt" and protocol 2.4 are violated for these inputs, and the fewshot path leaks the same way.
- **Suggested fix direction:** normalise whitespace (incl. NBSP) before the IBAN substitution, and accept `[ \-.]?` separators and a non-word-boundary start (e.g. `(?<![A-Z0-9])` or a lookbehind that tolerates a letter prefix).
- **Location:** `tools/ai_suggest/prompt.py::scrub` / `IBAN_RE`

### 3.1 No eGPU (High)
- **Tested (c3.py):** `FakeHost(egpu=False)` (only a 512 MiB iGPU + a `card0-DP-5` connector); plus a variant where the eGPU reports `mem_info_vram_total` = 6 GiB.
- **Expected:** exit 2, `eGPU niet aangesloten`, 0 requests, no CSV.
- **Actual:** both: exit 2, `eGPU niet aangesloten — geen CPU/iGPU-fallback`, stub requests 0, no CSV.
- **Severity:** ✅ pass

### 3.2 Model not on the eGPU (High)
- **Tested (c3.py):** card `mem_info_vram_used` 12 GiB held by another process (`/opt/jan/llama-server --alias Other-Model --port 7777`, 12 GiB fdinfo), the model process at 0 GiB; plus a variant with card used 2 GiB.
- **Expected:** exit 3 with the resident GiB.
- **Actual:** `model draait niet op de eGPU (0.0 GiB resident)`, exit 3, after exactly 1 request, no CSV. Variant: `model draait niet op de eGPU`, exit 3.
- **Severity:** ✅ pass

### 3.3 Spill (Normal)
- **Tested (c3.py):** model file 13 GiB (sparse), model process 6 GiB on the eGPU, `Jan-Model` (pid 300) 9 GiB, card used 15 GiB.
- **Expected:** warning twice (progress + summary) naming the other holder; exit 0.
- **Actual:** `WAARSCHUWING: model past niet volledig op de eGPU (6.0 van 13.0 GiB) — dit wordt traag. Andere VRAM-gebruikers: Jan-Model (pid 300, 9.0 GiB).` printed after the GPU line and again in the summary; exit 0.
- **Severity:** ✅ pass

### 4.1 Read-only (High)
- **Tested (c4.py):** SHA-256 of the synthetic DB and the directory listing before/after a full run; then `ReadOnlyDB(path).conn.execute(...)` with `INSERT`, `CREATE TABLE`, `PRAGMA user_version=5` + commit.
- **Expected:** SHA unchanged; a write via the tool's connection raises.
- **Actual:** SHA identical; the directory holds only `database.db` before and after (no `-journal`/`-wal`/`-shm` created); all three writes raise `sqlite3.OperationalError: attempt to write a readonly database`. (Out-of-band DB overwrite via `--out`: see exploratory E2.)
- **Severity:** ✅ pass

### 4.2 CSV (Normal)
- **Tested (c4.py):** raw bytes of the review file.
- **Expected:** BOM, `;`, header exactly as in the brief, decimal commas, `akkoord` empty, no `.tmp` left.
- **Actual:** starts with `EF BB BF`; header `groep;sleutel;naam;voorbeeld_omschrijving;aantal;totaal_bedrag;type;categorie;zoekterm;zekerheid;vlaggen;akkoord;opmerking` (= brief); rows like `1;test streaming b.v.;Test Streaming B.V.;Maandabonnement;3;-29,97;uitgaven;Abonnementen;test streaming b.v.;0,90;;;` and `…;2500,50;inkomsten;Salaris;…`; `akkoord` empty; no `.tmp`.
- **Severity:** ✅ pass

### 4.3 Network (High)
- **Tested (c43.py, c43b.py):** 16 `--endpoint` values combined with `--db /nonexistent/x.db` (so "refused before the DB is opened" shows as the endpoint error instead of `Database niet gevonden`); a full run with `http_proxy/HTTP_PROXY/https_proxy/ALL_PROXY/all_proxy` → `127.0.0.1:9`, `no_proxy=""`; the stub answering `307 Location: http://example.com/...`. The whole of c43b.py ran under `strace -f -e trace=connect`.
- **Expected:** refused before the DB is opened; proxy ignored; redirects refused.
- **Actual:** `http://example.com`, `http://127.0.0.1@evil.com:6767`, `https://127.0.0.1`, `http://evil.com@127.0.0.1:6767`, `http://127.0.0.1:6767@evil.com`, `http://[::ffff:127.0.0.1]:6767`, `http://127.1:6767`, `http://0.0.0.0:6767`, `http://localhost.evil.com`, `file:///etc/passwd`, `http://127.0.0.1\t@evil.com` → `endpoint moet lokaal zijn (127.0.0.1/::1/localhost)`, exit 1, before the DB check. `:99999` → `endpoint heeft een ongeldige poort`. `HTTP://LOCALHOST:6767`, `…:6767#@evil.com`, `…:6767/?@evil.com` pass the check (host really is loopback; the base URL is rebuilt from host:port, so the fragment/query are dropped). Proxy run: exit 0, both requests reached the stub. Redirect: `model-fout (redirect geweigerd (307))`. strace: the only IP connects were `127.0.0.1:<stub port>` (4×); no connect to port 9, no DNS, no non-loopback address (plus 2 failed `AF_UNIX /var/run/nscd/socket` NSS probes from libc).
- **Severity:** ✅ pass

### High-stakes output checks
| Output | Input | Observed | |
|---|---|---|---|
| `sleutel` | naam `Test Streaming B.V.` | `'test streaming b.v.'` | ✅ |
| `sleutel` (nameless) | naam `""`, omschrijving `Iets Anders` | `'iets anders'` | ✅ |
| `type` | −0.01 / 0 / 0.01 | `uitgaven` / `uitgaven` / `inkomsten` | ✅ |
| `zoekterm` | model `abonr.4163`, naam `Test Streaming B.V.` | `('test streaming b.v.', [])` | ✅ |
| collision | term `test`, `Test Garage` in `Auto` | `['botsing: 1 transacties in Auto']` | ✅ |

### 5. Real GPU run (AC14): precondition check, 09:49 UTC
- The protocol and the hunt brief say the router on `127.0.0.1:6767` is already running. **It isn't.** `ss -ltnp` shows no listener on 6767, `curl -m 3 http://127.0.0.1:6767/v1/models` → exit 7 (connection refused), and `systemctl --user status jan-claudian.service` → `inactive (dead)`, last `Stopped … 11:33:01` local time. That unit is "lifetime-bound to Obsidian" (`~/.local/bin/obsidian-jan` starts/stops it). The only llama-server running is the **Jan desktop app's** router: `--models-preset ~/.local/share/Jan/data/llamacpp/router.preset.ini --models-max 2 --host 127.0.0.1 --port 62872`, with no model loaded (eGPU `card0` `0000:03:00.0`: 0.3 of 15.9 GiB used).
- The hunt rules forbid changing or stopping any system service or model server, so I did **not** start `jan-claudian.service`. I also did not point the tool at Jan's router on 62872: its preset is a different one, and the unit file warns that Jan's preset "fills the 16GB card and kills the Vulkan device". Section 5 is deferred to the end of the hunt; see the final status below.

- **What can run without the router (09:52 UTC):** built the section-5 synthetic DB (`<tmp>/s5/data/database.db`: 8 uncategorised counterparties such as `Test Supermarkt B.V.` "Pinbetaling boodschappen", `Test Energie N.V.` "Termijnbedrag stroom en gas", `Test Werkgever B.V.` "Salaris september", `Test Streaming` "Maandabonnement", plus 4 categorised few-shot rows and 11 categories), then ran the real CLI against the **real** `/sys/class/drm` and `/proc` with the router down:
  ```
  AI_SUGGEST_API_KEY=<given> .venv/bin/python -m tools.ai_suggest --db <tmp>/s5/data/database.db --out <tmp>/s5/precheck.csv
  8 groepen ongecategoriseerde transacties (Ongecategoriseerd).
  [1/8] Test Streaming (3×) → model-fout (endpoint onbereikbaar: <urlopen error [Errno 111] Connection refused>) in 0.0 s
  … [4/8] …
  afgebroken na 4 opeenvolgende modelfouten
  exit=1
  ```
  So the real eGPU (`card0`, 15.9 GiB) passes the pre-check (no exit 2). With a dead endpoint the tool fails cleanly (4 × model-fout → abort → partial CSV). DB SHA-256 unchanged (`cd8a5925…98ed3` before and after). **5.1–5.4 (VRAM resident, proposals, seconds per call, spill warning) were not run.** See the final status below.

---

## Exploratory pass

**Timebox:** ~12 min · **Focus areas tried:** over-matching zoektermen that pass validation; making the tool write to the DB; output-path abuse; sending traffic off loopback (URL tricks, proxies, redirects, strace); getting descriptions onto stdout (nameless groups, error messages, control characters in naam); running without the eGPU check (fake `--sysfs-root`, real `/proc`); malformed inputs (non-SQLite `--db`, missing output dir, dead endpoint).

### [exploratory] E1 — Over-matching zoektermen pass validation with no flag, and conflicting duplicate terms go unflagged · 🟡 Medium
- **Input (e1.py):** uncategorised `Test Supermarkt B.V.` ×4 "Pinbetaling boodschappen pas 01x", `Test Bakker` ×3 "Pinbetaling brood pas 02x", `Test Apotheek` ×2 "Pinbetaling medicijnen", `Test Energie B.V.` "Termijnbedrag stroom", `Test Werkgever B.V.` +2500 "Salaris september". The stub (as the model) proposes `pinbetaling`, `betaling`, `b.v.` (for both the Energie expense and the Werkgever income group).
- **Command:** `cd <tmp> && .venv/bin/python e1.py`
- **Observed:**
  ```
  'Test Supermarkt B.V.'   zoekterm='pinbetaling'  vlaggen=''  would also match: ['Test Apotheek', 'Test Bakker']
  'Test Bakker'            zoekterm='betaling'     vlaggen=''  would also match: ['Test Apotheek', 'Test Supermarkt B.V.']
  'Test Energie B.V.'      zoekterm='b.v.'         vlaggen=''  would also match: ['Test Supermarkt B.V.', 'Test Werkgever B.V.']
  'Test Werkgever B.V.'    zoekterm='b.v.'         vlaggen=''  would also match: ['Test Energie B.V.', 'Test Supermarkt B.V.']
  ```
  The same happens in 1.2 (`test vriend` proposed for the inkomsten row → Salaris and the uitgaven row → Abonnementen) and in 2.1 (`test kapper` is a substring of the neighbouring group `Test Kappers`).
- **Why:** the validator only checks ≥ 4 chars / no digits / present in every text of *this* group. The collision check skips `Ongecategoriseerd`, so it's blind to other *uncategorised* groups the term would also swallow. Nothing compares rows of the same review file with each other. On Joost's first run after an import, most rows are uncategorised, so an over-broad term (`b.v.`, `pinbetaling`, `betaling`) comes out with **no flag at all**, which gives the reviewer no signal. The brief's promise is a "safe rule".
- **Why not higher:** the code follows the brief's literal rules (≥ 4, no digits, every-text substring, collision only against other categories), Joost reviews every row, and applying proposals is item 0003. The system prompt tells the model to avoid generic words, but that's not enforced.
- **Suggested direction:** also count hits on uncategorised transactions outside the group (e.g. flag `raakt ook N ongecategoriseerde transacties van andere tegenpartijen`), and flag a zoekterm that appears in more than one row or is a substring of another row's key.
- **Location:** `tools/ai_suggest/rules.py` (`validate_zoekterm`, `collision_flag`), `__main__.py` main loop

### [exploratory] E2 — `--out` pointing at the database overwrites `database.db` with the CSV · 🟠 High
- **Input (e2.py):** normal synthetic DB (2× `Test Bakker`, 1× `Test Garage` in Auto). Run with `--out` = the same path as `--db`.
- **Command:** `main(["--db", "<tmp>/data/database.db", "--out", "<tmp>/data/database.db", "--endpoint", <stub>, "--sysfs-root", <fake>, "--proc-root", <fake>])` via `cd <tmp> && .venv/bin/python e2.py`
- **Observed:**
  ```
  E2 exit 0 | sha same: False
  E2 first bytes of database.db: b'\xef\xbb\xbfgroep;sleutel;naam;voorbeeld_omschrijving;aantal;totaal_b'
  E2 sqlite now: DatabaseError file is not a database
  ```
  Exit 0, no warning. `write_review` writes `<db>.tmp` and `os.replace`s it over the database, so every transaction, rule and category is gone.
- **Expected:** the tool is read-only towards `database.db` (brief: "The tool never writes to it"; out of scope: "Any write to database.db"). A self-overwrite should be refused before the run, e.g. by comparing `Path(out).resolve()` with the DB path (and `os.path.samefile` when it exists). Ideally it should also refuse to write onto an existing `.db`/SQLite file or the DB's `-journal`/`-wal`.
- **Severity rationale:** total, silent data loss of the one file the feature promises never to touch, reachable through the tool's own CLI with a plausible slip (copy-pasting the `--db` value into `--out`). Rated 🟠, not 🔴, only because it needs a wrong argument; the normal flow never does it.
- **Location:** `tools/ai_suggest/__main__.py::main` (no out-path check), `tools/ai_suggest/review.py::write_review`

### [exploratory] E3 — Output path isn't checked up front: a bad `--out` crashes after all model calls and loses the run · 🟡 Medium
- **Input:** 3 uncategorised groups; `--out <tmp>/typo-map/review.csv` (directory doesn't exist).
- **Command:** `cd <tmp> && .venv/bin/python e2.py` (second half)
- **Observed:** `E17 raised after 3 model calls: FileNotFoundError [Errno 2] No such file or directory: '<tmp>/typo-map/review.csv.tmp'`. That's an uncaught traceback after every group was already sent to the model. No review file, no summary. With the real model (tens of seconds per group, many groups) a typo or a non-writable DB directory (the default output location) throws away the whole GPU run.
- **Expected:** validate that the output directory exists and is writable before the GPU guard and the first model call (and never leave only a traceback).
- **Location:** `tools/ai_suggest/__main__.py::main`

### [exploratory] E4 — Control characters in `naam` go raw to stdout · 🟢 Low
- **Input (e3.py):** naam `"\x1b[2J\x1b[31mTest Rood"` and naam `"Test Naam\nPINBETALING GEHEIM 1234"`, omschrijving "Omschrijving Geheim"; the stub answers non-JSON that contains the description text.
- **Observed stdout (repr):** `[1/2] \x1b[2J\x1b[31mTest Rood (1×) → model-fout (antwoord is geen geldige JSON) …` and `[2/2] Test Naam\nPINBETALING GEHEIM 1234 (1×) → …`. The ANSI sequence clears the terminal and colours the output. The description "Omschrijving Geheim" does **not** appear, even when the model echoes it in an invalid answer (the error text is fixed). Only the `naam` field (allowed by the brief) is printed, but unsanitised.
- **Expected:** strip/escape control characters in the printed name.
- **Location:** `tools/ai_suggest/__main__.py::display_name`

### [exploratory] E5 — `--sysfs-root` (a public flag) disables the pre-call eGPU check; one request is sent before the post-check stops it · 🟢 Low
- **Input:** a fake sysfs with a 16 GiB card, the real `/proc` (no `--proc-root`), the stub endpoint.
- **Observed:** `exit 3 | requests that reached the endpoint: 1` · `model-proces niet gevonden op :39387`. The pre-check is bypassed with a documented flag, and the per-process post-check (real `/proc`) catches it after exactly one call. A full bypass needs the hidden `--proc-root` plus a hand-built fake `/proc` tree, which only a deliberate test setup does. The one request stays on loopback. Low, by design (test hook), but `--sysfs-root` could be hidden like `--proc-root`.
- **Location:** `tools/ai_suggest/__main__.py::parse_args`

### [exploratory] Checked, no finding
- **Off-loopback traffic:** 16 URL tricks refused or reduced to loopback (see 4.3). Proxies ignored, redirects refused, and strace shows only `127.0.0.1` connects. `http://127.0.0.1:0` silently becomes port 80 (`parts.port or 80`), still loopback, so harmless.
- **DB writes through the tool's connection:** impossible (`mode=ro`, 3 write kinds raise). No journal/wal/shm files created. The DB SHA is unchanged across every run in this hunt except E2.
- **Descriptions on stdout:** nameless groups print `(geen naam)`, model error messages are fixed strings, and URLError text doesn't include content.
- **Non-SQLite `--db`:** uncaught `sqlite3.DatabaseError: file is not a database` traceback before any model call. Cosmetic, nothing lost.
- **Dead endpoint on real hardware:** clean abort after 4 `Connection refused`, partial CSV (see section 5 note).

---

## Section 5 final status: BLOCKED, not run (09:52 UTC)
Re-checked after the exploratory pass: nothing is listening on `127.0.0.1:6767`, and `jan-claudian.service` is still `inactive`. Under the hunt's rules I may not start model servers, so **5.1–5.4 / AC14 are unverified**. No VRAM, per-call-seconds or spill numbers exist for this round. To finish: start the 6767 router (e.g. open Obsidian through `obsidian-jan`, or `systemctl --user start jan-claudian.service` with Joost's OK), then run section 5 once against the prepared DB:
```
AI_SUGGEST_API_KEY=<given> .venv/bin/python -m tools.ai_suggest --db /tmp/tmp.H5feenupyk/s5/data/database.db --out /tmp/tmp.H5feenupyk/s5/review.csv
```
(Note for that run: the Jan desktop router on :62872 is up with `--models-max 2` but held no model at 09:49 UTC, so the spill warning is expected **not** to fire unless Jan loads a model first.)

---

## Summary

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| E2 | `--out` = DB path overwrites `database.db` with the CSV (exit 0, silent, total data loss) | 🟠 High | `tools/ai_suggest/__main__.py::main`, `review.py::write_review` |
| F2 | IBANs with double spaces/tabs/NBSP, dashes/dots or a glued `IBAN` prefix reach the model; whitespace is collapsed *after* the regex, so they become the banned spaced form; the glued form matches the AC13 regex | 🟡 Medium | `tools/ai_suggest/prompt.py::scrub` / `IBAN_RE` |
| E1 | Over-broad zoektermen (`b.v.`, `pinbetaling`, `betaling`) pass validation with no flag; the same term proposed for rows with different categories goes unflagged | 🟡 Medium | `tools/ai_suggest/rules.py`, `__main__.py` |
| E3 | Output path not checked up front: a bad `--out` (or read-only DB dir) crashes with a traceback after all model calls, so no CSV | 🟡 Medium | `tools/ai_suggest/__main__.py::main` |
| F1 | `zekerheid` 1.5 → `0,01`, no flag (percentage heuristic) | 🟢 Low | `tools/ai_suggest/llm.py::normalize_zekerheid` |
| E4 | Control characters/ANSI in `naam` go raw to stdout | 🟢 Low | `tools/ai_suggest/__main__.py::display_name` |
| E5 | Public `--sysfs-root` skips the pre-call eGPU check (1 request, then the post-check exits 3) | 🟢 Low | `tools/ai_suggest/__main__.py::parse_args` |

**Headline counts:** 0 🔴 · 1 🟠 · 3 🟡 · 3 🟢
**Protocol coverage:** sections 1–4, the high-stakes table and the regression scope were all run. **Section 5 (AC14: 5.1–5.4) was NOT run** because the `127.0.0.1:6767` router was down (`jan-claudian.service` inactive) and the hunt rules forbid starting it. Only the real-sysfs pre-check and the dead-endpoint abort were verified. Exploratory pass done (~12 min).

---

## Recommended next steps

1. 🟠 E2: refuse `--out` that resolves to (or `samefile`s) the `--db` path, or any existing SQLite file, before the run starts.
2. ⚠️ AC14: start the 6767 router and run section 5 once. Record the GPU line (resident GiB), per-call seconds (cold vs warm), whether the spill warning appears, and whether the model proposes over-broad terms like `pinbetaling`/`b.v.` (feeds E1).
3. 🟡 F2: collapse whitespace (incl. NBSP/tabs) *before* the IBAN substitution; accept `-`/`.` separators and a letter-glued start.
4. 🟡 E3: check the output directory is writable before the GPU guard; don't lose a finished run to a write error.
5. 🟡 E1: flag hits on other uncategorised counterparties and duplicate/overlapping zoektermen across rows (a candidate for the sign-off package, possibly together with 0003 apply).
6. 🟢 F1 / E4 / E5: clamp-and-flag `zekerheid` > 1; sanitise the printed name; hide `--sysfs-root` like `--proc-root`.
