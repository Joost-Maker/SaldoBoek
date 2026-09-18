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


def test_digits_fall_back_to_naam():
    # AC4
    assert choose_zoekterm("abonr.4163", "Test Streaming B.V.", TEXTS) == ("test streaming b.v.", [])


def test_invalid_when_fallback_fails():
    # AC4: naam te kort en modelterm ongeldig
    texts = ["ab 123", "ab 456"]
    assert choose_zoekterm("123", "AB", texts) == ("", ["zoekterm ongeldig"])


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
