"""Shadow's front door: picks a brain and keeps the conversation in memory."""

from collections.abc import Iterator

from . import config
from .memory import Memory


class BrainError(Exception):
    """A reply couldn't be produced; the message is shown to the user."""


class Shadow:
    def __init__(self, memory: Memory | None = None):
        self.memory = memory or Memory(config.DATA_DIR)
        if config.BRAIN == "claude":
            from .claude_brain import ClaudeBrain
            self.brain = ClaudeBrain(self.memory)
        else:
            from .rules import RuleBrain
            self.brain = RuleBrain(self.memory)

    def chat(self, user_text: str, device: str = "") -> Iterator[str]:
        """Send a message and yield Shadow's reply (in pieces, if it streams)."""
        reply = ""
        try:
            for chunk in self.brain.respond(user_text):
                reply += chunk
                yield chunk
        except BrainError as e:
            yield f"[{e}]"
            return

        # Only save the exchange once it succeeded, so a failed reply can't
        # leave an unanswered message in the history.
        if reply:
            self.memory.add_message("user", user_text, device)
            self.memory.add_message("assistant", reply, device)
