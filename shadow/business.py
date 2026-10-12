"""Shadow for a business: answers customer questions from what the owner teaches it.

Everything Shadow knows lives in data/business.json (copied from
business.example.json the first time). The owner edits it on the admin page.

How a customer question is answered:
  1. Emergencies first ("burst pipe", "my dog ate chocolate"): safety steps + phone.
  2. If the customer is in the middle of a booking request, continue it.
  3. If it closely matches one of the owner's FAQs, use that answer.
  4. Otherwise, try the built-in rules (hours, area, address, contact, prices).
  5. "Can someone come out?", "book", "quote": start a booking/call-back request.
  6. Otherwise, use a FAQ that matches loosely.
  7. Otherwise, save the question as "unanswered" so the owner can answer it.
     Next time, Shadow knows.

Templates for different trades live in templates/*.json.
"""

import json
import random
import re
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .learning import add_or_update, best_match, normalise, tokens

EXAMPLE = config.ROOT / "business.example.json"
TEMPLATES = config.ROOT / "templates"
# Fields a template sets. Name, contact details and address are kept.
TEMPLATE_FIELDS = ["about", "hours", "service_area", "bookings", "booking_label", "booking_question",
                   "items", "faqs", "emergencies"]
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

    def add_request(self, request: dict) -> dict:
        request = {"id": uuid.uuid4().hex[:8], "status": "new",
                   "time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **request}
        with self.lock:
            self.data.setdefault("requests", []).append(request)
            del self.data["requests"][:-500]
            self.save()
        return request

    def set_request_status(self, request_id: str, status: str | None) -> None:
        """Mark a request "new" or "done", or delete it (status None)."""
        with self.lock:
            requests = self.data.get("requests", [])
            if status is None:
                self.data["requests"] = [r for r in requests if r["id"] != request_id]
            else:
                for r in requests:
                    if r["id"] == request_id:
                        r["status"] = status
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
        "type": s(data.get("type"), 50),
        "service_area": s(data.get("service_area"), 500),
        "bookings": bool(data.get("bookings", False)),
        "booking_label": s(data.get("booking_label"), 60) or "Request a booking",
        "booking_question": s(data.get("booking_question"), 300) or "What do you need?",
        "emergency_phone": s(data.get("emergency_phone"), 50),
        "emergencies": [{"keywords": s(e.get("keywords"), 1000), "message": s(e.get("message"))}
                        for e in (data.get("emergencies") or [])[:50] if s(e.get("keywords")) and s(e.get("message"))],
        "unanswered": [{"q": s(u.get("q"), 500), "count": int(u.get("count") or 1), "time": s(u.get("time"), 40)}
                       for u in (data.get("unanswered") or [])[-200:] if s(u.get("q"))],
        "requests": [{k: s(r.get(k), 1000) for k in ("id", "name", "phone", "details", "when", "time", "status")}
                     for r in (data.get("requests") or [])[-500:] if s(r.get("id"))],
    }


def list_templates() -> list[dict]:
    return [{"id": f.stem, "label": json.loads(f.read_text(encoding="utf-8"))["label"]}
            for f in sorted(TEMPLATES.glob("*.json"))]


def template(template_id: str) -> dict | None:
    path = TEMPLATES / f"{template_id}.json"
    if not re.fullmatch(r"[a-z0-9_]+", template_id) or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"type": data["label"], **{k: data[k] for k in TEMPLATE_FIELDS if k in data}}


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
    """The products/services that match the question best ("men's cut" -> Men's cut, not every cut)."""
    asked = tokens(question)
    scored = [(len(tokens(i["name"]) & asked), i) for i in kb["items"]]
    best = max((n for n, _ in scored), default=0)
    return [i for n, i in scored if n and n == best]


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


def emergency_answer(kb: dict, text: str) -> str | None:
    """Urgent problems get safety steps and the phone number straight away."""
    asked = tokens(text)
    phone = kb.get("emergency_phone") or kb["phone"]
    call = f"\n\n📞 Call us now: {phone}" if phone else ""
    for emergency in kb.get("emergencies", []):
        for phrase in emergency["keywords"].split("|"):
            words = tokens(phrase)
            if words and words <= asked:  # every word of the phrase was said
                return "⚠️ " + emergency["message"] + call
    return None


def service_area_answer(kb: dict, text: str) -> str | None:
    t = normalise(text)
    area = kb.get("service_area", "")
    m = re.search(r"\b(?:do you (?:cover|come to|go to|work in|serve|travel to)|can you come to|"
                  r"service area|(?:which |what )?areas? (?:do you )?(?:cover|serve|work in)|which areas|what areas|where do you work|"
                  r"llegais a|trabajais en|zona)\b\s*(?P<place>[a-z .'-]*)", t)
    if not m or not area:
        return None
    place = re.sub(r"^(the |in |to |my )+", "", m.group("place")).strip(" ?.!")
    if place and len(place) > 2 and place in normalise(area):
        return f"Yes, we cover {place.title()}."
    reply = f"We cover: {area}."
    if place and len(place) > 2:
        reply += f" If you're not sure whether {place.title()} is included, send us your address and we'll check."
    return reply


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
    if re.search(r"\b(open|close|closed|closing|hours|opening|available|horario|abierto|abren|cerrado|cierran|abre|cierra)\b", t):
        day = next((d for w, d in DAY_ALIASES.items() if re.search(rf"\b{w}\b", t)), None)
        if day is None and re.search(r"\b(tomorrow|manana)\b", t):
            day = (now.weekday() + 1) % 7
        if day is not None:
            hours = describe_day(kb, day)
            return f"On {DAYS[day].title()} we're {hours}." if hours == "closed" else f"On {DAYS[day].title()} we're open {hours}."
        if re.search(r"\b(now|right now|currently|still|ahora|today|hoy)\b", t) or re.match(r"\W*(are|is) (you|it|the \w+) open", t):
            return open_now(kb, now) + f"\nToday's hours: {describe_day(kb, now.weekday())}."
        return week_hours(kb)

    # "It's urgent!" with no specific emergency recognised
    phone = kb.get("emergency_phone") or kb["phone"]
    if re.search(r"\b(emergency|urgent|asap|emergencia|urgente)\b", t) and phone:
        return f"If it's an emergency, please call us now on {phone} so we can help straight away."

    # Location
    if re.search(r"\b(where|address|located|location|directions|find you|direccion|donde|ubicacion|como llego)\b", t):
        if kb["address"]:
            return f"We're at {kb['address']}."
        if kb.get("service_area"):
            return f"We come to you! We cover: {kb['service_area']}."

    # Products / services / prices
    asking_price = re.search(r"\b(how much|price|prices|cost|costs|precio|precios|cuanto|cuesta|vale)\b", t)
    asking_have = re.search(r"\b(do you (have|sell|do|make|offer|fix|repair|install)|is there|"
                            r"can you (do|fix|repair|install|assemble|make|help with|clean|cut)|tienen|teneis|venden|hacen)\b", t)
    asking_list = re.search(r"\b(menu|services|products|what do you (sell|offer|have|do|make)|price list|carta|servicios|productos)\b", t)
    items = find_items(kb, text)
    if items and asking_have and not asking_price:
        # "Do you make vegan cakes?" mentions "cake", but "vegan" isn't covered: let the FAQs
        # (or the owner) answer instead of listing the plain cake.
        # A question that names the whole product ("assemble IKEA furniture" -> Furniture assembly) is fine.
        asked = tokens(text)
        fully_named = any(tokens(i["name"]) <= asked for i in items)
        covered = set().union(*(tokens(i["name"]) for i in items)) | FILLER
        if not fully_named and asked - covered:
            items = []
    if items and asking_have and not asking_price:
        return "Yes!\n" + "\n".join(item_line(i) for i in items)
    if items and asking_price:
        return "\n".join(item_line(i) for i in items)
    if asking_list or (asking_price and not items):
        if kb["items"]:
            return "Here's what we offer:\n" + "\n".join(item_line(i) for i in kb["items"])

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

    # About
    if re.search(r"\b(who are you|what is this|about you|tell me about|what kind of|quienes sois|que sois)\b", t) and kb["about"]:
        return kb["about"]

    return None


# ---------------------------------------------------------------------------
# The brain
# ---------------------------------------------------------------------------

BOOK = re.compile(r"\b(book|booking|appointment|reserve|reservation|schedule|quote|estimate|call me back|callback|"
                  r"call back|come out|come over|come round|come and|come today|come tomorrow|send someone|"
                  r"visit|cita|reservar|presupuesto|llamadme|que venga)\b")
CANCEL = re.compile(r"\W*(cancel|stop|never ?mind|forget it|no thanks|cancelar|dejalo)\W*")
SESSION_TIMEOUT = 30 * 60  # a half-finished booking is forgotten after 30 minutes


class BusinessBrain:
    def __init__(self, kb: KnowledgeBase, on_request: Callable[[dict], None] | None = None):
        self.kb = kb
        self.on_request = on_request  # called when a customer sends a booking request
        self.sessions: dict[str, dict] = {}
        self.lock = threading.Lock()

    # --- answering --------------------------------------------------------
    def lookup(self, question: str, now: datetime | None = None) -> str | None:
        """The answer if Shadow knows it, otherwise None. Never starts a booking."""
        now = now or datetime.now()
        data = self.kb.data

        urgent = emergency_answer(data, question) or service_area_answer(data, question)
        if urgent:
            return urgent

        score, faq = best_faq(data, question)
        if faq and score >= 0.7:
            return faq["a"]

        reply = builtin_answer(data, question, now)
        if reply:
            return reply

        if faq and score >= 0.5:
            return faq["a"]
        return None

    def answer(self, question: str, session: str = "", now: datetime | None = None) -> str:
        """Answer a customer. Unknown questions are saved for the owner to answer."""
        data = self.kb.data
        state = self._session(session)

        if state and not emergency_answer(data, question):
            return self._continue_booking(session, state, question)

        if data.get("bookings") and session and BOOK.search(normalise(question)):
            score, faq = best_faq(data, question)
            # "Do you give free quotes?" is a question for the FAQs; "book an appointment" is a request.
            asking_about = re.match(r"\W*(do|does|are|is|how|what|why|when|which)\b", normalise(question))
            if not (faq and score >= 0.7 and asking_about):
                return self._start_booking(session)

        reply = self.lookup(question, now)
        if reply:
            return reply

        self.kb.log_unanswered(question)
        if data.get("bookings") and session:
            return ("Sorry, I don't know that one yet. I've passed your question on to the team. "
                    "Would you like them to call you back? Just say “call me back”.")
        lines = contact_lines(data)[:2]
        reach = (" In the meantime you can reach us here:\n" + "\n".join(lines)) if lines else ""
        return f"Sorry, I don't know that one yet. I've passed your question on to the team.{reach}"

    # --- booking / call-back requests -------------------------------------
    def _session(self, session: str) -> dict | None:
        with self.lock:
            cutoff = time.time() - SESSION_TIMEOUT
            for sid in [k for k, v in self.sessions.items() if v["ts"] < cutoff]:
                del self.sessions[sid]
            return self.sessions.get(session)

    def _start_booking(self, session: str) -> str:
        with self.lock:
            if len(self.sessions) > 1000:  # protect memory from abuse
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[session] = {"step": "name", "data": {}, "ts": time.time()}
        return (f"Sure! I'll take a few details and the {self.kb.data['name']} team will contact you to confirm. "
                "What's your name? (You can say “cancel” at any time.)")

    def _continue_booking(self, session: str, state: dict, text: str) -> str:
        text = " ".join(text.split())[:500]
        state["ts"] = time.time()
        info = state["data"]
        if CANCEL.fullmatch(normalise(text)):
            with self.lock:
                self.sessions.pop(session, None)
            return "No problem, I've cancelled that. Anything else I can help with?"

        if state["step"] == "name":
            info["name"] = re.sub(r"^(my name is|i'?m|i am|it'?s|this is|me llamo|soy)\s+", "", text, flags=re.I)[:60]
            state["step"] = "phone"
            return f"Thanks, {info['name']}. What's the best phone number to reach you?"

        if state["step"] == "phone":
            if len(re.sub(r"\D", "", text)) < 6:
                return "That doesn't look like a phone number. Could you type it again?"
            info["phone"] = re.sub(r"^[^+\d(]*", "", text)[:30]
            state["step"] = "details"
            return self.kb.data.get("booking_question") or "What do you need?"

        if state["step"] == "details":
            info["details"] = text
            state["step"] = "when"
            return "When would suit you best? (e.g. “tomorrow morning”, “Friday after 5”, “as soon as possible”)"

        # Last step: when
        info["when"] = text
        with self.lock:
            self.sessions.pop(session, None)
        request = self.kb.add_request(info)
        if self.on_request:
            self.on_request(request)
        return (f"Done, thanks {info['name']}! I've sent this to the team:\n"
                f"• {info['details']}\n• When: {info['when']}\n\n"
                f"They'll call you on {info['phone']} to confirm. It's not booked until they do.")


def load(on_request: Callable[[dict], None] | None = None) -> tuple[KnowledgeBase, BusinessBrain]:
    kb = KnowledgeBase(config.DATA_DIR / "business.json")
    kb.data = clean_business(kb.data)  # fill in fields added in newer versions
    return kb, BusinessBrain(kb, on_request)
