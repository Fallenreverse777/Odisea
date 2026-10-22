"""Simple tools registry for Shadow.

New capabilities can be registered here without touching the core rule loop.
Each tool is a function that takes (memory, *args, **kwargs) and returns a string reply.
"""

from __future__ import annotations
from collections.abc import Callable
from typing import Any

from .memory import Memory

ToolFunc = Callable[..., str]

_REGISTRY: dict[str, ToolFunc] = {}


def register(name: str):
    """Decorator to register a tool under a short name."""
    def decorator(fn: ToolFunc) -> ToolFunc:
        _REGISTRY[name.lower()] = fn
        return fn
    return decorator


def get(name: str) -> ToolFunc | None:
    return _REGISTRY.get(name.lower())


def list_tools() -> list[str]:
    return sorted(_REGISTRY.keys())


def call(name: str, memory: Memory, *args: Any, **kwargs: Any) -> str:
    """Call a registered tool by name. Returns an error string if missing."""
    fn = get(name)
    if not fn:
        return f"I don't have a tool called '{name}'. Available: {', '.join(list_tools()) or 'none yet'}."
    try:
        return fn(memory, *args, **kwargs)
    except Exception as e:
        return f"Tool '{name}' failed: {e}"


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------

@register("reflect")
def reflect_today(memory: Memory) -> str:
    """Summarise what was learned or remembered today and store a daily note."""
    from datetime import date

    today = date.today()
    today_iso = today.isoformat()

    msgs = memory.messages_on(today)
    user_msgs = [m["content"] for m in msgs if m["role"] == "user"]

    new_facts = []
    new_likes = []

    name = memory.get("name")
    likes = memory.get("likes", [])
    learned = memory.get("learned", [])
    facts = memory.facts

    for msg in user_msgs:
        low = msg.lower()
        if any(p in low for p in ("my name is", "call me", "i am called")):
            new_facts.append(f"Name related: {msg}")
        if low.startswith(("i like", "i love", "i enjoy")):
            new_likes.append(msg)
        if low.startswith(("remember that", "remember ")):
            new_facts.append(msg)

    summary_parts = []
    if name:
        summary_parts.append(f"Your name is {name}.")
    if likes:
        summary_parts.append(f"You like: {', '.join(likes[-5:])}.")
    if facts:
        summary_parts.append(f"Long-term facts remembered: {len(facts)}.")
    if learned:
        summary_parts.append(f"Things you've taught me: {len(learned)}.")

    if not summary_parts and not new_likes and not new_facts:
        return "Nothing new stood out today. Tell me something about yourself and I'll remember it."

    reflections = memory.get("daily_reflections", {})
    reflections[today_iso] = {
        "summary": " ".join(summary_parts),
        "new_likes": new_likes,
        "new_facts": new_facts,
        "message_count": len(user_msgs),
    }
    memory.set("daily_reflections", reflections)

    lines = ["Here's what I noticed today:"]
    if new_likes:
        lines.append("- New likes: " + "; ".join(new_likes))
    if new_facts:
        lines.append("- New facts: " + "; ".join(new_facts))
    lines.append("- " + " ".join(summary_parts))
    lines.append("\nI've saved this as today's reflection.")
    return "\n".join(lines)


@register("improve")
def improve_self(memory: Memory) -> str:
    """Analyse recent conversations and propose concrete improvements."""
    from .improve import propose_improvements
    return propose_improvements(memory)


@register("proposals")
def show_proposals(memory: Memory) -> str:
    """Show the most recent improvement proposals."""
    from .improve import show_last_proposals
    return show_last_proposals(memory)


@register("list_tools")
def list_available(memory: Memory) -> str:
    tools = list_tools()
    if not tools:
        return "No tools registered yet."
    return "Available tools:\n- " + "\n- ".join(tools)
