"""Acceptatietests detectie + import van Knab (0001-knab-csv-parser). Alleen fictieve data."""

import shutil

import pandas as pd

from .conftest import count_transactions, knab_row

DEFAULT_KNAB_NAME = (
    "Knab Transactieoverzicht Test NL00KNAB0000000000 - 2026-01-01 - 2026-09-17.csv"
)


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, filepath, account_type=None):
        self.calls.append(filepath)
        return pd.DataFrame()


def spy_parsers(importer, monkeypatch):
    spies = {name: Spy() for name in ("knab", "rabo", "sns")}
    monkeypatch.setattr(importer.knab_parser, "parse_csv", spies["knab"])
    monkeypatch.setattr(importer.rabo_parser, "parse_csv", spies["rabo"])
    monkeypatch.setattr(importer.sns_parser, "parse_csv", spies["sns"])
    return spies


def test_detect_by_filename(importer, knab_csv, monkeypatch):
    # AC6 (standaard Knab-bestandsnaam)
    path = knab_csv([knab_row()], filename=DEFAULT_KNAB_NAME)
    spies = spy_parsers(importer, monkeypatch)
    importer.detect_bank_and_parse(str(path), "betaalrekening")
    assert spies["knab"].calls == [str(path)]
    assert not spies["rabo"].calls and not spies["sns"].calls


def test_detect_by_header(importer, knab_csv, monkeypatch, tmp_path):
    # AC6 (zelfde inhoud als export.csv)
    source = knab_csv([knab_row()], filename=DEFAULT_KNAB_NAME)
    path = tmp_path / "export.csv"
    shutil.copy(source, path)
    spies = spy_parsers(importer, monkeypatch)
    importer.detect_bank_and_parse(str(path), "betaalrekening")
    assert spies["knab"].calls == [str(path)]


def test_detect_by_header_parses_for_real(importer, knab_csv, tmp_path):
    source = knab_csv([knab_row("Afschrijvingen", "6,5")], filename=DEFAULT_KNAB_NAME)
    path = tmp_path / "export.csv"
    shutil.copy(source, path)
    df = importer.detect_bank_and_parse(str(path), "betaalrekening")
    assert list(df["bedrag"]) == [-6.5]


def test_rabo_filename_still_rabo(importer, tmp_path, monkeypatch):
    # AC7 (regressie)
    path = tmp_path / "RABO_test.csv"
    path.write_text('"Datum","Bedrag"\n', encoding="utf-8")
    spies = spy_parsers(importer, monkeypatch)
    importer.detect_bank_and_parse(str(path), "betaalrekening")
    assert spies["rabo"].calls == [str(path)]
    assert not spies["knab"].calls


def test_non_knab_unknown_file_still_rejected(importer, tmp_path):
    path = tmp_path / "export.csv"
    path.write_text('"Datum";"Bedrag";\r\n"01-01-2026";"1,0";\r\n', encoding="utf-8")
    try:
        importer.detect_bank_and_parse(str(path), "betaalrekening")
    except ValueError as e:
        assert "Onbekend bankformaat" in str(e)
    else:
        raise AssertionError("verwacht ValueError voor onbekend bankformaat")


def test_import_unknown_creditdebet_stores_nothing(importer, knab_csv):
    # AC3 (import-deel)
    path = knab_csv([knab_row("Afschrijvingen"), knab_row("Onbekend")])
    total, _ = importer.import_transactions_with_categorization(
        [str(path)], 1, "betaalrekening"
    )
    assert total == 0
    assert count_transactions(importer) == 0


def test_import_twice_is_idempotent(importer, knab_csv):
    # AC8
    path = knab_csv(
        [
            knab_row("Afschrijvingen", "6,5", "17-09-2026"),
            knab_row("Bijschrijvingen", "1234,56", "16-09-2026", naam="Test Werkgever"),
            knab_row("Afschrijvingen", "12,95", "15-09-2026", naam="Test Supermarkt"),
        ],
        filename=DEFAULT_KNAB_NAME,
    )
    first, _ = importer.import_transactions_with_categorization(
        [str(path)], 1, "betaalrekening"
    )
    second, _ = importer.import_transactions_with_categorization(
        [str(path)], 1, "betaalrekening"
    )
    assert first == 3
    assert second == 0
    assert count_transactions(importer) == 3
    bedragen = importer.db.execute(
        "SELECT bedrag FROM transacties ORDER BY datum", fetch=True
    )
    assert [b for (b,) in bedragen] == [-12.95, 1234.56, -6.5]
