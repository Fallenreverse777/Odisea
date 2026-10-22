"""Continuous self-improvement for Shadow.

Provides:
- A "reflect and propose improvements" command
- Simple ingestion of external patterns / knowledge (including from files)
- Tracking of improvement suggestions so the user can accept them later
"""

from __future__ import annotations
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config
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
    auto_patterns: list[dict] = []  # high-value patterns we can offer to ingest

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
        auto_patterns.append({
            "q": "I'm exhausted | I'm so tired | feeling drained",
            "a": "That sounds heavy. Did you manage to get any rest? Want to talk about what's wearing you out?"
        })

    # 3. Repeated questions that weren't taught
    from collections import Counter
    questions = [m for m in recent if m.strip().endswith("?")]
    common = Counter(q.lower().strip() for q in questions).most_common(5)
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

    # 5. Business mode / reflection opportunity
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

    # 7. Pattern loading hint
    patterns_dir = config.DATA_DIR / "patterns"
    if patterns_dir.exists() and any(patterns_dir.glob("*.json")):
        suggestions.append(
            f"I found pattern files in data/patterns/. "
            f"Say 'load patterns' to absorb them."
        )

    if not suggestions and not auto_patterns:
        return (
            "Looking good. No obvious gaps right now.\n"
            "Keep teaching me when I don't know something — that's how I improve fastest."
        )

    # Store the proposal (including any auto patterns we can ingest)
    proposals = mem.get("improvement_proposals", [])
    proposals.append({
        "date": date.today().isoformat(),
        "suggestions": suggestions,
        "auto_patterns": auto_patterns,
    })
    mem.set("improvement_proposals", proposals[-10:])

    # Also stash auto_patterns so "yes, ingest them" can find them
    if auto_patterns:
        mem.set("pending_auto_patterns", auto_patterns)

    lines = ["Here's how I could get better:"]
    for i, s in enumerate(suggestions, 1):
        lines.append(f"{i}. {s}")

    if auto_patterns:
        lines.append("")
        lines.append(f"I also prepared {len(auto_patterns)} high-value pattern(s) I can absorb right now.")
        lines.append("Say **yes, ingest them** (or just 'ingest them') to add them permanently.")

    lines.append("\nJust teach me the missing pieces or change settings — I'll keep learning.")
    return "\n".join(lines)


def ingest_patterns(mem: Memory, patterns: list[dict]) -> str:
    """Ingest external patterns (from agent-architect, files, or auto-suggestions).

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


def ingest_pending_auto_patterns(mem: Memory) -> str:
    """Ingest the patterns that 'improve yourself' last offered."""
    patterns = mem.get("pending_auto_patterns") or []
    if not patterns:
        return "There are no pending patterns to ingest. Run 'improve yourself' first."
    result = ingest_patterns(mem, patterns)
    mem.set("pending_auto_patterns", [])
    return result


def load_patterns_from_disk(mem: Memory, subdir: str | None = None) -> str:
    """Load every *.json file from data/patterns/ (or a subdirectory)."""
    base = config.DATA_DIR / "patterns"
    if subdir:
        base = base / subdir

    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        return (
            f"Created {base}. Drop JSON files there (list of {{\"q\": ..., \"a\": ...}} objects) "
            f"and say 'load patterns' again."
        )

    files = sorted(base.rglob("*.json"))
    if not files:
        return f"No .json pattern files found in {base}."

    total_added = 0
    loaded_files = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return f"Failed to read {path.name}: {e}"

        if isinstance(data, dict) and "patterns" in data:
            patterns = data["patterns"]
        elif isinstance(data, list):
            patterns = data
        else:
            return f"{path.name} must be a JSON list of objects or {{\"patterns\": [...]}}."

        before = len(mem.get("learned", []))
        ingest_patterns(mem, patterns)
        after = len(mem.get("learned", []))
        added = after - before
        total_added += max(0, added)
        loaded_files.append(f"{path.relative_to(config.DATA_DIR)} ({added} new)")

    lines = [f"Loaded patterns from {len(loaded_files)} file(s):"]
    lines += [f"- {f}" for f in loaded_files]
    lines.append(f"\nTotal new patterns absorbed: {total_added}")
    return "\n".join(lines)


def show_last_proposals(mem: Memory) -> str:
    proposals = mem.get("improvement_proposals", [])
    if not proposals:
        return "No improvement proposals yet. Say 'improve yourself' or 'how can you get better' to generate some."
    last = proposals[-1]
    lines = [f"Last proposal ({last['date']}):"]
    for i, s in enumerate(last["suggestions"], 1):
        lines.append(f"{i}. {s}")
    auto = last.get("auto_patterns") or []
    if auto:
        lines.append(f"\n({len(auto)} auto-pattern(s) were offered — say 'ingest them' if you still want them.)")
    return "\n".join(lines)
