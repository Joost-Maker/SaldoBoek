import logging
import os

import pandas as pd

from ..config.bank_parsers import BANK_PARSERS
from .parsers.knab_parser import KnabParser, is_knab_file
from .parsers.rabo_parser import RaboParser
from .parsers.sns_parser import SNSParser

logger = logging.getLogger(__name__)


class TransactionImporter:
    def __init__(self, categorizer, db_manager, gebruiker_id):
        self.categorizer = categorizer
        self.db = db_manager
        self.gebruiker_id = gebruiker_id

        # Initialiseer parsers
        self.sns_parser = SNSParser()
        self.rabo_parser = RaboParser()
        self.knab_parser = KnabParser()

    def detect_bank_and_parse(self, filepath, account_type=None):
        """Detecteer bank type en parse het bestand.

        Args:
            filepath: Pad naar het CSV bestand
            account_type: Optioneel 'betaalrekening' of 'spaarrekening'
        """
        filename = os.path.basename(filepath).upper()

        if "SNS" in filename:
            return self.sns_parser.parse_csv(filepath, account_type)
        elif "RABO" in filename or "RABOBANK" in filename:
            return self.rabo_parser.parse_csv(filepath, account_type)
        elif "KNAB" in filename:
            return self.knab_parser.parse_csv(filepath, account_type)
        elif is_knab_file(filepath):
            # Knab-export onder een andere naam: herken aan de header
            return self.knab_parser.parse_csv(filepath, account_type)
        else:
            # Fallback naar oude methode
            for bank_code, parser_method in BANK_PARSERS.items():
                if bank_code in filename:
                    return getattr(self, parser_method)(filepath, account_type)

        raise ValueError(f"Onbekend bankformaat in bestandsnaam: {filename}")

    def import_transactions_with_categorization(
        self, file_paths, gebruiker_id, account_type="betaalrekening"
    ):
        """Importeer transacties met interactieve categorisatie

        Args:
            file_paths: Lijst van bestandspaden
            gebruiker_id: Gebruiker ID
            account_type: 'betaalrekening' of 'spaarrekening'
        """
        ongecategoriseerd = []
        total_imported = 0

        for file_path in file_paths:
            if not os.path.exists(file_path):
                print(f"Bestand niet gevonden: {file_path}")
                continue

            print(f"\nVerwerken: {file_path}")

            try:
                df = self.detect_bank_and_parse(file_path, account_type)
            except ValueError as e:
                print(f"  ! {e}")
                continue

            if df.empty:
                continue

            nieuwe_transacties = 0
            duplicaten = 0

            for _, row in df.iterrows():
                datum_str = row["datum"].strftime("%Y-%m-%d")
                bestaande = self.db.execute(
                    """
                    SELECT COUNT(*) FROM transacties
                    WHERE datum = ? AND rekening = ? AND bedrag = ? AND omschrijving = ? AND gebruiker_id = ?
                    """,
                    (
                        datum_str,
                        row["rekening"],
                        row["bedrag"],
                        row["omschrijving"],
                        self.gebruiker_id,
                    ),
                    fetch=True,
                )

                if bestaande[0][0] == 0:
                    categorie = self.categorizer.categorize(
                        row.get("naam", ""), row["omschrijving"]
                    )

                    if not categorie:
                        ongecategoriseerd.append(
                            {
                                "naam": row.get("naam", ""),
                                "omschrijving": row["omschrijving"],
                                "rekening": row["rekening"],
                                "tegenrekening": row["tegenrekening"],
                                "bedrag": row["bedrag"],
                                "datum": datum_str,
                                "row_data": row,
                            }
                        )
                        categorie = "Ongecategoriseerd"

                    self.db.execute(
                        """
                        INSERT INTO transacties
                        (datum, rekening, tegenrekening, naam, omschrijving, bedrag, saldo_voor, valuta, categorie, rekeningtype, gebruiker_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            datum_str,
                            row["rekening"],
                            row.get("tegenrekening", ""),
                            row.get("naam", ""),
                            row["omschrijving"],
                            row["bedrag"],
                            row.get("saldo_voor", 0),
                            row.get("valuta", "EUR"),
                            categorie,
                            row["rekeningtype"],
                            self.gebruiker_id,
                        ),
                    )
                    nieuwe_transacties += 1
                else:
                    duplicaten += 1

            print(f"  ✓ {nieuwe_transacties} nieuwe transacties geïmporteerd")
            if duplicaten > 0:
                print(f"  ! {duplicaten} duplicaten overgeslagen")
            total_imported += nieuwe_transacties

        if ongecategoriseerd:
            logger.info(
                "%d transacties vereisen handmatige categorisatie",
                len(ongecategoriseerd),
            )

        logger.info("Import voltooid: %d nieuwe transacties", total_imported)

        return total_imported, ongecategoriseerd

    @staticmethod
    def get_uncategorized_prompt(item, alle_categorieën):
        """Genereer prompt tekst voor een ongecategoriseerde transactie.

        Deze methode is statisch zodat CLI en GUI deze kunnen gebruiken
        voor interactieve categorisatie zonder directe input() aanroepen.
        """
        regel = []
        regel.append("=" * 60)
        regel.append(f"Datum:         {item['datum']}")
        regel.append(f"Rekening:      {item['rekening']}")
        regel.append(f"Tegenrekening: {item['tegenrekening']}")
        regel.append(f"Naam:          {item['naam']}")
        regel.append(f"Omschrijving:  {item['omschrijving']}")
        regel.append(f"Bedrag:        €{item['bedrag']:.2f}")

        if item["bedrag"] > 0:
            relevante_categorieën = [c for c in alle_categorieën if c[1] == "inkomsten"]
            regel.append("\nBeschikbare INKOMSTEN categorieën:")
        else:
            relevante_categorieën = [c for c in alle_categorieën if c[1] == "uitgaven"]
            regel.append("\nBeschikbare UITGAVEN categorieën:")

        for i, (cat_naam, cat_type, cat_desc) in enumerate(relevante_categorieën, 1):
            regel.append(f"{i:2d}. {cat_naam} ({cat_type})")

        return "\n".join(regel), relevante_categorieën

    def handle_uncategorized_interactive(self, ongecategoriseerd):
        """Interactieve categorisatie van ongecategoriseerde transacties.

        Deze methode wordt alleen door CLI gebruikt.
        Retourneert het aantal succesvol gecategoriseerde transacties.
        """
        print(f"\n=== HANDMATIGE CATEGORISATIE VEREIST ===")
        print(f"{len(ongecategoriseerd)} transacties vereisen handmatige categorisatie")

        alle_categorieën = self.db.get_categories(self.gebruiker_id)

        print("\nOpties bij elke transactie:")
        print("- Voer nummer in voor categorie")
        print("- 'n' voor nieuwe categorie maken")
        print("- 's' om te skippen (blijft ongecategoriseerd)")
        print("- 'q' om te stoppen met categoriseren")

        for item in ongecategoriseerd:
            prompt_text, relevante_categorieën = self.get_uncategorized_prompt(
                item, alle_categorieën
            )
            print(f"\n{prompt_text}")

            while True:
                keuze = input("\nCategorie keuze: ").strip().lower()

                if keuze == "q":
                    print("Categorisatie gestopt.")
                    return

                if keuze == "s":
                    break

                if keuze == "n":
                    nieuwe_cat = self.categorizer.create_new_category()
                    if nieuwe_cat:
                        self.categorizer.update_transaction_category(item, nieuwe_cat)
                        if (
                            input(
                                "Wilt u een regel toevoegen voor toekomstige herkenning? (j/n): "
                            ).lower()
                            == "j"
                        ):
                            zoekterm = input("Zoekterm: ").strip()
                            if zoekterm:
                                self.categorizer.add_categorization_rule(
                                    zoekterm, nieuwe_cat
                                )
                    break

                try:
                    index = int(keuze) - 1
                    if 0 <= index < len(relevante_categorieën):
                        gekozen_categorie = relevante_categorieën[index][0]
                        self.categorizer.update_transaction_category(
                            item, gekozen_categorie
                        )
                        if (
                            input(
                                "Wilt u een regel toevoegen voor toekomstige herkenning? (j/n): "
                            ).lower()
                            == "j"
                        ):
                            zoekterm = input("Zoekterm: ").strip()
                            if zoekterm:
                                self.categorizer.add_categorization_rule(
                                    zoekterm, gekozen_categorie
                                )
                        break
                    print("Ongeldig nummer.")
                except ValueError:
                    print("Ongeldige invoer.")
