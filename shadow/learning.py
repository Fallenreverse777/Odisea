"""Matching questions to things Shadow has learned, without any AI.

Shadow compares the meaningful words in a question with the words in each
thing it has learned. Rare words (like "gluten") count more than common ones
(like "bread"), and small differences in wording ("prices"/"price") are ignored.
A learned question can list alternative phrasings separated by "|".
"""


from __future__ import annotations
import math
import re
import unicodedata

# Words that carry no meaning for matching (English + Spanish).
STOPWORDS = set("""
a an the is are was were be been am do does did can could would will shall should may might must
i you we they he she it me my your our their its this that these those there here what which who whom
when where why how to of in on at for from by with about as and or but if so not no yes any some
please hi hello hey thanks thank just also too very really get got have has had
el la los las un una unos unas de del al y o que en es son por para con se su sus lo le les mi tu
hay como cuando donde quien cual muy mas ya si no pero porque hola gracias usted ustedes vosotros
whats hows wheres whos im ive id dont doesnt isnt arent s t m ll re ve d own need want like would could
""".split())

# Words that mean the same thing (or are spelled differently) count as one word.
SYNONYMS = {
    "favourite": "favorite", "fav": "favorite", "fave": "favorite",
    "film": "movie", "films": "movie", "movies": "movie",
    "colour": "color", "colours": "color", "colors": "color",
    "created": "made", "create": "made", "creator": "made", "built": "made", "build": "made",
    "make": "made", "wrote": "made", "programmed": "made",
    "cost": "price", "costs": "price", "prices": "price", "fee": "price", "fees": "price", "charge": "price",
    "delivery": "deliver", "delivering": "deliver", "deliveries": "deliver", "ship": "deliver", "shipping": "deliver",
    "booking": "book", "reserve": "book", "reservation": "book", "appointment": "book",
    "payment": "pay", "paying": "pay", "kids": "children", "kid": "children", "child": "children",
    "dogs": "dog", "pets": "pet", "wifi": "internet", "wi": "internet",
    "song": "music", "songs": "music", "band": "music",
    "hourly": "hour", "hours": "hour", "assemble": "assembly", "assembling": "assembly", "build": "made",
    "fix": "repair", "fixing": "repair", "repairs": "repair", "mend": "repair",
    "install": "installation", "installing": "installation", "fit": "installation", "fitting": "installation",
    "haircut": "cut", "trim": "cut", "mens": "men", "womens": "women", "ladies": "women", "gents": "men",
    "cleaning": "clean", "cleaner": "clean", "tyres": "tyre", "tires": "tyre", "tire": "tyre",
    "vaccine": "vaccination", "vaccines": "vaccination", "jab": "vaccination", "shots": "vaccination",
    "neuter": "neutering", "spay": "neutering", "castration": "neutering",
}


def normalise(text: str) -> str:
    """Lowercase, strip accents ("miércoles" -> "miercoles"), straighten apostrophes."""
    text = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    return "".join(c for c in text if not unicodedata.combining(c))


def stem(word: str) -> str:
    """Very rough stemming so "prices"/"price" and "opening"/"open" match."""
    if len(word) > 6 and word.endswith("ing"):
        return word[:-3]
    if word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]            # boxes -> box, dishes -> dish
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]            # prices -> price, baguettes -> baguette
    return word


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", normalise(text))
    meaningful = {stem(SYNONYMS.get(w, w)) for w in words if w not in STOPWORDS}
    # A question made only of common words ("how are you") still needs something to match on.
    return meaningful or {stem(SYNONYMS.get(w, w)) for w in words}


def best_match(entries: list[dict], question: str) -> tuple[float, dict | None]:
    """Find the entry (with a "q" field) closest to `question`. Score runs 0 to 1."""
    asked = tokens(question)
    if not entries or not asked:
        return 0.0, None

    phrasings = [(e, tokens(p)) for e in entries for p in e["q"].split("|") if p.strip()]
    doc_count: dict[str, int] = {}
    for _, words in phrasings:
        for w in words:
            doc_count[w] = doc_count.get(w, 0) + 1
    idf = {w: math.log(1 + len(phrasings) / n) for w, n in doc_count.items()}

    best_score, best = 0.0, None
    for entry, words in phrasings:
        shared = asked & words
        if not words or not shared:
            continue
        # How much of the learned question was covered, and how much of the new one was explained.
        coverage = sum(idf[w] for w in shared) / sum(idf[w] for w in words)
        precision = len(shared) / len(asked)
        # Both must be high: "capital of Spain" must not match "capital of France".
        score = coverage * (0.5 + 0.5 * precision)
        if score > best_score:
            best_score, best = score, entry
    return best_score, best


TEACH_PATTERNS = [
    # when I say good night, say sleep well  /  if someone asks "do you deliver?" answer "no, sorry"
    re.compile(r"^(?:when|if|whenever)\s+(?:i|someone|somebody|anyone|a customer|customers|people|they)\s+"
               r"(?:says|say|asks|ask|types|type|writes|write)(?:\s+(?:me|you))?\s*[:,]?\s*"
               r"[\"'“]?(?P<q>.+)[\"'”]?\s*[,;]?\s*(?:then\s+)?(?:you\s+)?"
               r"(?:say|answer|reply|respond|tell (?:them|me|him|her))(?:\s+with)?\s*[:,]?\s*[\"'“]?(?P<a>.+?)[\"'”]?$",
               re.IGNORECASE),
    # learn: do you deliver = no, sorry
    re.compile(r"^(?:learn|teach|teach you)\s*[:,]?\s*(?P<q>.+?)\s*(?:=|->|=>)\s*(?P<a>.+)$", re.IGNORECASE),
]


def parse_teaching(text: str) -> tuple[str, str] | None:
    """Spot "when I say X, say Y" style teaching. Returns (question, answer) or None."""
    text = " ".join(text.split())
    for pattern in TEACH_PATTERNS:
        m = pattern.match(text)
        if m:
            question = re.sub(r"^(about|for)\s+|[\s,;]+(you|then)$", "", m.group("q").strip(" \"'“”,;"), flags=re.I)
            answer = m.group("a").strip(" \"'“”")
            if question.strip(" \"'“”,;") and answer:
                return question.strip(" \"'“”,;"), answer
    return None


def add_or_update(entries: list[dict], question: str, answer: str) -> list[dict]:
    """Learn a question/answer. If the same question was learned before, replace its answer."""
    key = normalise(question).strip(" ?!.")
    kept = [e for e in entries if normalise(e["q"]).strip(" ?!.") != key]
    return kept + [{"q": question, "a": answer}]
