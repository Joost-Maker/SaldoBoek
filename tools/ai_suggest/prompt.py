"""Prompts voor het lokale model (volledige transacties, alleen lokaal)."""

from tools.ai_common.grouping import group_key, is_uncategorized, sign_type

MAX_FEWSHOT = 15
MAX_SAMPLES = 3
MAX_TEXT = 1000

SYSTEM_PROMPT = (
    "Je categoriseert Nederlandse banktransacties voor een huishoudboekje.\n"
    "Kies precies één categorie uit de lijst met toegestane categorieën.\n"
    "Stel ook een zoekterm voor: een kort, specifiek stukje tekst in kleine letters, "
    "zonder cijfers, dat letterlijk in de naam of omschrijving van deze transacties staat "
    "en waarmee toekomstige transacties van dezelfde tegenpartij herkend worden. "
    "Gebruik bij voorkeur de naam van de tegenpartij, nooit een algemeen woord.\n"
    "Geef je zekerheid als getal tussen 0 en 1."
)


def clean(text):
    """Witruimte samenvouwen en extreem lange teksten inkorten.

    Geen maskering: het model draait lokaal (alleen 127.0.0.1) en logt geen
    prompts, dus het krijgt de volledige transactie (PO-besluit 2026-09-18).
    """
    text = " ".join(str(text or "").split())
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
                "naam": clean(tx.naam) or "(geen naam)",
                "omschrijving": clean(tx.omschrijving),
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

    samples = "\n".join(f"- {clean(line)}" for line in group["lines"]) or "- (geen)"
    user = (
        f"Tegenpartij: {clean(group['naam']) or '(geen naam)'}\n"
        f"Type: {group['type']}\n"
        f"Aantal transacties: {group['aantal']}\n"
        f"Voorbeeldtransacties (datum · bedrag · omschrijving):\n{samples}\n"
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
