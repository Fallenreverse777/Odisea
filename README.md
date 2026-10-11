# Odisea: Shadow

Shadow is a personal companion you can talk to from your PC's terminal or your phone's browser. Both share the same memory.

Shadow's brain is its own Python code, a loop of if/else rules. It runs **offline, for free, with no API key and no AI service**.

## Start Shadow (one click)

1. Install Python 3.10+ from https://www.python.org/downloads/ (on Windows, tick **"Add Python to PATH"**).
2. Double-click the launcher in the `Odisea` folder:
   - **Windows:** `start-shadow.bat`
   - **Mac:** `start-shadow.command`
   - **Linux:** `./start-shadow.sh`

The first run sets everything up, which takes about a minute. After that it starts in seconds and opens the chat in your browser.
Keep the window open while you use Shadow.

**On your phone:** open the "On your phone" address the launcher prints (e.g. `http://192.168.1.20:8000`) while on the same Wi-Fi.
Tip: add it to your home screen so it opens like an app. Set `SHADOW_ACCESS_CODE` in `.env` so only you can use it.
If the phone can't connect, allow Python through your PC's firewall.

## Start Shadow with your PC

Turn this on once and Shadow runs quietly in the background whenever you log in. Your phone can reach it any time, and reminders pop up on your PC as notifications.

```bash
.venv\Scripts\python -m shadow.autostart on      # Windows
.venv/bin/python -m shadow.autostart on          # Mac / Linux
```

Use `off` instead of `on` to turn it off, or leave it out to check whether it's on. While it's running, the launcher just opens the chat.

## Voice

**In the chat page:** tap 🔈 to have Shadow read its replies out loud.
On your PC's browser (Chrome or Edge), the 🎤 button lets you talk to it.
On the phone, use your keyboard's microphone key to dictate. Browsers only allow the page's mic over a secure connection.

**Hands-free on your PC:**

```bash
.venv\Scripts\pip install -r requirements-voice.txt     # once (Mac/Linux: .venv/bin/pip)
.venv\Scripts\python -m shadow.voice --wake              # then say "Shadow, what's the weather?"
```

Without `--wake`, you press Enter before each sentence. Say "Shadow, goodbye" to stop.
Shadow speaks with your computer's built-in voice. Listening uses Google's free speech recognition, so it needs internet but no account.
On Mac, you may need `brew install portaudio` before installing the voice packages.

## Terminal chat

Prefer the terminal? `.venv\Scripts\python -m shadow.cli` (Mac/Linux: `.venv/bin/python -m shadow.cli`).

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
| `I live in Madrid` | Remembers your city |
| `what's the weather?` / `will it rain tomorrow?` / `weather in Paris` | Forecast from Open-Meteo (free, no key) |
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

Reminders pop up as PC notifications and in any open chat page, where the phone also vibrates. They only fire while Shadow is running on your PC, so turn on start-with-PC.

Rules near the top win. A rule can return `None` to pass the message on to the next rule.

## Project layout

```
shadow/
  rules.py         Shadow's brain: the if/else rules
  planner.py       to-do list and reminders rules
  weather.py       weather rules (Open-Meteo)
  voice.py         talk out loud on your PC
  notify.py        PC pop-up notifications
  autostart.py     start Shadow when you log in
  memory.py        conversation, facts and what Shadow learned, saved in data/memory.json
  brain.py         picks the brain and saves the conversation
  cli.py           terminal chat
  web.py           the server: chat page for PC and phone, delivers reminders
  static/          the phone chat page
  claude_brain.py  optional AI brain (off by default, see below)
  persona.py       personality for the AI brain
```

## Optional: AI brain

If you ever want Shadow to hold free-form conversations, set `SHADOW_BRAIN=claude` and `ANTHROPIC_API_KEY` in `.env`, then run `pip install anthropic`. This is a paid service. The default rules brain needs none of it.
