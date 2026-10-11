"""Shadow for a business: answers customer questions from what the owner teaches it.

Everything Shadow knows lives in data/business.json (copied from
business.example.json the first time). The owner edits it on the admin page.

How a customer question is answered:
  1. If it closely matches one of the owner's FAQs, use that answer.
  2. Otherwise, try the built-in rules (opening hours, address, contact, prices).
  3. Otherwise, use a FAQ that matches loosely.
  4. Otherwise, save the question as "unanswered" so the owner can answer it.
     Next time, Shadow knows.
"""

import json
import random
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .learning import add_or_update, best_match, normalise, tokens

EXAMPLE = config.ROOT / "business.example.json"
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_ALIASES = {
    "mon": 0, "monday": 0, "lunes": 0, "tue": 1, "tues": 1, "tuesday": 1, "martes": 1,
    "wed": 2, "wednesday": 2, "miercoles": 2, "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "jueves": 3,
    "fri": 4, "friday": 4, "viernes": 4, "sat": 5, "saturday": 5, "sabado": 5,
    "sun": 6, "sunday": 6, "domingo": 6,
}


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

class KnowledgeBase:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def replace(self, new_data: dict) -> None:
        """Save everything from the admin page (keeps unanswered questions it didn't send)."""
        with self.lock:
            self.data = clean_business(new_data)
            self.save()

    def teach(self, question: str, answer: str) -> None:
        """Learn an answer from the owner. Any matching unanswered question is cleared."""
        key = normalise(question).strip(" ?!.")
        with self.lock:
            self.data["faqs"] = add_or_update(self.data["faqs"], question.strip(), answer.strip())
            self.data["unanswered"] = [u for u in self.data.get("unanswered", [])
                                       if normalise(u["q"]).strip(" ?!.") != key]
            self.save()

    def dismiss(self, question: str) -> None:
        """Remove an unanswered question without teaching an answer."""
        key = normalise(question).strip(" ?!.")
        with self.lock:
            self.data["unanswered"] = [u for u in self.data.get("unanswered", [])
                                       if normalise(u["q"]).strip(" ?!.") != key]
            self.save()

    def log_unanswered(self, question: str) -> None:
        key = normalise(question).strip(" ?!.")
        with self.lock:
            for item in self.data.setdefault("unanswered", []):
                if normalise(item["q"]).strip(" ?!.") == key:
                    item["count"] = item.get("count", 1) + 1
                    break
            else:
                self.data["unanswered"].append({
                    "q": question.strip(), "count": 1,
                    "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                })
                del self.data["unanswered"][:-200]  # keep the latest 200
            self.save()


def clean_business(data: dict) -> dict:
    """Keep only the fields Shadow understands, as strings, with sane sizes."""
    def s(value, limit=2000):
        return str(value or "").strip()[:limit]

    hours = data.get("hours") or {}
    return {
        "name": s(data.get("name"), 100) or "Our business",
        "about": s(data.get("about")),
        "address": s(data.get("address"), 300),
        "phone": s(data.get("phone"), 50),
        "email": s(data.get("email"), 100),
        "website": s(data.get("website"), 200),
        "hours": {day: s(hours.get(day), 100) or "closed" for day in DAYS},
        "items": [{"name": s(i.get("name"), 100), "price": s(i.get("price"), 50), "details": s(i.get("details"), 300)}
                  for i in (data.get("items") or [])[:500] if s(i.get("name"))],
        "faqs": [{"q": s(f.get("q"), 500), "a": s(f.get("a"))}
                 for f in (data.get("faqs") or [])[:1000] if s(f.get("q")) and s(f.get("a"))],
        "unanswered": [{"q": s(u.get("q"), 500), "count": int(u.get("count") or 1), "time": s(u.get("time"), 40)}
                       for u in (data.get("unanswered") or [])[-200:] if s(u.get("q"))],
    }


# ---------------------------------------------------------------------------
# Opening hours
# ---------------------------------------------------------------------------

def parse_hours(text: str) -> list[tuple[str, str]]:
    """'08:00-14:00, 17:00-20:30' -> [('08:00','14:00'), ('17:00','20:30')]. 'closed' -> []."""
    return [(f"{int(a):02d}:{b}", f"{int(c):02d}:{d}")
            for a, b, c, d in re.findall(r"(\d{1,2})[:.h](\d{2})\s*[-–to]+\s*(\d{1,2})[:.h](\d{2})", text)]


def describe_day(kb: dict, day: int) -> str:
    slots = parse_hours(kb["hours"].get(DAYS[day], ""))
    if not slots:
        return "closed"
    return " and ".join(f"{a} to {b}" for a, b in slots)


def open_now(kb: dict, now: datetime) -> str:
    today = now.weekday()
    hhmm = now.strftime("%H:%M")
    for start, end in parse_hours(kb["hours"].get(DAYS[today], "")):
        if start <= hhmm < end:
            return f"Yes, we're open right now until {end}."
    # Closed: find when we next open.
    for offset in range(0, 8):
        day = (today + offset) % 7
        for start, _ in parse_hours(kb["hours"].get(DAYS[day], "")):
            if offset == 0 and start <= hhmm:
                continue
            when = "today" if offset == 0 else "tomorrow" if offset == 1 else f"on {DAYS[day].title()}"
            return f"We're closed right now. We open again {when} at {start}."
    return "We're closed at the moment."


def week_hours(kb: dict) -> str:
    return "Our opening hours:\n" + "\n".join(f"{DAYS[d].title()}: {describe_day(kb, d)}" for d in range(7))


# ---------------------------------------------------------------------------
# FAQ matching
# ---------------------------------------------------------------------------

def best_faq(kb: dict, question: str) -> tuple[float, dict | None]:
    return best_match(kb["faqs"], question)


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------

def find_items(kb: dict, question: str) -> list[dict]:
    asked = tokens(question)
    return [i for i in kb["items"] if tokens(i["name"]) & asked]


def item_line(item: dict) -> str:
    line = item["name"]
    if item["price"]:
        line += f": {item['price']}"
    if item["details"]:
        line += f" ({item['details']})"
    return line


def contact_lines(kb: dict) -> list[str]:
    lines = []
    if kb["phone"]:
        lines.append(f"Phone: {kb['phone']}")
    if kb["email"]:
        lines.append(f"Email: {kb['email']}")
    if kb["address"]:
        lines.append(f"Address: {kb['address']}")
    if kb["website"]:
        lines.append(f"Website: {kb['website']}")
    return lines


# Words that don't change what a "do you have ...?" question is about.
FILLER = tokens("much sell offer made buy want order one some any fresh today now still left please also")


def builtin_answer(kb: dict, text: str, now: datetime) -> str | None:
    t = normalise(text)

    if re.fullmatch(r"\W*(hi|hello|hey|hola|buenas|good (morning|afternoon|evening)|buenos dias)\W*", t):
        return f"Hi, welcome to {kb['name']}! How can I help you?"
    if re.fullmatch(r"\W*(thanks|thank you|gracias|cheers|ok|okay|great|perfect|perfecto)\W*", t):
        return random.choice(["You're welcome!", "Happy to help!", "Anytime. See you soon!"])
    if re.fullmatch(r"\W*(bye|goodbye|adios|hasta luego|see you)\W*", t):
        return f"Thanks for visiting {kb['name']}. See you soon!"

    # Opening hours
    if re.search(r"\b(open|close|closed|closing|hours|opening|horario|abierto|abren|cerrado|cierran|abre|cierra)\b", t):
        day = next((d for w, d in DAY_ALIASES.items() if re.search(rf"\b{w}\b", t)), None)
        if day is None and re.search(r"\b(tomorrow|manana)\b", t):
            day = (now.weekday() + 1) % 7
        if day is not None:
            hours = describe_day(kb, day)
            return f"On {DAYS[day].title()} we're {hours}." if hours == "closed" else f"On {DAYS[day].title()} we're open {hours}."
        if re.search(r"\b(now|right now|currently|still|ahora|today|hoy)\b", t) or re.match(r"\W*(are|is) (you|it|the \w+) open", t):
            return open_now(kb, now) + f"\nToday's hours: {describe_day(kb, now.weekday())}."
        return week_hours(kb)

    # Location
    if re.search(r"\b(where|address|located|location|directions|find you|direccion|donde|ubicacion|como llego)\b", t):
        if kb["address"]:
            return f"We're at {kb['address']}."

    # Contact
    if re.search(r"\b(phone|call|number|telephone|telefono|llamar)\b", t) and kb["phone"]:
        return f"You can call us on {kb['phone']}."
    if re.search(r"\b(email|e-mail|mail|correo)\b", t) and kb["email"]:
        return f"Our email is {kb['email']}."
    if re.search(r"\b(website|web|site|pagina)\b", t) and kb["website"]:
        return f"Our website is {kb['website']}."
    if re.search(r"\b(contact|reach you|get in touch|contacto|contactar)\b", t):
        lines = contact_lines(kb)
        if lines:
            return "Here's how to reach us:\n" + "\n".join(lines)

    # Products / services / prices
    asking_price = re.search(r"\b(how much|price|prices|cost|costs|precio|precios|cuanto|cuesta|vale)\b", t)
    asking_have = re.search(r"\b(do you (have|sell|do|make|offer)|is there|tienen|teneis|venden|hacen)\b", t)
    asking_list = re.search(r"\b(menu|services|products|what do you (sell|offer|have|do|make)|price list|carta|servicios|productos)\b", t)
    items = find_items(kb, text)
    if items and asking_have and not asking_price:
        # "Do you make vegan cakes?" mentions "cake", but "vegan" isn't covered: let the FAQs
        # (or the owner) answer instead of listing the plain cake.
        covered = set().union(*(tokens(i["name"]) for i in items)) | FILLER
        if tokens(text) - covered:
            items = []
    if items and (asking_price or asking_have):
        return "\n".join(item_line(i) for i in items)
    if asking_list or (asking_price and not items):
        if kb["items"]:
            return "Here's what we offer:\n" + "\n".join(item_line(i) for i in kb["items"])

    # About
    if re.search(r"\b(who are you|what is this|about you|tell me about|what kind of|quienes sois|que sois)\b", t) and kb["about"]:
        return kb["about"]

    return None


# ---------------------------------------------------------------------------
# The brain
# ---------------------------------------------------------------------------

class BusinessBrain:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def lookup(self, question: str, now: datetime | None = None) -> str | None:
        """The answer if Shadow knows it, otherwise None."""
        now = now or datetime.now()
        data = self.kb.data

        score, faq = best_faq(data, question)
        if faq and score >= 0.7:
            return faq["a"]

        reply = builtin_answer(data, question, now)
        if reply:
            return reply

        if faq and score >= 0.5:
            return faq["a"]
        return None

    def answer(self, question: str, now: datetime | None = None) -> str:
        """Answer a customer. Unknown questions are saved for the owner to answer."""
        reply = self.lookup(question, now)
        if reply:
            return reply
        self.kb.log_unanswered(question)
        lines = contact_lines(self.kb.data)[:2]
        reach = (" In the meantime you can reach us here:\n" + "\n".join(lines)) if lines else ""
        return f"Sorry, I don't know that one yet. I've passed your question on to the team.{reach}"


def load() -> tuple[KnowledgeBase, BusinessBrain]:
    kb = KnowledgeBase(config.DATA_DIR / "business.json")
    return kb, BusinessBrain(kb)
