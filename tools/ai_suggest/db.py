"""Alleen-lezen toegang tot SaldoBoek's database.

SaldoBoek's DatabaseManager schrijft bij het openen (CREATE/seed), dus die
gebruiken we hier bewust niet: de verbinding is `mode=ro`.
"""

import sqlite3
from collections import OrderedDict, namedtuple
from pathlib import Path

from tools.ai_common.grouping import UNCATEGORIZED

Transaction = namedtuple(
    "Transaction", "id datum naam omschrijving bedrag categorie"
)


class ReadOnlyDB:
    def __init__(self, path):
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Database niet gevonden: {resolved}")
        self.path = resolved
        self.conn = sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True)

    def close(self):
        self.conn.close()

    def users(self):
        return self.conn.execute(
            "SELECT id, naam FROM gebruikers ORDER BY id"
        ).fetchall()

    def categories(self, gebruiker_id):
        """(naam, type) van de gebruiker, zonder 'Ongecategoriseerd'."""
        rows = self.conn.execute(
            "SELECT naam, type FROM categorieen WHERE gebruiker_id = ? ORDER BY type, naam",
            (gebruiker_id,),
        ).fetchall()
        return [(naam, typ) for naam, typ in rows if naam != UNCATEGORIZED]

    def transactions(self, gebruiker_id):
        rows = self.conn.execute(
            "SELECT id, datum, naam, omschrijving, bedrag, categorie "
            "FROM transacties WHERE gebruiker_id = ? ORDER BY datum DESC, id DESC",
            (gebruiker_id,),
        ).fetchall()
        return [Transaction(*row) for row in rows]

    def rules(self, gebruiker_id):
        """Actieve regels in dezelfde volgorde als Categorizer._load_rules:
        eerst globaal, daarna gebruikersregels (die dezelfde term overschrijven).
        Eerste match wint."""
        rules = OrderedDict()
        for term, cat in self.conn.execute(
            "SELECT zoekterm, categorie FROM categorisatie_regels "
            "WHERE actief = 1 AND gebruiker_id IS NULL"
        ):
            rules[str(term).lower()] = cat
        for term, cat in self.conn.execute(
            "SELECT zoekterm, categorie FROM categorisatie_regels "
            "WHERE actief = 1 AND gebruiker_id = ?",
            (gebruiker_id,),
        ):
            rules[str(term).lower()] = cat
        return rules
