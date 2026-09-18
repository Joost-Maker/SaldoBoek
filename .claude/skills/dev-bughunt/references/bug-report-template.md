# Bug Hunt Report template

Pipeline: save as `docs/features/NNNN-<slug>/05-bughunt-report.md`; re-hunts append `## Round N`.
Ad-hoc: save as `testing/YYYYMMDDTHHMMSSZ_bugreport.md`.

```markdown
# Bug Hunt Report
**Date (UTC):** YYYY-MM-DDTHH:MM:SSZ
**Feature / scope:** [name (NNNN-<slug> if pipeline)]
**Test protocol:** [path, or "none — ad-hoc hunt"]
**App URL:** [localhost or staging]
**Round:** 1

---

## Environment
- Browser / driver: [e.g. Playwright chromium]
- App version / last commit:
- Test data:

---

## Test results

### [Protocol case or interaction name]
- **Tested:** [what was done — click-by-click if needed]
- **Expected:** [per the protocol]
- **Actual:** [what happened]
- **Severity:** 🔴 / 🟠 / 🟡 / 🟢 — or ✅ pass
- **Console errors:** [verbatim, or "none"]
- **Network errors:** [failed requests, or "none"]
- **Screenshot:** [filename, or "n/a"]
- **Reproduction:** [numbered steps]

...

---

## Exploratory pass

**Timebox:** [~10–15 min] · **Focus areas tried:** [chaos clicks, refresh mid-action, storage
corruption, viewport extremes, …]

### [exploratory] [Finding name — or "No additional findings"]
- Same fields as above (Tested / Expected / Actual / Severity / Console / Reproduction)

---

## Summary

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | | | |

**Headline counts:** N 🔴 · N 🟠 · N 🟡 · N 🟢
**Protocol coverage:** [all cases run / which were skipped and why]

---

## Recommended next steps

1. 🔴 [most urgent]
2. 🟠 [next]
3. 🟡 [backlog candidate — goes in the sign-off package, not the vault]
```

Re-hunt rounds repeat Results → Summary under a `## Round N` header, stating explicitly which
cases were re-run and which prior findings are now resolved.
