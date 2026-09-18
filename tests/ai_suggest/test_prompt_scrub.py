"""IBAN-maskering in prompts (0002-ai-suggest, code gate R5).

Positief: elke IBAN-vorm verdwijnt. Negatief: gewone omschrijvingen blijven
letterlijk staan — zonder deze kant kan een filter slagen door alles weg te halen.
"""

import pytest

from tools.ai_suggest.prompt import scrub

IBANS = [
    "Overboeking NL00ABNA0000000001 okt",
    "Overboeking nl00abna0000000001",
    "Overboeking NL00 ABNA 0000 0000 01",
    "Overboeking NL00  ABNA  0000  0000  01",
    "Overboeking NL00\tRABO\t0000\t0000\t02",
    "Overboeking NL00 INGB 0000 0000 03",
    "Overboeking NL00-KNAB-0000-0000-04",
    "Overboeking NL00.ASNB.0000.0000.05",
    "Overboeking IBANNL00TRIO0000000006 ref",
    "iban: nl00knab0000000000",
    # Code gate R6: een eerdere kandidaat ('AH 12', 'NS 20', 'nr 12', 'op 18')
    # mag de start van een echte IBAN niet overslaan
    "Retour AH 12 boodschappen teruggestort NL00 ABNA 0000 0000 01",
    "NS 20 euro retour graag naar NL00 INGB 0000 0000 01",
    "nr 12 van Test Energie via NL00-ABNA-0000-0000-01",
    "Huur op 18-09-2026 overgemaakt naar NL00 ABNA 0000 0000 01",
    "Twee rekeningen NL00 ABNA 0000 0000 01 en NL00.RABO.0000.0000.02",
]

PLAIN = [
    "Factuur 2026-00123 abonnement oktober",
    "Termijn 3 van 12 maanden huur",
    "huur okt 2026 woning 12a",
    "Kenmerk 1234567890123456 Test Energie",
    "Donald Duck Junior termijnbetalingAbonr.00000000",
    "AH to go 1418 Amsterdam",
    "Jumbo 7042 Utrecht Centrum",
    "Pinbetaling NS 2026 reis Amsterdam Centraal",
]


@pytest.mark.parametrize("text", IBANS)
def test_iban_forms_are_masked(text):
    out = scrub(text)
    assert "[IBAN]" in out
    digits = "".join(ch for ch in out if ch.isdigit())
    assert "0000" not in digits, out


@pytest.mark.parametrize("text", PLAIN)
def test_plain_text_is_left_intact(text):
    assert scrub(text) == " ".join(text.split())
