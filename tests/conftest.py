"""Gedeelde test-fixtures.

Knab-fixtures worden tijdens de test in tmp_path geschreven in plaats van als
.csv in de repo te staan: .gitignore negeert *.csv (zo blijven echte
bankexports buiten git). Alle data hieronder is fictief.
"""

import pytest

KNAB_HEADER = [
    "Rekeningnummer",
    "Transactiedatum",
    "Valutacode",
    "CreditDebet",
    "Bedrag",
    "Tegenrekeningnummer",
    "Tegenrekeninghouder",
    "Valutadatum",
    "Betaalwijze",
    "Omschrijving",
    "Type betaling",
    "Machtigingsnummer",
    "Incassant ID",
    "Referentie",
    "Boekdatum",
]

FAKE_ACCOUNT = "NL00KNAB0000000000"


def knab_row(
    credit_debet="Afschrijvingen",
    bedrag="6,5",
    datum="17-09-2026",
    tegenrekening="NL00INGB0000000000",
    naam="Test Uitgever B.V.",
    omschrijving="Testblad termijnbetaling",
    boekdatum=None,
):
    """Eén Knab-transactie als lijst van 15 velden (fictieve data)."""
    return [
        FAKE_ACCOUNT,
        datum,
        "EUR",
        credit_debet,
        bedrag,
        tegenrekening,
        naam,
        datum,
        "Periodieke incasso",
        omschrijving,
        "",
        "000000000000000",
        "NL00ZZZ000000000000",
        "XXXXXXXXXXXXXXXX",
        datum if boekdatum is None else boekdatum,
    ]


def render_knab(rows, preamble=None, header=None):
    """Knab-formaat: BOM, alle velden gequote, ';' als scheiding, afsluitende ';'."""

    def line(fields):
        return ";".join(f'"{field}"' for field in fields) + ";"

    lines = []
    if preamble is not None:
        lines.append(preamble)
    lines.append(line(header or KNAB_HEADER))
    lines.extend(line(row) for row in rows)
    return "﻿" + "\r\n".join(lines) + "\r\n"


@pytest.fixture
def knab_csv(tmp_path):
    """Factory: schrijf een Knab-bestand in tmp_path en geef het pad terug."""

    def make(rows, filename="Knab Transactieoverzicht Test.csv", preamble=None):
        path = tmp_path / filename
        path.write_text(render_knab(rows, preamble=preamble), encoding="utf-8")
        return path

    return make


@pytest.fixture
def importer(tmp_path):
    """TransactionImporter op een lege tijdelijke database (nooit de echte)."""
    from saldoboek.core.categorization import Categorizer
    from saldoboek.core.database import DatabaseManager
    from saldoboek.core.importer import TransactionImporter

    db = DatabaseManager(db_path=tmp_path / "test.db")
    return TransactionImporter(Categorizer(db, 1), db, 1)


def count_transactions(importer):
    return importer.db.execute("SELECT COUNT(*) FROM transacties", fetch=True)[0][0]
