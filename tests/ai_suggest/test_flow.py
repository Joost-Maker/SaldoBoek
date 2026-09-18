"""Eind-tot-eind: CLI tegen synthetische DB, stub-LLM en nep-GPU (0002-ai-suggest)."""

import re

from tools.ai_common.grouping import group_key

from .conftest import read_review

IBAN_PATTERN = re.compile(r"[A-Z]{2}\d{2}[A-Z]{4}\d{10}")


def seed_basic(sdb):
    for _ in range(3):
        sdb.add_tx("Test Streaming B.V.", "Maandabonnement streaming NL00ABNA0000000001", -9.99)
    for _ in range(2):
        sdb.add_tx("Test Bakker", "Brood en banket", -4.50)


def test_two_groups_two_calls(sdb, stub, run):
    # AC1
    seed_basic(sdb)
    code, out, csv_path = run()
    assert code == 0
    assert len(stub.requests) == 2
    _, rows = read_review(csv_path)
    assert [r["aantal"] for r in rows] == ["3", "2"]
    assert rows[0]["naam"] == "Test Streaming B.V."
    assert rows[0]["totaal_bedrag"] == "-29,97"


def test_model_error_flag(sdb, stub, run):
    # AC2: onbekende categorie en vrije tekst -> model-fout, geen verzonnen categorie
    seed_basic(sdb)
    answers = iter([
        (200, {"categorie": "Verzonnen", "zoekterm": "x", "zekerheid": 1}),
        (200, "dit is geen json"),
    ])
    stub.responder = lambda body: next(answers)
    code, out, csv_path = run()
    assert code == 0
    _, rows = read_review(csv_path)
    assert all("model-fout" in r["vlaggen"] for r in rows)
    assert all(r["categorie"] == "" for r in rows)
    assert "Verzonnen" not in csv_path.read_text(encoding="utf-8-sig")


def test_enum_by_sign(sdb, stub, run):
    # AC3
    sdb.add_tx("Test Werkgever", "Salaris september", 2500.0)
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    run()
    enums = {}
    for req in stub.requests:
        user = req["body"]["messages"][-1]["content"]
        enum = req["body"]["response_format"]["json_schema"]["schema"]["properties"]["categorie"]["enum"]
        enums["inkomsten" if "Type: inkomsten" in user else "uitgaven"] = set(enum)
    assert enums["inkomsten"] == {"Salaris"}
    assert enums["uitgaven"] == {"Abonnementen", "Boodschappen", "Auto"}
    assert "Ongecategoriseerd" not in enums["uitgaven"]


def test_mixed_sign_split(sdb, stub, run):
    sdb.add_tx("Test Persoon", "Tikkie etentje", 10.0)
    sdb.add_tx("Test Persoon", "Tikkie etentje", -10.0)
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert sorted(r["type"] for r in rows) == ["inkomsten", "uitgaven"]
    assert len(stub.requests) == 2


def test_sleutel_matches_helper(sdb, run):
    # AC5
    seed_basic(sdb)
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert [r["sleutel"] for r in rows] == [
        group_key("Test Streaming B.V.", ""),
        group_key("Test Bakker", ""),
    ] == ["test streaming b.v.", "test bakker"]


def test_digits_zoekterm_falls_back(sdb, stub, run):
    # AC4 (eind-tot-eind)
    sdb.add_tx("Test Streaming B.V.", "termijnbetalingAbonr.4163", -9.99)
    stub.responder = lambda body: (200, {"categorie": "Abonnementen", "zoekterm": "abonr.4163", "zekerheid": 0.8})
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert rows[0]["zoekterm"] == "test streaming b.v."


def test_collision_flag(sdb, stub, run):
    # AC6
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    sdb.add_tx("Test Garage", "APK", -60.0, categorie="Auto")
    stub.responder = lambda body: (200, {"categorie": "Boodschappen", "zoekterm": "test", "zekerheid": 0.7})
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert "botsing: 1 transacties in Auto" in rows[0]["vlaggen"]


def test_collision_ignores_uncategorized_and_null(sdb, stub, run):
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    sdb.add_tx("Test Bakker", "Taart", -12.0, categorie=None)
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert "botsing" not in rows[0]["vlaggen"]


def test_shadow_flag(sdb, stub, run):
    # AC7
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    sdb.add_rule("bakker", "Boodschappen")
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert "al gedekt door regel 'bakker'" in rows[0]["vlaggen"]


def test_no_iban_in_requests(sdb, stub, run):
    # AC13: synthetische omschrijvingen bevatten nep-IBAN's, ook met spaties/kleine letters
    sdb.add_tx("Test Streaming B.V.", "Overboeking NL00ABNA0000000001 maand", -9.99)
    sdb.add_tx("Test Huurbaas", "huur nl00 rabo 0000 0000 02 okt", -900.0)
    sdb.add_tx("Test Winkel", "Pin NL00KNAB0000000003", -5.0, categorie="Boodschappen")
    run()
    assert stub.requests
    for req in stub.requests:
        text = str(req["body"])
        assert not IBAN_PATTERN.search(text)
        assert "0000 0000 02" not in text


def test_stdout_has_no_descriptions(sdb, stub, run):
    # FR: geen transactie-inhoud op stdout; naamloze groep toont '(geen naam)' (N13)
    sdb.add_tx("Test Streaming B.V.", "Geheime omschrijving een", -9.99)
    sdb.add_tx("", "Geheime omschrijving twee", -3.0)
    code, out, csv_path = run()
    assert code == 0
    assert "Geheime omschrijving" not in out
    assert "geheime omschrijving" not in out
    assert "(geen naam)" in out
    assert "Test Streaming B.V." in out


def test_abort_after_four_failures_writes_partial(sdb, stub, run):
    # AC12
    for i in range(6):
        sdb.add_tx(f"Test Partij {chr(65 + i)}", "iets", -1.0 - i)
    stub.responder = lambda body: (500, "kapot")
    code, out, csv_path = run()
    assert code == 1
    assert "afgebroken na 4 opeenvolgende modelfouten" in out
    _, rows = read_review(csv_path)
    assert len(rows) == 4
    assert all("model-fout" in r["vlaggen"] for r in rows)


def test_failure_counter_resets_after_success(sdb, stub, run):
    for i in range(6):
        sdb.add_tx(f"Test Partij {chr(65 + i)}", "iets", -1.0 - i)
    calls = {"n": 0}

    def flaky(body):
        calls["n"] += 1
        if calls["n"] % 2 == 0:
            return 500, "kapot"
        from .conftest import default_responder
        return default_responder(body)

    stub.responder = flaky
    code, out, csv_path = run()
    assert code == 0
    _, rows = read_review(csv_path)
    assert len(rows) == 6


def test_no_categories_for_type(sdb, stub, run):
    with sdb.connect() as conn:
        conn.execute("DELETE FROM categorieen WHERE type = 'inkomsten'")
    sdb.add_tx("Test Werkgever", "Salaris", 2500.0)
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert rows[0]["vlaggen"] == "geen categorieën voor inkomsten"
    assert len(stub.requests) == 0


def test_zekerheid_percentage_normalised(sdb, stub, run):
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    stub.responder = lambda body: (200, {"categorie": "Boodschappen", "zoekterm": "test bakker", "zekerheid": 95})
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert rows[0]["zekerheid"] == "0,95"
    assert "zekerheid ongeldig" not in rows[0]["vlaggen"]


def test_zekerheid_out_of_range_flagged(sdb, stub, run):
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    stub.responder = lambda body: (200, {"categorie": "Boodschappen", "zoekterm": "test bakker", "zekerheid": 250})
    code, out, csv_path = run()
    _, rows = read_review(csv_path)
    assert rows[0]["zekerheid"] == "1,00"
    assert "zekerheid ongeldig" in rows[0]["vlaggen"]
