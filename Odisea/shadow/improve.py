"""Continuous self-improvement for Shadow.

Provides:
- A "reflect and propose improvements" command
- Simple ingestion of external patterns / knowledge
- Tracking of improvement suggestions so the user can accept them later
"""

from __future__ import annotations
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .memory import Memory


def _recent_user_messages(mem: Memory, days: int = 7) -> list[str]:
    cutoff = date.today() - timedelta(days=days)
    msgs = []
    for m in mem.all_messages():
        if m["role"] != "user":
            continue
        try:
            d = datetime.fromisoformat(m["time"]).astimezone().date()
        except Exception:
            continue
        if d >= cutoff:
            msgs.append(m["content"])
    return msgs


def propose_improvements(mem: Memory) -> str:
    """Analyse recent activity and suggest concrete improvements."""
    recent = _recent_user_messages(mem, days=14)
    learned = mem.get("learned", [])
    facts = mem.facts
    likes = mem.get("likes", [])
    reflections = mem.get("daily_reflections", {})

    suggestions = []

    # 1. Gaps in learning
    if len(learned) < 5:
        suggestions.append(
            "You've only taught me a few things so far. "
            "Try answering when I say I don't know — those answers become permanent knowledge."
        )

    # 2. Mood / emotional support
    mood_words = {"sad", "tired", "stressed", "anxious", "overwhelmed", "lonely"}
    mood_hits = sum(1 for m in recent if any(w in m.lower() for w in mood_words))
    if mood_hits >= 3:
        suggestions.append(
            "You've mentioned feeling low several times recently. "
            "I can get better at checking in — say 'when I say I'm exhausted, ask if I slept'."
        )

    # 3. Repeated questions that weren't taught
    from collections import Counter
    questions = [m for m in recent if m.strip().endswith("?")]
    common = Counter(q.lower().strip() for q in questions).most_common(3)
    for q, count in common:
        if count >= 2 and not any(q in e["q"].lower() for e in learned):
            suggestions.append(
                f"You've asked something like “{q}” {count} times. "
                f"Teach me the answer and I'll stop asking."
            )

    # 4. Missing basic profile
    if not mem.get("name"):
        suggestions.append("You still haven't told me your name. Just say 'my name is …'.")
    if not likes:
        suggestions.append("Tell me a few things you like so I can personalise replies.")

    # 5. Business mode opportunity
    if not reflections and len(recent) > 10:
        suggestions.append(
            "We've talked a fair amount. Try 'reflect' at the end of the day — "
            "I now save a daily summary you can look back on."
        )

    # 6. Hybrid brain hint
    suggestions.append(
        "For free-form conversation you can switch brains: "
        "set SHADOW_BRAIN=claude in .env (needs an Anthropic key). "
        "The rules brain stays the default for speed and privacy."
    )

    if not suggestions:
        return (
            "Looking good. No obvious gaps right now.\n"
            "Keep teaching me when I don't know something — that's how I improve fastest."
        )

    # Store the proposal so the user can refer back
    proposals = mem.get("improvement_proposals", [])
    proposals.append({
        "date": date.today().isoformat(),
        "suggestions": suggestions,
    })
    mem.set("improvement_proposals", proposals[-10:])  # keep last 10

    lines = ["Here's how I could get better:"]
    for i, s in enumerate(suggestions, 1):
        lines.append(f"{i}. {s}")
    lines.append("\nJust teach me the missing pieces or change settings — I'll keep learning.")
    return "\n".join(lines)


def ingest_patterns(mem: Memory, patterns: list[dict]) -> str:
    """Ingest external patterns (from agent-architect or other sources).

    Each pattern is expected to look like:
        {"q": "question or trigger", "a": "answer or behaviour"}
    """
    from .learning import add_or_update

    learned = mem.get("learned", [])
    added = 0
    for p in patterns:
        q = (p.get("q") or p.get("trigger") or "").strip()
        a = (p.get("a") or p.get("response") or "").strip()
        if q and a:
            learned = add_or_update(learned, q, a)
            added += 1
    mem.set("learned", learned)
    return f"Ingested {added} new pattern{'s' if added != 1 else ''}. I know them from now on."


def show_last_proposals(mem: Memory) -> str:
    proposals = mem.get("improvement_proposals", [])
    if not proposals:
        return "No improvement proposals yet. Say 'improve yourself' or 'how can you get better' to generate some."
    last = proposals[-1]
    lines = [f"Last proposal ({last['date']}):"]
    for i, s in enumerate(last["suggestions"], 1):
        lines.append(f"{i}. {s}")
    return "\n".join(lines)
