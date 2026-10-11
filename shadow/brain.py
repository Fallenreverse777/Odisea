"""Talks to Claude and keeps the conversation in memory."""

from collections.abc import Iterator

import anthropic

from . import config
from .memory import Memory
from .persona import build_system_prompt


class Shadow:
    def __init__(self, memory: Memory | None = None):
        self.client = anthropic.Anthropic()
        self.memory = memory or Memory(config.DATA_DIR)

    def chat(self, user_text: str, device: str = "") -> Iterator[str]:
        """Send a message and yield Shadow's reply as it streams in."""
        history = self.memory.recent_messages(config.HISTORY_WINDOW - 1)
        messages = history + [{"role": "user", "content": user_text}]
        system = build_system_prompt(self.memory.facts, config.USER_NAME)

        reply = ""
        try:
            with self.client.beta.messages.stream(
                model=config.MODEL,
                max_tokens=16000,
                system=system,
                messages=messages,
                output_config={"effort": config.EFFORT},
                # If the main model declines, the API retries on a suitable
                # fallback model automatically.
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
            ) as stream:
                for text in stream.text_stream:
                    reply += text
                    yield text
                final = stream.get_final_message()
        except anthropic.AuthenticationError:
            yield "[Shadow can't reach Claude: check ANTHROPIC_API_KEY in your .env file.]"
            return
        except anthropic.RateLimitError:
            yield "[Shadow is being rate limited. Give it a moment and try again.]"
            return
        except anthropic.APIConnectionError:
            yield "[Shadow can't connect to the internet right now.]"
            return
        except anthropic.APIStatusError as e:
            yield f"[Something went wrong talking to Claude: {e.status_code} {e.message}]"
            return

        if final.stop_reason == "refusal":
            reply = "I'd rather not go there. Let's talk about something else."
            yield reply

        # Only save the exchange once it succeeded, so a failed call can't
        # leave an unanswered message in the history.
        if reply:
            self.memory.add_message("user", user_text, device)
            self.memory.add_message("assistant", reply, device)
