"""To-do list and reminders for the rule-based brain."""


from __future__ import annotations
import re
from datetime import datetime, timedelta

from .memory import Memory

# ---------------------------------------------------------------------------
# To-do list  (stored in the profile as a list of strings)
# ---------------------------------------------------------------------------


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))


def add_todo(m, text, mem: Memory):
    item = m.group("item").strip(" .")
    if not item:
        return None
    count = mem.update("todos", lambda todos: (todos + [item], len(todos) + 1), [])
    return f"Added to your list: {item}. That's {count} thing{'s' if count != 1 else ''} on it."


def show_todos(m, text, mem: Memory):
    todos = mem.get("todos", [])
    if not todos:
        return "Your list is empty. Nice."
    return "Here's your list:\n" + _numbered(todos)


def _find(todos: list[str], what: str) -> int | None:
    """Find a to-do by its number ("2") or by words in it ("milk")."""
    what = what.strip(" .")
    if what.isdigit():
        i = int(what) - 1
        return i if 0 <= i < len(todos) else None
    for i, item in enumerate(todos):
        if what in item.lower():
            return i
    return None


def finish_todo(m, text, mem: Memory):
    def change(todos):
        i = _find(todos, m.group("what"))
        if i is None:
            return todos, None
        return todos[:i] + todos[i + 1:], todos[i]

    done = mem.update("todos", change, [])
    if done is None:
        return "I couldn't find that on your list. Say 'show my list' to see the numbers."
    left = len(mem.get("todos", []))
    return f"Done: {done}. " + (f"{left} left." if left else "Your list is clear!")


def clear_todos(m, text, mem: Memory):
    mem.set("todos", [])
    return "List cleared."


# ---------------------------------------------------------------------------
# Reminders  (stored as {"text": ..., "due": "2026-10-11T18:30:00"})
# ---------------------------------------------------------------------------

UNITS = {"sec": 1, "second": 1, "min": 60, "minute": 60, "hour": 3600, "hr": 3600, "day": 86400}
NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "five": 5, "ten": 10,
                "fifteen": 15, "twenty": 20, "thirty": 30, "half an": 0.5}

IN_TIME = re.compile(r"\bin (?P<n>\d+|half an|a|an|one|two|three|five|ten|fifteen|twenty|thirty) "
                     r"(?P<unit>sec|second|min|minute|hour|hr|day)s?\b")
AT_TIME = re.compile(r"\b(?P<tomorrow>tomorrow )?(at )?(?P<h>\d{1,2})(:(?P<m>\d{2}))? ?(?P<ampm>am|pm)\b"
                     r"|\b(?P<tomorrow2>tomorrow )?at (?P<h2>\d{1,2})(:(?P<m2>\d{2}))?\b")
TOMORROW = re.compile(r"\btomorrow\b")


def parse_when(text: str, now: datetime) -> tuple[datetime | None, str]:
    """Find a time in `text`. Returns (when, text with the time removed)."""
    if m := IN_TIME.search(text):
        n = m.group("n")
        amount = float(n) if n.isdigit() else NUMBER_WORDS[n]
        when = now + timedelta(seconds=amount * UNITS[m.group("unit")])
        return when, text[:m.start()] + text[m.end():]

    if m := AT_TIME.search(text):
        hour = int(m.group("h") or m.group("h2"))
        minute = int(m.group("m") or m.group("m2") or 0)
        ampm = m.group("ampm")
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None, text
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if m.group("tomorrow") or m.group("tomorrow2") or TOMORROW.search(text):
            when += timedelta(days=1)
        elif when <= now:  # that time already passed today: means tomorrow
            when += timedelta(days=1)
        rest = TOMORROW.sub("", text[:m.start()] + text[m.end():])
        return when, rest

    if TOMORROW.search(text):
        when = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return when, TOMORROW.sub("", text)

    return None, text


def describe(when: datetime, now: datetime) -> str:
    if when.date() == now.date():
        day = "today"
    elif when.date() == (now + timedelta(days=1)).date():
        day = "tomorrow"
    else:
        day = f"on {when:%A %d %B}"
    return f"{day} at {when:%H:%M}"


def add_reminder(m, text, mem: Memory):
    now = datetime.now()
    when, task = parse_when(m.group("rest"), now)
    task = re.sub(r"^\s*(to|that|about)\s+", "", " ".join(task.split())).strip(" .")
    if when is None:
        return "When should I remind you? Try 'remind me to call mom in 20 minutes' or '... at 6pm'."
    if not task:
        return "What should I remind you about?"
    reminder = {"text": task, "due": when.isoformat(timespec="seconds")}
    mem.update("reminders", lambda rs: (sorted(rs + [reminder], key=lambda r: r["due"]), None), [])
    return f"Okay, I'll remind you to {task} {describe(when, now)}."


def show_reminders(m, text, mem: Memory):
    reminders = mem.get("reminders", [])
    if not reminders:
        return "You don't have any reminders."
    now = datetime.now()
    lines = [f"{r['text']}, {describe(datetime.fromisoformat(r['due']), now)}" for r in reminders]
    return "Your reminders:\n" + _numbered(lines)


def cancel_reminder(m, text, mem: Memory):
    def change(reminders):
        i = _find([r["text"].lower() for r in reminders], m.group("what"))
        if i is None:
            return reminders, None
        return reminders[:i] + reminders[i + 1:], reminders[i]

    gone = mem.update("reminders", change, [])
    if gone is None:
        return "I couldn't find that reminder. Say 'show my reminders' to see the numbers."
    return f"Cancelled: {gone['text']}."


def pop_due_reminders(mem: Memory) -> list[str]:
    """Take every reminder whose time has come (so it's only shown once)."""
    now = datetime.now().isoformat(timespec="seconds")

    def change(reminders):
        due = [r for r in reminders if r["due"] <= now]
        return [r for r in reminders if r["due"] > now], due

    return [f"⏰ Reminder: {r['text']}" for r in mem.update("reminders", change, [])]


PLANNER_RULES = [
    (r"^remind me (?P<rest>.+)", add_reminder),
    (r"\b(show|list|what are) (me )?my reminders\b|^reminders$", show_reminders),
    (r"^(cancel|delete|remove) (the )?reminder (?P<what>.+)", cancel_reminder),
    (r"^(add|put) (?P<item>.+?) (to|on) (my|the) (to-?do |shopping )?list$", add_todo),
    (r"^(to-?do|add to-?do|new to-?do)[: ]+(?P<item>.+)", add_todo),
    (r"\b(show|what'?s on|what is on|read) (me )?my (to-?do |shopping )?list\b|^(my )?(to-?dos?|list)$", show_todos),
    (r"^(clear|empty|delete) my (to-?do |shopping )?list$", clear_todos),
    (r"^(done|finished|i did|i finished|tick off|cross off|check off|remove)[: ]+(?P<what>.+?)( from my list)?$", finish_todo),
]
