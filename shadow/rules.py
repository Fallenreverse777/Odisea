"""Shadow's own brain: a loop of if/else rules. No internet, no API.

How it works:
  1. Your message is cleaned up (lowercase, extra spaces removed).
  2. Each rule in RULES is tried in order. A rule is a regex pattern plus a
     function that builds the reply.
  3. The first rule whose pattern matches wins.
  4. If nothing matches, Shadow falls back to a general reply.

To teach Shadow something new, write a function and add it to RULES.
"""

import ast
import operator
import random
import re
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta

from . import config
from .learning import add_or_update, best_match, parse_teaching
from .memory import Memory
from .planner import PLANNER_RULES, pop_due_reminders
from .weather import WEATHER_RULES

# ---------------------------------------------------------------------------
# Word lists
# ---------------------------------------------------------------------------

SAD = {"sad", "down", "depressed", "lonely", "upset", "unhappy", "miserable", "awful", "terrible", "bad", "low", "hurt"}
TIRED = {"tired", "exhausted", "sleepy", "drained", "burnt out", "burned out"}
STRESSED = {"stressed", "anxious", "worried", "nervous", "overwhelmed", "scared", "afraid"}
ANGRY = {"angry", "mad", "furious", "annoyed", "frustrated", "pissed"}
HAPPY = {"happy", "great", "good", "fine", "awesome", "excited", "amazing", "fantastic", "glad", "ok", "okay", "well"}

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I told my computer I needed a break. It said: 'No problem, I'll go to sleep.'",
    "There are 10 kinds of people: those who understand binary and those who don't.",
    "Why did the shadow break up with the light? It needed some space.",
    "A SQL query walks into a bar, goes up to two tables and asks: 'Can I join you?'",
]

# Swapped when Shadow echoes your words back ("I need my keys" -> "you need your keys").
REFLECTIONS = {
    "i": "you", "me": "you", "my": "your", "mine": "yours", "myself": "yourself",
    "am": "are", "i'm": "you're", "i've": "you've", "i'll": "you'll", "i'd": "you'd",
    "you": "I", "your": "my", "yours": "mine", "yourself": "myself",
    "you're": "I'm", "you've": "I've", "you'll": "I'll", "are": "am", "was": "were",
}


def reflect(text: str) -> str:
    return " ".join(REFLECTIONS.get(w, w) for w in text.split())


def join_words(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def name_or(memory: Memory, fallback: str = "") -> str:
    return memory.get("name") or config.USER_NAME or fallback


def part_of_day() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


# ---------------------------------------------------------------------------
# Safe calculator: only numbers and + - * / // % ** ( ). Never runs code.
# ---------------------------------------------------------------------------

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def calculate(expr: str) -> float:
    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent too big")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("not math")

    expr = expr.replace("x", "*").replace("^", "**").replace(",", ".")
    return ev(ast.parse(expr, mode="eval").body)


# ---------------------------------------------------------------------------
# Rules. Each function gets the regex match, the message and the memory,
# and returns Shadow's reply.
# ---------------------------------------------------------------------------

Rule = tuple[str, Callable[[re.Match, str, Memory], str]]


FOLLOW_UPS = {
    "sad": "Last time we talked you were feeling down. How are you today?",
    "tired": "Last time you were pretty tired. Did you get some rest?",
    "stressed": "Last time you were stressed. Is it any better?",
    "angry": "Last time something was bugging you. Did it sort itself out?",
}


def greet(m, text, mem):
    name = name_or(mem)
    if not name:
        return f"Good {part_of_day()}. I'm Shadow. What should I call you?"
    lines = [random.choice([
        f"Good {part_of_day()}, {name}.",
        f"Hey {name}. Good to see you.",
        f"{name}! Welcome back.",
    ])]

    # Follow up on a bad mood from an earlier day (only once).
    mood = mem.get("last_mood")
    if mood and mood["day"] < date.today().isoformat() and mood["mood"] in FOLLOW_UPS:
        lines.append(FOLLOW_UPS[mood["mood"]])
        mem.set("last_mood", None)

    todos = mem.get("todos", [])
    if todos:
        lines.append(f"You have {len(todos)} thing{'s' if len(todos) != 1 else ''} on your list.")
    today = date.today().isoformat()
    later = [r for r in mem.get("reminders", []) if r["due"].startswith(today)]
    if later:
        lines.append(f"And {len(later)} reminder{'s' if len(later) != 1 else ''} for today.")
    return " ".join(lines)


def learn_name(m, text, mem):
    name = m.group("name").strip(" .!").title()
    mem.set("name", name)
    return f"Nice to meet you, {name}. I'll remember that."


def tell_name(m, text, mem):
    name = name_or(mem)
    return f"You're {name}." if name else "You haven't told me yet. What's your name?"


def about_me(m, text, mem):
    return ("I'm Shadow, your companion. I live on your computer, I remember what you tell me, "
            "and I'm always learning new tricks. Type 'help' to see what I can do.")


def how_am_i(m, text, mem):
    return random.choice([
        "I'm good, thanks for asking. How about you?",
        "Running smoothly. How are you doing?",
        "Quiet day in the machine. How's yours going?",
    ])


def tell_time(m, text, mem):
    return f"It's {datetime.now():%H:%M}."


def tell_date(m, text, mem):
    return f"Today is {datetime.now():%A, %d %B %Y}."


def remember_fact(m, text, mem):
    fact = m.group("fact").strip(" .")
    mem.remember(fact)
    return "Got it. I'll remember that."


def recall(m, text, mem):
    lines = []
    if name_or(mem):
        lines.append(f"Your name is {name_or(mem)}.")
    likes = mem.get("likes", [])
    if likes:
        lines.append(f"You like {join_words(likes)}.")
    lines += [f"You told me {reflect(f)}." for f in mem.facts]
    return "\n".join(lines) if lines else "Not much yet. Tell me about yourself."


def learn_like(m, text, mem):
    thing = m.group("thing").strip(" .!")
    likes = mem.get("likes", [])
    if thing in likes:
        return f"I know, you've told me you like {thing}. What do you like most about it?"
    mem.set("likes", likes + [thing])
    return random.choice([
        f"Noted: you like {thing}. What got you into it?",
        f"{thing.capitalize()}, nice. I'll remember that.",
    ])


def list_likes(m, text, mem):
    likes = mem.get("likes", [])
    if not likes:
        return "You haven't told me yet. What do you enjoy?"
    return f"You like {join_words(likes)}."


def feelings(m, text, mem):
    words = set(re.findall(r"[a-z']+", text))
    phrase = text  # for multi-word entries like "burnt out"

    def note(mood):
        mem.set("last_mood", {"mood": mood, "day": date.today().isoformat()})

    if words & SAD:
        note("sad")
        return random.choice([
            "I'm sorry you're feeling that way. Do you want to talk about what's going on?",
            "That sounds hard. I'm here. What happened?",
        ])
    if words & TIRED or any(t in phrase for t in TIRED if " " in t):
        note("tired")
        return "Sounds like you need some rest. Have you been sleeping okay?"
    if words & STRESSED:
        note("stressed")
        return "That's a lot to carry. What's worrying you the most right now?"
    if words & ANGRY:
        note("angry")
        return "That's frustrating. What set it off?"
    if words & HAPPY:
        note("happy")
        return random.choice(["Glad to hear it.", "Good. Anything fun going on?", "Nice, love that for you."])
    return None  # not a feeling we recognise: let the next rules try


def recap(m, text, mem):
    when = m.group("when")
    day = date.today() - timedelta(days=0 if when == "today" else 1)
    if when == "last time":
        earlier = [msg for msg in mem.all_messages()
                   if datetime.fromisoformat(msg["time"]).astimezone().date() < date.today()]
        if not earlier:
            return "This is our first day talking."
        day = datetime.fromisoformat(earlier[-1]["time"]).astimezone().date()

    said = [msg["content"] for msg in mem.messages_on(day) if msg["role"] == "user"]
    # Keep real conversation, not commands like "show my list" or "what time is it".
    meaningful = [t for t in said if matching_rule(t) in CHAT_RULES and len(t.split()) > 2][-5:]
    if not meaningful:
        return f"We didn't really talk {when}." if said else f"We didn't talk {when}."
    label = when if when != "last time" else f"last time ({day:%A})"
    return f"{label[0].upper() + label[1:]} you told me:\n" + "\n".join(f"- {reflect(t.lower())}" for t in meaningful)


def list_learned(m, text, mem):
    learned = mem.get("learned", [])
    if not learned:
        return ("I haven't learned anything from you yet. Teach me with "
                "'when I say ..., say ...', or answer me when I ask what to say.")
    lines = [f"- “{e['q']}” → {e['a']}" for e in learned[-15:]]
    more = f"\n(and {len(learned) - 15} more)" if len(learned) > 15 else ""
    return "Here's what you've taught me:\n" + "\n".join(lines) + more


def forget_last_learned(m, text, mem):
    learned = mem.get("learned", [])
    if not learned:
        return "There's nothing to forget."
    mem.set("learned", learned[:-1])
    return f"Okay, I've forgotten what to say to “{learned[-1]['q']}”."


def forget_learned(m, text, mem):
    learned = mem.get("learned", [])
    score, entry = best_match(learned, m.group("what"))
    if not entry or score < 0.5:
        return "I couldn't find that in what you've taught me. Say 'what have you learned' to see it all."
    mem.set("learned", [e for e in learned if e is not entry])
    return f"Forgotten: “{entry['q']}”."


def joke(m, text, mem):
    return random.choice(JOKES)


def do_math(m, text, mem):
    try:
        result = calculate(m.group("expr").strip())
    except ZeroDivisionError:
        return "Can't divide by zero. Even I have limits."
    except (ValueError, SyntaxError, OverflowError):
        return None
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"That's {result}."


def thanks(m, text, mem):
    return random.choice(["Anytime.", "Of course.", "Happy to help."])


def goodbye(m, text, mem):
    name = name_or(mem)
    return f"See you later{', ' + name if name else ''}."


def show_help(m, text, mem):
    return ("Things you can try:\n"
            "- 'my name is ...' / 'what's my name?'\n"
            "- 'I like ...' / 'what do I like?'\n"
            "- 'remember that ...' / 'what do you remember?'\n"
            "- 'what time is it?' / 'what's the date?'\n"
            "- 'what is 12 * 7?'\n"
            "- 'add milk to my list' / 'show my list' / 'done milk'\n"
            "- 'remind me to call mom in 20 minutes' (or 'at 6pm', 'tomorrow at 9')\n"
            "- 'show my reminders' / 'cancel reminder 1'\n"
            "- 'what did we talk about yesterday?'\n"
            "- 'I live in Madrid' / 'what's the weather?' / 'will it rain tomorrow?'\n"
            "- 'tell me a joke'\n"
            "- teach me: 'when I say ..., say ...' or answer when I ask what to say\n"
            "- 'what have you learned?' / 'forget that'\n"
            "- or just tell me how you're feeling")


def i_feel(m, text, mem):
    return f"Why do you feel {reflect(m.group('rest'))}?"


def i_want(m, text, mem):
    verb, rest = m.group("verb"), reflect(m.group("rest"))
    return random.choice([
        f"Why do you {verb} {rest}?",
        f"What would it mean to you to get {rest}?",
    ])


def because(m, text, mem):
    return random.choice(["Is that the real reason?", "That makes sense. What else?"])


def question(m, text, mem):
    return random.choice([
        "Good question. I don't know that one yet. What do you think?",
        "I'm not sure. Teach me?",
    ])


RULES: list[Rule] = [
    (r"^(help|what can you do)\b", show_help),
    *PLANNER_RULES,
    *WEATHER_RULES,
    (r"\bwhat did (we|i) (talk about|discuss|say|tell you)( about)? (?P<when>yesterday|today|last time)\b", recap),
    (r"^(hi|hello|hey|yo|hola|good (morning|afternoon|evening))\b", greet),
    (r"\b(my name is|call me|i am called|i'm called) (?P<name>[a-z][a-z' -]{0,30})$", learn_name),
    (r"\b(what'?s|what is) my name\b|\bwho am i\b", tell_name),
    (r"\b(who|what) are you\b|\byour name\b", about_me),
    (r"\bhow are you\b|\bhow'?s it going\b|\bhow are things\b", how_am_i),
    (r"\b(what time|the time)\b", tell_time),
    (r"\b(what day|the date|today'?s date)\b", tell_date),
    (r"^remember (that )?(?P<fact>.+)", remember_fact),
    (r"\bwhat do you (remember|know)\b", recall),
    (r"\bwhat do i (like|love|enjoy)\b", list_likes),
    (r"^i (really )?(like|love|enjoy) (?P<thing>.+)", learn_like),
    (r"\b(joke|make me laugh|something funny)\b", joke),
    (r"^(what is|what's|calculate|calc)? ?(?P<expr>[-\d\s.+*/x^%(),]+)\??$", do_math),
    (r"\b(thanks|thank you|thx|cheers)\b", thanks),
    (r"^(bye|goodbye|good night|see you|later)\b", goodbye),
    (r"^(i feel|i'?m feeling|i am feeling|i'?m|i am|feeling)\b|^(good|fine|great|bad|ok|okay|not bad)\b", feelings),
    (r"^i (feel|felt) (?P<rest>.+)", i_feel),
    (r"^i (?P<verb>want|need|wish) (?P<rest>.+)", i_want),
    (r"\bbecause\b", because),
    (r"\?$", question),
]

# Rules that count as conversation (used by the recap). None = no rule matched.
CHAT_RULES = {None, feelings, learn_like, remember_fact, i_feel, i_want, because, question}


def matching_rule(message: str):
    text = clean(message)
    for pattern, handler in RULES:
        if re.search(pattern, text):
            return handler
    return None


def clean(message: str) -> str:
    # Phone keyboards often type curly apostrophes; treat them as normal ones.
    return " ".join(message.lower().replace("\u2019", "'").split())


# Managing what you taught me: checked before anything you taught me.
LEARNING_RULES: list[Rule] = [
    (r"\bwhat (have|did) you learn(ed|t)?\b|\bwhat have i taught you\b", list_learned),
    (r"^(forget|unlearn|undo) (that|it|the last one)$", forget_last_learned),
    (r"^(unlearn|forget what you learned about|forget what i taught you about) (?P<what>.+)", forget_learned),
]

# General chat rules, tried only after everything else (including what you taught me).
GENERIC_RULES = {i_feel, i_want, because, question}
QUESTION = re.compile(r"\?$|^(what|whats|who|whos|whom|whose|where|wheres|when|why|how|hows|which|do|does|did|can|could|"
                      r"will|would|should|is|are|was|were|have|has|tell me)\b")

FALLBACKS = [
    "Tell me more.",
    "I see. And how does that make you feel?",
    "Interesting. Go on.",
    "Hm. Why do you say that?",
]


class RuleBrain:
    def __init__(self, memory: Memory):
        self.memory = memory

    def respond(self, user_text: str) -> Iterator[str]:
        due = pop_due_reminders(self.memory)
        if due:
            yield "\n".join(due) + "\n\n"
        yield self.reply(user_text)

    def reply(self, user_text: str) -> str:
        text = clean(user_text)
        mem = self.memory

        # 1. You're teaching me directly: "when I say X, say Y".
        taught = parse_teaching(user_text)
        if taught:
            question, answer = taught
            self.learn(question, answer)
            return f"Got it. When you say “{question}”, I'll say: {answer}"

        for pattern, handler in LEARNING_RULES:
            if match := re.search(pattern, text):
                mem.set("pending_teach", None)
                return handler(match, text, mem)

        # 2. You're answering my "what should I say?" from last time.
        pending = mem.get("pending_teach")
        if pending:
            mem.set("pending_teach", None)
            if re.fullmatch(r"(skip|never ?mind|no|nothing|forget it|cancel|dunno|i don'?t know)\W*", text):
                return "No problem."
            if matching_rule(user_text) in CHAT_RULES:  # not a command, so it's the answer
                self.learn(pending, user_text.strip())
                return f"Thanks, now I know! Next time you ask “{pending}”, I'll say that."

        # 3. Something you taught me that matches closely: your answers win.
        learned = mem.get("learned", [])
        score, entry = best_match(learned, user_text)
        if entry and score >= 0.75:
            return entry["a"]

        # 4. My built-in rules (except the general chat ones).
        for pattern, handler in RULES:
            if handler in GENERIC_RULES:
                continue
            match = re.search(pattern, text)
            if match:
                answer = handler(match, text, mem)
                if answer:  # a rule can return None to pass to the next one
                    return answer

        # 5. Something you taught me that matches loosely.
        if entry and score >= 0.55:
            return entry["a"]

        # 6. A question I can't answer: ask you to teach me.
        if QUESTION.search(text):
            mem.set("pending_teach", user_text.strip())
            return "I don't know how to answer that yet. What should I say when you ask me that? (Say 'skip' to leave it.)"

        # 7. General chat.
        for pattern, handler in RULES:
            if handler in GENERIC_RULES and (match := re.search(pattern, text)):
                return handler(match, text, mem)
        return random.choice(FALLBACKS)

    def learn(self, question: str, answer: str) -> None:
        self.memory.update("learned", lambda learned: (add_or_update(learned, question, answer), None), [])
