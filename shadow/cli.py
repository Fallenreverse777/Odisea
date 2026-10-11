"""Chat with Shadow in your terminal:  python -m shadow.cli"""

import threading

from .brain import Shadow
from .planner import pop_due_reminders

HELP = """Commands:
  /remember <fact>   Tell Shadow something to always remember
  /facts             List remembered facts
  /forget <number>   Forget a fact
  /clear             Wipe the conversation (keeps facts)
  /quit              Leave"""


def watch_reminders(shadow: Shadow, stop: threading.Event) -> None:
    """Every 15 seconds, print any reminder whose time has come."""
    while not stop.wait(15):
        for reminder in pop_due_reminders(shadow.memory):
            print(f"\n\aShadow: {reminder}\nYou: ", end="", flush=True)


def main() -> None:
    shadow = Shadow()
    stop = threading.Event()
    threading.Thread(target=watch_reminders, args=(shadow, stop), daemon=True).start()
    print("Shadow is here. Type /help for commands.\n")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue

        if text.startswith("/"):
            cmd, _, arg = text.partition(" ")
            if cmd in ("/quit", "/exit"):
                break
            elif cmd == "/help":
                print(HELP)
            elif cmd == "/remember" and arg:
                shadow.memory.remember(arg)
                print("Shadow: Got it, I'll remember that.")
            elif cmd == "/facts":
                facts = shadow.memory.facts
                print("\n".join(f"  {i + 1}. {f}" for i, f in enumerate(facts)) or "  (nothing yet)")
            elif cmd == "/forget" and arg.isdigit() and 0 < int(arg) <= len(shadow.memory.facts):
                print(f"Shadow: Forgotten: {shadow.memory.forget(int(arg) - 1)}")
            elif cmd == "/clear":
                shadow.memory.clear_conversation()
                print("Shadow: Fresh start.")
            else:
                print("Unknown command. Type /help.")
            print()
            continue

        print("Shadow: ", end="", flush=True)
        for chunk in shadow.chat(text, device="pc"):
            print(chunk, end="", flush=True)
        print("\n")
    stop.set()


if __name__ == "__main__":
    main()
