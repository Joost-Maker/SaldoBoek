"""Acceptatietests KnabParser (0001-knab-csv-parser). Alleen fictieve data."""

import pandas as pd
import pytest

from saldoboek.core.parsers.knab_parser import KnabParser, is_knab_file

from .conftest import knab_row

TEXT_COLUMNS = ["rekening", "tegenrekening", "naam", "valuta", "omschrijving"]


def parse(path):
    return KnabParser().parse_csv(str(path), "betaalrekening")


def test_basic_rows(knab_csv):
    # AC1
    path = knab_csv(
        [
            knab_row("Afschrijvingen", "6,5", "17-09-2026"),
            knab_row("Bijschrijvingen", "1234,56", "17-09-2026", naam="Test Werkgever"),
        ]
    )
    df = parse(path)

    assert len(df) == 2
    assert list(df["bedrag"]) == [-6.5, 1234.56]
    assert (df["datum"] == pd.Timestamp(2026, 9, 17)).all()
    assert (df["rekeningtype"] == "betaalrekening").all()
    assert (df["saldo_voor"] == 0.0).all()
    assert not [c for c in df.columns if str(c).startswith("Unnamed")]
    assert list(df.columns) == [
        "datum",
        "rekening",
        "tegenrekening",
        "naam",
        "valuta",
        "saldo_voor",
        "bedrag",
        "omschrijving",
        "rekeningtype",
    ]
    assert df.iloc[0]["rekening"] == "NL00KNAB0000000000"
    assert df.iloc[0]["tegenrekening"] == "NL00INGB0000000000"
    assert df.iloc[0]["naam"] == "Test Uitgever B.V."
    assert df.iloc[0]["valuta"] == "EUR"


def test_thousands_separator(knab_csv):
    # AC2
    df = parse(knab_csv([knab_row("Afschrijvingen", "1.234,56")]))
    assert df.iloc[0]["bedrag"] == -1234.56


def test_unknown_creditdebet_raises(knab_csv):
    # AC3 (parser-deel)
    path = knab_csv([knab_row("Afschrijvingen"), knab_row("Onbekend")])
    with pytest.raises(ValueError, match="Onbekend"):
        parse(path)


def test_empty_creditdebet_raises(knab_csv):
    path = knab_csv([knab_row("")])
    with pytest.raises(ValueError, match="CreditDebet"):
        parse(path)


def test_empty_fields(knab_csv):
    # AC4
    path = knab_csv([knab_row(tegenrekening="", naam="Test Pinautomaat", omschrijving="")])
    df = parse(path)

    assert df.iloc[0]["tegenrekening"] == ""
    assert df.iloc[0]["omschrijving"] == "Test Pinautomaat"
    for column in TEXT_COLUMNS:
        values = df[column]
        assert not values.isna().any(), column
        assert not (values.str.lower() == "nan").any(), column


def test_preamble_is_ignored(knab_csv):
    # AC5
    rows = [knab_row("Afschrijvingen", "6,5"), knab_row("Bijschrijvingen", "10")]
    plain = parse(knab_csv(rows, filename="Knab zonder preamble.csv"))
    with_preamble = parse(
        knab_csv(rows, filename="Knab met preamble.csv", preamble="KNAB EXPORT")
    )
    pd.testing.assert_frame_equal(plain, with_preamble)


def test_boekdatum_fallback(knab_csv):
    df = parse(knab_csv([knab_row(datum="", boekdatum="18-09-2026")]))
    assert df.iloc[0]["datum"] == pd.Timestamp(2026, 9, 18)


def test_unreadable_amount_raises(knab_csv):
    with pytest.raises(ValueError, match="abc"):
        parse(knab_csv([knab_row(bedrag="abc")]))


def test_unreadable_date_raises(knab_csv):
    with pytest.raises(ValueError, match="datum"):
        parse(knab_csv([knab_row(datum="2026/09/17")]))


def test_extra_filled_cell_raises(knab_csv, tmp_path):
    path = knab_csv([knab_row()])
    text = path.read_text(encoding="utf-8").rstrip("\r\n") + '"extra";\r\n'
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="meer gevulde velden"):
        parse(path)


def test_header_only_file(knab_csv):
    df = parse(knab_csv([]))
    assert df.empty
    assert "bedrag" in df.columns


def test_no_header_raises(tmp_path):
    path = tmp_path / "Knab kapot.csv"
    path.write_text('"a";"b";\r\n"1";"2";\r\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Geen Knab-header"):
        parse(path)


def test_is_knab_file(knab_csv, tmp_path):
    assert is_knab_file(knab_csv([knab_row()]))
    other = tmp_path / "other.csv"
    other.write_text('"Datum";"Bedrag";\r\n"01-01-2026";"1,0";\r\n', encoding="utf-8")
    assert not is_knab_file(other)
    assert not is_knab_file(tmp_path / "bestaat-niet.csv")


# Regressietests fixronde 1 (05-bughunt-report.md)


def test_quoted_preamble_does_not_corrupt_header(knab_csv):
    # BUG-1: een preamble die met een losse '"' begint smelt samen met de header;
    # dan ontbreekt 'Rekeningnummer' en moet het bestand geweigerd worden
    path = knab_csv([knab_row()], preamble='"Export van Knab')
    with pytest.raises(ValueError, match="Rekeningnummer"):
        parse(path)


def test_missing_required_column_raises(tmp_path):
    # E-3 (header): hernoemde kolom mag niet stil leeg worden
    from .conftest import KNAB_HEADER, render_knab

    header = ["IBAN" if c == "Rekeningnummer" else c for c in KNAB_HEADER]
    path = tmp_path / "Knab hernoemd.csv"
    path.write_text(render_knab([knab_row()], header=header), encoding="utf-8")
    with pytest.raises(ValueError, match="Rekeningnummer"):
        parse(path)


def test_row_without_any_date_raises(knab_csv):
    # E-2: lege Transactiedatum én Boekdatum -> fout, geen NaT
    path = knab_csv([knab_row(), knab_row(datum="", boekdatum="")])
    with pytest.raises(ValueError, match="zonder Transactiedatum"):
        parse(path)
