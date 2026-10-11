# Odisea: Shadow

Shadow is a personal companion you can talk to from your PC's terminal or your phone's browser. Both share the same memory.

Shadow's brain is its own Python code, a loop of if/else rules. It runs **offline, for free, with no API key and no AI service**.

## Setup (on your PC)

```bash
python -m venv .venv
.venv\Scripts\activate           # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env
```

Optional: in `.env`, set `SHADOW_ACCESS_CODE` so only you can use the phone page.

## Talk to Shadow

**On your PC (terminal):**

```bash
python -m shadow.cli
```

**On your phone:** start the server on your PC:

```bash
python -m shadow.web
```

It prints an address like `http://192.168.1.20:8000`. Open that on your phone while it's on the same Wi-Fi. If the page won't load, allow Python through your PC's firewall.

## What Shadow understands

| Say | Shadow |
|---|---|
| `hi`, `good morning` | Greets you by name |
| `my name is ...`, `call me ...` | Learns your name |
| `I like ...` / `what do I like?` | Learns and lists your likes |
| `remember that ...` / `what do you remember?` | Stores and recalls facts |
| `how are you?` | Chats back |
| `I'm tired / sad / stressed / happy` | Responds to your mood |
| `I feel ...`, `I want ...`, `I need ...` | Asks you about it |
| `what time is it?`, `what's the date?` | Tells you |
| `what is 12 * 7?` | Does the maths |
| `tell me a joke` | Tells one |
| `add milk to my list`, `todo: call the bank` | Adds to your to-do list |
| `show my list` / `done milk` / `cross off 2` | Shows or ticks off items |
| `remind me to call mom in 20 minutes` | Sets a reminder (also `at 6pm`, `tomorrow at 9`) |
| `show my reminders` / `cancel reminder 1` | Lists or cancels reminders |
| `what did we talk about yesterday?` | Recaps a past conversation (`today`, `last time` too) |
| `help` | Lists all of this |

## How the brain works (`shadow/rules.py`)

```
your message → clean it up → try each rule in RULES, in order
             → first pattern that matches → its function builds the reply
             → nothing matched → a general fallback ("Tell me more.")
```

To teach Shadow something new, write a function and add a line to `RULES`:

```python
def favourite_colour(m, text, mem):
    return "Mine is black. Obviously."

RULES = [
    (r"\bfavou?rite colou?r\b", favourite_colour),
    ...
]
```

When you say hi, Shadow also checks in on how you felt last time, and mentions your to-dos and today's reminders.

Reminders pop up on their own while the terminal chat or the phone page is open (the page checks every 30 seconds). They only fire while Shadow is running on your PC.

Rules near the top win. A rule can return `None` to pass the message on to the next rule.

## Project layout

```
shadow/
  rules.py         Shadow's brain: the if/else rules
  planner.py       to-do list and reminders rules
  memory.py        conversation, facts and what Shadow learned, saved in data/memory.json
  brain.py         picks the brain and saves the conversation
  cli.py           terminal chat
  web.py           web server for the phone
  static/          the phone chat page
  claude_brain.py  optional AI brain (off by default, see below)
  persona.py       personality for the AI brain
```

## Optional: AI brain

If you ever want Shadow to hold free-form conversations, set `SHADOW_BRAIN=claude` and `ANTHROPIC_API_KEY` in `.env`, then run `pip install anthropic`. This is a paid service. The default rules brain needs none of it.
