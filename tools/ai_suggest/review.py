"""Review-CSV voor LibreOffice: ';', utf-8-sig, decimale komma, atomisch geschreven."""

import csv
import os

COLUMNS = [
    "groep",
    "sleutel",
    "naam",
    "voorbeeld_omschrijving",
    "aantal",
    "totaal_bedrag",
    "type",
    "categorie",
    "zoekterm",
    "zekerheid",
    "vlaggen",
    "akkoord",
    "opmerking",
]


def dutch_number(value, decimals):
    return f"{value:.{decimals}f}".replace(".", ",")


def write_review(path, rows):
    """Schrijf rijen (dicts met COLUMNS-sleutels) atomisch naar `path`."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([row.get(col, "") for col in COLUMNS])
    os.replace(tmp, path)
