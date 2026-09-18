"""AI suggest — categorie- en regelvoorstellen voor ongecategoriseerde transacties.

Gebruik:
    .venv/bin/python -m tools.ai_suggest --db saldoboek/data/database.db

Leest de database alleen (mode=ro), roept alleen het lokale endpoint aan en
schrijft een review-CSV. Toepassen gebeurt pas met tools.ai_apply.
"""

import argparse
import os
import sys
import time
from datetime import datetime

from tools.ai_common.grouping import (
    UNCATEGORIZED,
    group_key,
    rule_text,
    sign_type,
)
from tools.ai_suggest import gpu, prompt, review, rules
from tools.ai_suggest.db import ReadOnlyDB
from tools.ai_suggest.llm import EndpointError, LLMClient, LLMError, check_endpoint

DEFAULT_DB = "saldoboek/data/database.db"
DEFAULT_MODEL = "Qwen3-14B-Q4_K_M"
DEFAULT_ENDPOINT = "http://127.0.0.1:6767"
DEFAULT_API_KEY_ENV = "AI_SUGGEST_API_KEY"
DEFAULT_SYSFS = "/sys/class/drm"
DEFAULT_PROC = "/proc"
TIMEOUT = 300
MAX_CONSECUTIVE_FAILURES = 4


def parse_args(argv):
    p = argparse.ArgumentParser(prog="python -m tools.ai_suggest", description=__doc__)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--gebruiker", type=int)
    p.add_argument("--out")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    p.add_argument("--sysfs-root", default=DEFAULT_SYSFS)
    p.add_argument("--proc-root", default=DEFAULT_PROC, help=argparse.SUPPRESS)
    return p.parse_args(argv)


def display_name(naam):
    """Naam voor stdout: nooit terugvallen op de omschrijving."""
    naam = (naam or "").strip()
    return naam if naam else "(geen naam)"


def build_groups(transactions):
    groups = {}
    for tx in transactions:
        # Brief: alleen 'Ongecategoriseerd'. NULL telt hier niet mee (0003 zoekt
        # groepen op dezelfde manier terug, via UNCATEGORIZED uit ai_common)
        if tx.categorie != UNCATEGORIZED:
            continue
        key = (group_key(tx.naam, tx.omschrijving), sign_type(tx.bedrag))
        g = groups.setdefault(
            key,
            {
                "sleutel": key[0],
                "type": key[1],
                "naam": (tx.naam or "").strip(),
                "aantal": 0,
                "totaal": 0.0,
                "samples": [],
                "lines": [],
                "texts": [],
            },
        )
        g["aantal"] += 1
        g["totaal"] += tx.bedrag or 0.0
        g["texts"].append(rule_text(tx.naam, tx.omschrijving))
        oms = (tx.omschrijving or "").strip()
        if oms and oms not in g["samples"] and len(g["samples"]) < prompt.MAX_SAMPLES:
            g["samples"].append(oms)
            g["lines"].append(
                f"{tx.datum} · {review.dutch_number(tx.bedrag or 0.0, 2)} · {oms}"
            )
    ordered = sorted(groups.values(), key=lambda g: (-g["aantal"], g["sleutel"], g["type"]))
    for i, g in enumerate(ordered, start=1):
        g["groep"] = i
    return ordered


def review_row(g, categorie="", zoekterm="", zekerheid=None, flags=()):
    return {
        "groep": g["groep"],
        "sleutel": g["sleutel"],
        "naam": g["naam"],
        "voorbeeld_omschrijving": g["samples"][0] if g["samples"] else "",
        "aantal": g["aantal"],
        "totaal_bedrag": review.dutch_number(g["totaal"], 2),
        "type": g["type"],
        "categorie": categorie,
        "zoekterm": zoekterm,
        "zekerheid": "" if zekerheid is None else review.dutch_number(zekerheid, 2),
        "vlaggen": " | ".join(flags),
        "akkoord": "",
        "opmerking": "",
    }


def check_output(out, db_path):
    """Het reviewbestand mag nooit de database (of een ander niet-CSV-bestand) raken."""
    out_path = os.path.realpath(out)
    if out_path == os.path.realpath(db_path):
        return "--out mag niet de database zijn"
    if not out_path.lower().endswith(".csv"):
        return "--out moet een .csv-bestand zijn"
    return None


def resolve_user(db, requested):
    users = db.users()
    if requested is not None:
        if requested not in {uid for uid, _ in users}:
            raise SystemExit(f"Gebruiker {requested} bestaat niet.")
        return requested
    if len(users) == 1:
        return users[0][0]
    lijst = ", ".join(f"{uid}={naam}" for uid, naam in users) or "(geen)"
    print(f"Kies een gebruiker met --gebruiker: {lijst}")
    return None


def main(argv=None):
    args = parse_args(argv)

    try:
        check_endpoint(args.endpoint)
    except EndpointError as e:
        print(str(e))
        return 1

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"Let op: {args.api_key_env} is niet gezet — aanroep zonder API-sleutel.")

    if args.out:
        problem = check_output(args.out, args.db)
        if problem:
            print(problem)
            return 1

    try:
        egpu = gpu.require_egpu(args.sysfs_root)
    except gpu.GuardError as e:
        print(e.message)
        return e.code

    try:
        db = ReadOnlyDB(args.db)
    except FileNotFoundError as e:
        print(str(e))
        return 1

    try:
        gebruiker = resolve_user(db, args.gebruiker)
        if gebruiker is None:
            return 1
        categories = db.categories(gebruiker)
        all_rules = db.rules(gebruiker)
        transactions = db.transactions(gebruiker)
    finally:
        db.close()

    examples = prompt.fewshot_examples(transactions)
    groups = build_groups(transactions)
    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.db)),
        f"ai_review_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
    )
    print(f"{len(groups)} groepen ongecategoriseerde transacties ({UNCATEGORIZED}).")

    client = LLMClient(args.endpoint, args.model, api_key, timeout=TIMEOUT)
    rows = []
    calls = 0
    durations = []
    consecutive = 0
    gpu_report = None
    spill_warning = None
    aborted = False

    for g in groups:
        name = display_name(g["naam"])
        allowed = [naam for naam, typ in categories if typ == g["type"]]
        if not allowed:
            rows.append(review_row(g, flags=[f"geen categorieën voor {g['type']}"]))
            print(f"[{g['groep']}/{len(groups)}] {name} ({g['aantal']}×) → geen categorieën")
            continue

        messages = prompt.build_messages(g, allowed, examples)
        schema = prompt.response_schema(allowed)
        started = time.monotonic()
        calls += 1
        try:
            answer = client.suggest(messages, schema, allowed)
        except LLMError as e:
            elapsed = time.monotonic() - started
            durations.append(elapsed)
            consecutive += 1
            rows.append(review_row(g, flags=["model-fout"]))
            print(f"[{g['groep']}/{len(groups)}] {name} ({g['aantal']}×) → model-fout ({e}) in {elapsed:.1f} s")
            if consecutive >= MAX_CONSECUTIVE_FAILURES:
                print(f"afgebroken na {MAX_CONSECUTIVE_FAILURES} opeenvolgende modelfouten")
                aborted = True
                break
            continue

        elapsed = time.monotonic() - started
        durations.append(elapsed)
        consecutive = 0

        if gpu_report is None:
            try:
                gpu_report, spill_warning = gpu.post_check(
                    egpu, args.proc_root, args.model, client.port
                )
            except gpu.GuardError as e:
                print(e.message)
                return e.code
            print(gpu_report)
            if spill_warning:
                print(spill_warning)

        flags = list(answer["flags"])
        zoekterm, zflags = rules.choose_zoekterm(answer["zoekterm"], g["naam"], g["texts"])
        flags += zflags
        flags += rules.collision_flag(zoekterm, answer["categorie"], transactions)
        flags += rules.shadow_flag(g["texts"], all_rules)
        rows.append(
            review_row(g, answer["categorie"], zoekterm, answer["zekerheid"], flags)
        )
        print(
            f"[{g['groep']}/{len(groups)}] {name} ({g['aantal']}×) → "
            f"{answer['categorie']} in {elapsed:.1f} s"
        )

    review.write_review(out, rows)

    flag_count = sum(1 for r in rows if r["vlaggen"])
    mean = sum(durations) / len(durations) if durations else 0.0
    print("")
    print("Samenvatting")
    print(f"  groepen: {len(groups)} (in bestand: {len(rows)})")
    print(f"  modelaanroepen: {calls}, gemiddeld {mean:.1f} s")
    print(f"  rijen met vlaggen: {flag_count}")
    if gpu_report:
        print(f"  {gpu_report}")
    if spill_warning:
        print(f"  {spill_warning}")
    print(f"  reviewbestand: {out}")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
