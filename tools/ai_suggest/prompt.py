"""Prompts voor het lokale model. Er gaan nooit IBAN's naar het model."""

import re

from tools.ai_common.grouping import group_key, is_uncategorized, sign_type

MAX_FEWSHOT = 15
MAX_SAMPLES = 3
MAX_TEXT = 120

# IBAN in elke vorm die na het samenvouwen van witruimte overblijft: 2 letters,
# 2 cijfers, dan 11-30 alfanumeriek, met hooguit één spatie/punt/streepje ertussen.
# Grenzen aan beide kanten (anders wordt gewone tekst als 'Factuur 2026-00123 …'
# gemaskeerd), met één uitzondering vooraan: direct na 'IBAN' (vastgeplakt 'IBANNL00…').
IBAN_RE = re.compile(
    r"(?:(?<=IBAN)|(?<![A-Z0-9]))[A-Z]{2}[ .\-]?\d{2}(?:[ .\-]?[A-Z0-9]){11,30}(?![A-Z0-9])",
    re.IGNORECASE,
)
# Een echte IBAN heeft ≥ 10 cijfers (NL: 2 controle + 10 rekening; andere landen meer).
# Kandidaten met minder cijfers zijn gewone tekst, bv. 'AH to go 1418 Amsterdam'.
IBAN_MIN_DIGITS = 10


def _mask_iban(match):
    text = match.group(0)
    if sum(ch.isdigit() for ch in text) >= IBAN_MIN_DIGITS:
        return "[IBAN]"
    return text

SYSTEM_PROMPT = (
    "Je categoriseert Nederlandse banktransacties voor een huishoudboekje.\n"
    "Kies precies één categorie uit de lijst met toegestane categorieën.\n"
    "Stel ook een zoekterm voor: een kort, specifiek stukje tekst in kleine letters, "
    "zonder cijfers, dat letterlijk in de naam of omschrijving van deze transacties staat "
    "en waarmee toekomstige transacties van dezelfde tegenpartij herkend worden. "
    "Gebruik bij voorkeur de naam van de tegenpartij, nooit een algemeen woord.\n"
    "Geef je zekerheid als getal tussen 0 en 1."
)


def scrub(text):
    """Vervang IBAN's door [IBAN] en kort lange teksten in.

    Eerst witruimte (tabs, dubbele spaties, NBSP) samenvouwen, dan maskeren:
    andersom zou een IBAN met rare witruimte het patroon ontlopen.
    """
    text = " ".join(str(text or "").split())
    text = IBAN_RE.sub(_mask_iban, text)
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"
    return text


def fewshot_examples(transactions):
    """Tot 15 al gecategoriseerde voorbeelden, één per tegenpartij, recentste eerst.

    `transactions` komt al gesorteerd op datum aflopend uit de database.
    """
    seen = set()
    examples = []
    for tx in transactions:
        if is_uncategorized(tx.categorie):
            continue
        key = group_key(tx.naam, tx.omschrijving)
        if not key or key in seen:
            continue
        seen.add(key)
        examples.append(
            {
                "naam": scrub(tx.naam) or "(geen naam)",
                "omschrijving": scrub(tx.omschrijving),
                "type": sign_type(tx.bedrag),
                "categorie": tx.categorie,
            }
        )
        if len(examples) >= MAX_FEWSHOT:
            break
    return examples


def build_messages(group, allowed, examples):
    system = SYSTEM_PROMPT
    if examples:
        lines = [
            f"- {ex['naam']} | {ex['omschrijving']} | {ex['type']} → {ex['categorie']}"
            for ex in examples
        ]
        system += "\n\nZo heeft de gebruiker eerder gecategoriseerd:\n" + "\n".join(lines)

    samples = "\n".join(f"- {scrub(s)}" for s in group["samples"]) or "- (geen)"
    user = (
        f"Tegenpartij: {scrub(group['naam']) or '(geen naam)'}\n"
        f"Type: {group['type']}\n"
        f"Aantal transacties: {group['aantal']}\n"
        f"Voorbeeldomschrijvingen:\n{samples}\n"
        f"Toegestane categorieën: {', '.join(allowed)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def response_schema(allowed):
    return {
        "type": "object",
        "properties": {
            "categorie": {"type": "string", "enum": list(allowed)},
            "zoekterm": {"type": "string"},
            "zekerheid": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["categorie", "zoekterm", "zekerheid"],
        "additionalProperties": False,
    }
