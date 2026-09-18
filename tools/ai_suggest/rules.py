"""Deterministische controles op voorgestelde zoektermen."""

from tools.ai_common.grouping import is_uncategorized, rule_text

MIN_ZOEKTERM_LENGTH = 4


def validate_zoekterm(term, group_texts):
    """Geldige zoekterm (kleine letters) of None.

    Eisen: ≥ 4 tekens, geen cijfers, en substring van de tekst van élke
    transactie in de groep (anders matcht de regel de groep niet eens).
    """
    if not isinstance(term, str):
        return None
    term = term.strip().lower()
    if len(term) < MIN_ZOEKTERM_LENGTH:
        return None
    if any(ch.isdigit() for ch in term):
        return None
    if not group_texts or not all(term in text for text in group_texts):
        return None
    return term


def choose_zoekterm(model_term, naam, group_texts):
    """(zoekterm, flags).

    PO-besluit (2026-09-18): heeft de groep een tegenpartij-naam van ≥ 4 tekens,
    dan is de zoekterm altijd die volledige naam (cijfers toegestaan: Knab
    schrijft de naam steeds hetzelfde). Algemene modeltermen als 'woning' of
    'salaris' zouden als vaste regel toekomstige transacties verkeerd raken.
    Alleen bij een lege of te korte naam telt de modelterm, met de gewone
    validatie.
    """
    naam_term = (naam or "").strip().lower()
    if len(naam_term) >= MIN_ZOEKTERM_LENGTH:
        return naam_term, []
    term = validate_zoekterm(model_term, group_texts)
    if term:
        return term, []
    return "", ["zoekterm ongeldig"]


def collisions(term, categorie, transactions):
    """Transacties die de term zou raken maar al een andere categorie hebben."""
    hits = [
        tx
        for tx in transactions
        if not is_uncategorized(tx.categorie)
        and tx.categorie != categorie
        and term in rule_text(tx.naam, tx.omschrijving)
    ]
    return hits


def collision_flag(term, categorie, transactions):
    if not term:
        return []
    hits = collisions(term, categorie, transactions)
    if not hits:
        return []
    cats = ", ".join(sorted({tx.categorie for tx in hits}))
    return [f"botsing: {len(hits)} transacties in {cats}"]


def shadow_flag(group_texts, rules):
    """Eerste bestaande regel (in Categorizer-volgorde) die de groep al raakt."""
    for zoekterm in rules:
        if any(zoekterm in text for text in group_texts):
            return [f"al gedekt door regel '{zoekterm}'"]
    return []
