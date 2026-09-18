import csv
import os

import pandas as pd

# Kolommen die samen een Knab-header herkennen (ook als er regels boven staan)
KNAB_HEADER_MARKERS = ("CreditDebet", "Tegenrekeninghouder")

# CreditDebet bepaalt het teken: Knab levert Bedrag altijd zonder teken
KNAB_SIGN = {
    "Afschrijvingen": -1,
    "Bijschrijvingen": 1,
}

KNAB_ENCODINGS = ("utf-8-sig", "cp1252")
KNAB_DATE_FORMAT = "%d-%m-%Y"
DETECT_MAX_ROWS = 20


def _read_rows(filepath, max_rows=None):
    """Lees CSV-rijen met de csv-module, met encoding-fallback."""
    last_error = None
    for encoding in KNAB_ENCODINGS:
        try:
            with open(filepath, encoding=encoding, newline="") as f:
                reader = csv.reader(f, delimiter=";", quotechar='"')
                rows = []
                for row in reader:
                    rows.append(row)
                    if max_rows is not None and len(rows) >= max_rows:
                        break
                return rows
        except UnicodeDecodeError as e:
            last_error = e
            continue
    raise ValueError(f"Kon {filepath} niet lezen: {last_error}")


def _is_header(row):
    cells = [cell.strip() for cell in row]
    return all(marker in cells for marker in KNAB_HEADER_MARKERS)


def is_knab_file(filepath):
    """True als het bestand een Knab-header bevat (binnen de eerste rijen)."""
    try:
        rows = _read_rows(filepath, max_rows=DETECT_MAX_ROWS)
    except Exception:
        return False
    return any(_is_header(row) for row in rows)


class KnabParser:
    """Parser voor Knab CSV bestanden (Transactieoverzicht)"""

    def __init__(self, account_type=None):
        """
        Initialiseer KnabParser.

        Args:
            account_type: Optioneel 'betaalrekening' of 'spaarrekening'.
                          Indien None, wordt interactieve modus gebruikt (alleen voor CLI).
        """
        self.account_type = account_type

    def parse_csv(self, filepath, account_type=None):
        """Parse een Knab CSV-bestand.

        Anders dan de andere parsers worden formaatfouten niet ingeslikt:
        een onbekende CreditDebet-waarde, een onleesbaar bedrag of een
        onleesbare datum geeft een ValueError, zodat er nooit transacties
        met een gegokt teken worden geïmporteerd.

        Args:
            filepath: Pad naar CSV bestand.
            account_type: Optioneel 'betaalrekening' of 'spaarrekening'.
                          Overschrijft constructor waarde. None = interactieve modus.
        """
        df = self._read_knab_table(filepath)

        if account_type is not None:
            rekeningtype = account_type
        elif self.account_type is not None:
            rekeningtype = self.account_type
        else:
            rekeningtype = self._ask_account_type(filepath)

        processed_df = self._process_knab_data(df, rekeningtype, filepath)
        self._print_import_summary(filepath, processed_df, rekeningtype)
        return processed_df

    def _read_knab_table(self, filepath):
        """Zoek de header-rij op inhoud en bouw een DataFrame met alleen strings."""
        rows = _read_rows(filepath)

        header_index = None
        for i, row in enumerate(rows):
            if _is_header(row):
                header_index = i
                break
        if header_index is None:
            raise ValueError(f"Geen Knab-header gevonden in {filepath}")

        header = [cell.strip() for cell in rows[header_index]]
        # De afsluitende ';' levert lege kolomnamen op: die vallen weg
        keep = [i for i, name in enumerate(header) if name != ""]
        columns = [header[i] for i in keep]
        width = len(header)

        records = []
        for line_no, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
            if not any(cell.strip() for cell in row):
                continue
            extra = row[width:]
            if any(cell.strip() for cell in extra):
                raise ValueError(
                    f"Rij {line_no} in {filepath} heeft meer gevulde velden dan de header"
                )
            row = (row + [""] * width)[:width]
            records.append([row[i] for i in keep])

        return pd.DataFrame(records, columns=columns, dtype=str)

    def _ask_account_type(self, filepath):
        """Vraag gebruiker om rekeningtype"""
        print(f"\nBestand: {filepath}")
        while True:
            keuze = (
                input("Rekeningtype? (b = betaalrekening, s = spaarrekening): ")
                .strip()
                .lower()
            )
            if keuze == "b":
                return "betaalrekening"
            elif keuze == "s":
                return "spaarrekening"
            else:
                print("Ongeldige invoer. Kies 'b' of 's'.")

    def _process_knab_data(self, df, rekeningtype, filepath):
        """Verwerk Knab data naar gestandaardiseerd formaat"""
        if df.empty:
            return pd.DataFrame(
                columns=[
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
            )

        def text(column):
            if column not in df.columns:
                return pd.Series([""] * len(df), index=df.index)
            return df[column].fillna("").astype(str).str.strip()

        # Teken bepalen, onbekende waarden weigeren (vóór alles, geen deelresultaat)
        credit_debet = text("CreditDebet")
        onbekend = sorted(set(credit_debet[~credit_debet.isin(KNAB_SIGN.keys())]))
        if onbekend:
            raise ValueError(
                f"Onbekende CreditDebet-waarde(n) in {filepath}: {', '.join(repr(v) for v in onbekend)}"
            )
        sign = credit_debet.map(KNAB_SIGN)

        bedrag = self._convert_dutch_currency(text("Bedrag"), filepath) * sign

        datum_tekst = text("Transactiedatum")
        datum_tekst = datum_tekst.where(datum_tekst != "", text("Boekdatum"))
        try:
            datum = pd.to_datetime(datum_tekst, format=KNAB_DATE_FORMAT, errors="raise")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Onleesbare datum in {filepath}: {e}")

        naam = text("Tegenrekeninghouder")
        omschrijving = text("Omschrijving")
        omschrijving = omschrijving.where(omschrijving != "", naam)

        return pd.DataFrame(
            {
                "datum": datum,
                "rekening": text("Rekeningnummer"),
                "tegenrekening": text("Tegenrekeningnummer"),
                "naam": naam,
                "valuta": text("Valutacode"),
                "saldo_voor": 0.0,
                "bedrag": bedrag,
                "omschrijving": omschrijving,
                "rekeningtype": rekeningtype,
            }
        )

    def _convert_dutch_currency(self, series, filepath):
        """Converteer Nederlands valuta formaat (1.234,56 of 6,5) naar float"""
        cleaned = series.str.replace(".", "", regex=False).str.replace(
            ",", ".", regex=False
        )
        try:
            return cleaned.astype(float)
        except ValueError:
            slecht = [v for v in series if not self._is_number(v)]
            raise ValueError(
                f"Onleesbaar bedrag in {filepath}: {', '.join(repr(v) for v in slecht)}"
            )

    @staticmethod
    def _is_number(value):
        try:
            float(value.replace(".", "").replace(",", "."))
            return True
        except ValueError:
            return False

    def _print_import_summary(self, filepath, df, rekeningtype):
        """Print samenvatting van geïmporteerde data"""
        print(
            f"✓ {os.path.basename(filepath)} succesvol gelezen: {len(df)} transacties"
        )
        print(f"  Rekeningtype: {rekeningtype}")
        if not df.empty:
            print(
                f"  Periode: {df['datum'].min().strftime('%d-%m-%Y')} tot {df['datum'].max().strftime('%d-%m-%Y')}"
            )
