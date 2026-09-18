"""Review-CSV voor LibreOffice: ';', utf-8-sig, decimale komma, atomisch geschreven."""

import csv
import os
import tempfile

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
    """Schrijf rijen (dicts met COLUMNS-sleutels) atomisch naar `path`.

    Het tijdelijke bestand komt van mkstemp (O_EXCL, nieuwe naam), dus een
    bestaande link naar de database kan nooit worden beschreven. mkstemp maakt
    het bestand 0600: het reviewbestand bevat bankdata en is alleen voor de eigenaar.
    """
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".ai_review_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(COLUMNS)
            for row in rows:
                writer.writerow([row.get(col, "") for col in COLUMNS])
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
