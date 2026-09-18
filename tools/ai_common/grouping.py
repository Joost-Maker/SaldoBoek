"""Groepssleutel en teken: gedeeld door ai_suggest en ai_apply.

Eén bron van waarheid, zodat apply precies dezelfde groepen terugvindt
als suggest in het reviewbestand heeft gezet.
"""

UNCATEGORIZED = "Ongecategoriseerd"


def group_key(naam, omschrijving):
    """Tegenpartij in kleine letters; valt terug op de omschrijving."""
    key = (naam or "").strip().lower()
    if key:
        return key
    return (omschrijving or "").strip().lower()


def sign_type(bedrag):
    """SaldoBoek-regel: bedrag > 0 is inkomsten, anders uitgaven."""
    return "inkomsten" if bedrag is not None and bedrag > 0 else "uitgaven"


def rule_text(naam, omschrijving):
    """De tekst waarin SaldoBoek's Categorizer naar zoektermen zoekt."""
    return f"{naam or ''} {omschrijving or ''}".lower()


def is_uncategorized(categorie):
    return categorie is None or categorie == UNCATEGORIZED
