"""Zoekterm-validatie, botsing en schaduw (0002-ai-suggest)."""

from collections import OrderedDict

from tools.ai_suggest.db import Transaction
from tools.ai_suggest.rules import (
    choose_zoekterm,
    collision_flag,
    shadow_flag,
    validate_zoekterm,
)

TEXTS = ["test streaming b.v. termijnbetalingabonr.4163", "test streaming b.v. maand"]


def test_naam_always_wins():
    # AC4 (PO-amendement): algemene modelterm wordt vervangen door de volledige naam
    texts = ["test woonstichting huur woning oktober"]
    assert choose_zoekterm("woning", "Test Woonstichting", texts) == ("test woonstichting", [])


def test_naam_with_digits_allowed():
    texts = ["test winkel 1418 pinbetaling"]
    assert choose_zoekterm("pinbetaling", "Test Winkel 1418", texts) == ("test winkel 1418", [])


def test_nameless_invalid_model_term():
    # AC4: lege naam + modelterm met cijfers -> leeg + vlag
    texts = [" termijnbetalingabonr.4163"]
    assert choose_zoekterm("abonr.4163", "", texts) == ("", ["zoekterm ongeldig"])


def test_nameless_valid_model_term():
    # AC4: lege naam + geldige modelterm in élke tekst
    texts = [" maandhuur garagebox", " maandhuur garagebox oktober"]
    assert choose_zoekterm("Maandhuur", "", texts) == ("maandhuur", [])


def test_short_naam_uses_model_term():
    texts = ["ah pinbetaling filiaal", "ah pinbetaling filiaal"]
    assert choose_zoekterm("pinbetaling", "AH", texts) == ("pinbetaling", [])
    assert choose_zoekterm("x", "AH", texts) == ("", ["zoekterm ongeldig"])


def test_validation_rules():
    assert validate_zoekterm("Streaming", TEXTS) == "streaming"
    assert validate_zoekterm("str", TEXTS) is None  # te kort
    assert validate_zoekterm("maand", TEXTS) is None  # niet in élke tekst
    assert validate_zoekterm("  STREAMING  ", TEXTS) == "streaming"
    assert validate_zoekterm(None, TEXTS) is None


def tx(naam, oms, cat):
    return Transaction(1, "2026-09-17", naam, oms, -1.0, cat)


def test_collision_counts_other_categories_only():
    txs = [tx("Test Garage", "APK", "Auto"), tx("Test Bakker", "Brood", "Boodschappen"),
           tx("Test Iets", "x", "Ongecategoriseerd"), tx("Test Null", "x", None)]
    assert collision_flag("test", "Boodschappen", txs) == ["botsing: 1 transacties in Auto"]
    assert collision_flag("", "Boodschappen", txs) == []


def test_shadow_uses_first_rule_in_order():
    rules = OrderedDict([("bakker", "Boodschappen"), ("test", "Overig")])
    assert shadow_flag(["test bakker brood"], rules) == ["al gedekt door regel 'bakker'"]
    assert shadow_flag(["iets anders"], rules) == []
