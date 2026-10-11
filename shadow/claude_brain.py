"""Optional brain that uses the Claude API. Enable with SHADOW_BRAIN=claude."""

from collections.abc import Iterator

import anthropic

from . import config
from .brain import BrainError
from .memory import Memory
from .persona import build_system_prompt


class ClaudeBrain:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.client = anthropic.Anthropic()

    def respond(self, user_text: str) -> Iterator[str]:
        history = self.memory.recent_messages(config.HISTORY_WINDOW - 1)
        messages = history + [{"role": "user", "content": user_text}]
        system = build_system_prompt(self.memory.facts, config.USER_NAME)

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
                yield from stream.text_stream
                final = stream.get_final_message()
        except anthropic.AuthenticationError:
            raise BrainError("Shadow can't reach Claude: check ANTHROPIC_API_KEY in your .env file.")
        except anthropic.RateLimitError:
            raise BrainError("Shadow is being rate limited. Give it a moment and try again.")
        except anthropic.APIConnectionError:
            raise BrainError("Shadow can't connect to the internet right now.")
        except anthropic.APIStatusError as e:
            raise BrainError(f"Something went wrong talking to Claude: {e.status_code} {e.message}")

        if final.stop_reason == "refusal":
            yield "I'd rather not go there. Let's talk about something else."
