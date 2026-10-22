"""To-do list and reminders for the rule-based brain.

Supports optional priority (high / medium / low) on both todos and reminders.
"""


from __future__ import annotations
import re
from datetime import datetime, timedelta

from .memory import Memory

# ---------------------------------------------------------------------------
# Priority helpers
# ---------------------------------------------------------------------------

PRIORITY_WORDS = {
    "urgent": "high", "asap": "high", "important": "high", "critical": "high",
    "high": "high", "high priority": "high",
    "medium": "medium", "normal": "medium",
    "low": "low", "later": "low", "someday": "low",
}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _extract_priority(text: str) -> tuple[str, str]:
    """Pull a priority word out of the text if present. Returns (priority, cleaned_text)."""
    low = text.lower()
    for phrase, level in sorted(PRIORITY_WORDS.items(), key=lambda x: -len(x[0])):
        if phrase in low:
            cleaned = re.sub(re.escape(phrase), "", text, count=1, flags=re.I)
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.")
            return level, cleaned
    return "medium", text


def _priority_badge(p: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(p, "🟡")


# ---------------------------------------------------------------------------
# To-do list  (stored as list of {"text": str, "priority": str})
# ---------------------------------------------------------------------------


def _normalise_todos(todos: list) -> list[dict]:
    """Migrate old string todos to the new dict format."""
    out = []
    for t in todos:
        if isinstance(t, str):
            out.append({"text": t, "priority": "medium"})
        else:
            out.append({"text": t.get("text", ""), "priority": t.get("priority", "medium")})
    return out


def _numbered(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        badge = _priority_badge(item.get("priority", "medium"))
        lines.append(f"{i}. {badge} {item['text']}")
    return "\n".join(lines)


def add_todo(m, text, mem: Memory):
    raw = m.group("item").strip(" .")
    if not raw:
        return None
    priority, item = _extract_priority(raw)
    if not item:
        return None

    def change(todos):
        todos = _normalise_todos(todos)
        todos.append({"text": item, "priority": priority})
        # Keep high priority near the top
        todos.sort(key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 1))
        return todos, len(todos)

    count = mem.update("todos", change, [])
    badge = _priority_badge(priority)
    return f"Added to your list: {badge} {item}. That's {count} thing{'s' if count != 1 else ''} on it."


def show_todos(m, text, mem: Memory):
    todos = _normalise_todos(mem.get("todos", []))
    if not todos:
        return "Your list is empty. Nice."
    # Persist migration if needed
    mem.set("todos", todos)
    return "Here's your list:\n" + _numbered(todos)


def _find(todos: list[dict], what: str) -> int | None:
    """Find a to-do by its number ("2") or by words in it ("milk")."""
    what = what.strip(" .")
    if what.isdigit():
        i = int(what) - 1
        return i if 0 <= i < len(todos) else None
    for i, item in enumerate(todos):
        if what.lower() in item["text"].lower():
            return i
    return None


def finish_todo(m, text, mem: Memory):
    def change(todos):
        todos = _normalise_todos(todos)
        i = _find(todos, m.group("what"))
        if i is None:
            return todos, None
        done = todos[i]
        return todos[:i] + todos[i + 1:], done

    done = mem.update("todos", change, [])
    if done is None:
        return "I couldn't find that on your list. Say 'show my list' to see the numbers."
    left = len(mem.get("todos", []))
    return f"Done: {done['text']}. " + (f"{left} left." if left else "Your list is clear!")


def clear_todos(m, text, mem: Memory):
    mem.set("todos", [])
    return "List cleared."


# ---------------------------------------------------------------------------
# Reminders  (stored as {"text": ..., "due": "...", "priority": ...})
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

    priority, task = _extract_priority(task)
    reminder = {"text": task, "due": when.isoformat(timespec="seconds"), "priority": priority}
    mem.update("reminders", lambda rs: (sorted(rs + [reminder], key=lambda r: (r["due"], PRIORITY_ORDER.get(r.get("priority", "medium"), 1))), None), [])
    badge = _priority_badge(priority)
    return f"Okay, I'll remind you to {badge} {task} {describe(when, now)}."


def show_reminders(m, text, mem: Memory):
    reminders = mem.get("reminders", [])
    if not reminders:
        return "You don't have any reminders."
    now = datetime.now()
    lines = []
    for r in reminders:
        badge = _priority_badge(r.get("priority", "medium"))
        lines.append(f"{badge} {r['text']}, {describe(datetime.fromisoformat(r['due']), now)}")
    return "Your reminders:\n" + "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))


def cancel_reminder(m, text, mem: Memory):
    def change(reminders):
        i = _find([{"text": r["text"]} for r in reminders], m.group("what"))
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
        # High priority first
        due.sort(key=lambda r: PRIORITY_ORDER.get(r.get("priority", "medium"), 1))
        return [r for r in reminders if r["due"] > now], due

    return [f"⏰ {_priority_badge(r.get('priority', 'medium'))} Reminder: {r['text']}" for r in mem.update("reminders", change, [])]


# ---------------------------------------------------------------------------
# Lightweight multi-step planner
# ---------------------------------------------------------------------------

def plan_steps(m, text, mem: Memory):
    """Break a complex request into simple sequential steps."""
    goal = m.group("goal").strip(" .")
    if not goal:
        return "What do you want me to help plan?"

    # Very lightweight heuristic breakdown – no LLM required
    steps = []
    low = goal.lower()

    if any(w in low for w in ("launch", "start", "open", "set up", "setup")):
        steps = [
            "Clarify the exact goal and success criteria",
            "List the required materials / accounts / tools",
            "Do the first concrete action",
            "Test that it works",
            "Write down what to do next time",
        ]
    elif any(w in low for w in ("learn", "study", "understand", "master")):
        steps = [
            "Define what 'good enough' looks like",
            "Find one short explanation or tutorial",
            "Practice the smallest possible version",
            "Explain it back in your own words",
            "Apply it to a real task",
        ]
    elif any(w in low for w in ("fix", "fix", "debug", "solve")):
        steps = [
            "Reproduce the problem clearly",
            "Write down what changed recently",
            "Try the simplest possible fix",
            "Check the result",
            "If still broken, gather more evidence",
        ]
    else:
        # Generic breakdown
        steps = [
            f"Clarify exactly what '{goal}' means",
            "Break it into the smallest next action",
            "Do that one action",
            "Check progress and adjust",
            "Repeat until done",
        ]

    lines = [f"Here's a simple plan for: {goal}"]
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")
    lines.append("\nSay 'add … to my list' for any step you want to track.")
    return "\n".join(lines)


PLANNER_RULES = [
    (r"^(plan|help me plan|break down|how (do|can) i) (?P<goal>.+)", plan_steps),
    (r"^remind me (?P<rest>.+)", add_reminder),
    (r"\b(show|list|what are) (me )?my reminders\b|^reminders$", show_reminders),
    (r"^(cancel|delete|remove) (the )?reminder (?P<what>.+)", cancel_reminder),
    (r"^(add|put) (?P<item>.+?) (to|on) (my|the) (to-?do |shopping )?list$", add_todo),
    (r"^(to-?do|add to-?do|new to-?do)[: ]+(?P<item>.+)", add_todo),
    (r"\b(show|what'?s on|what is on|read) (me )?my (to-?do |shopping )?list\b|^(my )?(to-?dos?|list)$", show_todos),
    (r"^(clear|empty|delete) my (to-?do |shopping )?list$", clear_todos),
    (r"^(done|finished|i did|i finished|tick off|cross off|check off|remove)[: ]+(?P<what>.+?)( from my list)?$", finish_todo),
]
