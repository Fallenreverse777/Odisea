# Odisea: Shadow

Shadow is a personal companion you can talk to from your PC's terminal or your phone's browser. Both share the same memory.

Shadow's brain is its own Python code, a loop of if/else rules. It runs **offline, for free, with no API key and no AI service**.

## Start Shadow (one click)

1. Install Python 3.9 or newer from https://www.python.org/downloads/ (on Windows, tick **"Add Python to PATH"**).
2. Double-click the launcher in the `Odisea` folder:
   - **Windows:** `start-shadow.bat`
   - **Mac:** `start-shadow.command`
   - **Linux:** `./start-shadow.sh`

The first run sets everything up, which takes about a minute. After that it starts in seconds and opens the chat in your browser.
Keep the window open while you use Shadow.

**On your phone:** open the "On your phone" address the launcher prints (e.g. `http://192.168.1.20:8000`) while on the same Wi-Fi.
Tip: add it to your home screen so it opens like an app. Set `SHADOW_ACCESS_CODE` in `.env` so only you can use it.
If the phone can't connect, allow Python through your PC's firewall.

### Mac: if it doesn't start

Open **Terminal** (Applications → Utilities), then:

```bash
cd ~/Odisea                 # or wherever you cloned it
git checkout shadow-v1      # the code lives on this branch
git pull
./start-shadow.sh
```

- **"Shadow needs Python 3.9 or newer" / "command not found: python3"**: install Python from https://www.python.org/downloads/ (macOS installer), then run it again.
- **"Permission denied"** (common after downloading a ZIP instead of cloning): run `chmod +x *.sh *.command` in the folder.
- **"cannot be opened because it is from an unidentified developer"** when double-clicking: right-click `start-shadow.command` → **Open** → **Open**. Or run `xattr -dr com.apple.quarantine .` in the folder.
- **Something else broke during setup**: delete the `.venv` folder (`rm -rf .venv`) and run `./start-shadow.sh` again.
- On a Mac, use `python3` where instructions say `python`, and `.venv/bin/python` instead of `.venv\Scripts\python`.

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
| `when I say ..., say ...` | Teaches Shadow a reply (it also asks when it doesn't know) |
| `what have you learned?` / `forget that` | Shows or undoes what you've taught it |
| `help` | Lists all of this |

## Shadow learns from you

When you ask Shadow something it can't answer, it asks what it should say. Your next message becomes the answer:

```
You:    what's your favourite movie?
Shadow: I don't know how to answer that yet. What should I say when you ask me that?
You:    Blade Runner, obviously.
...
You:    what's your favorite film          ← different words, same question
Shadow: Blade Runner, obviously.
```

You can also teach it directly: `when I say good night, say sleep well`, or `learn: who made you = Alex did`.
`what have you learned?` lists everything, `forget that` undoes the last thing, and `unlearn favourite movie` removes one.
Your answers take priority over Shadow's built-in replies. Say `skip` if you don't want to teach it something.

Matching ignores small words, plurals, accents and common synonyms (film/movie, made/created/built), and checks that the important words match. So "capital of Spain" won't get the answer you taught for "capital of France".

## Shadow for a business

A separate version of Shadow answers **customers** of a local business: opening hours ("are you open now?"), location, contact details, products and prices, and any question the owner teaches it. It understands simple Spanish too ("¿a qué hora abren el sábado?").

**Start it:** double-click `start-business.bat` (Windows), `start-business.command` (Mac) or run `./start-business.sh` (Linux).
The admin page opens on your PC, and it prints the customer chat address for other devices.

| Page | Who | Address |
|---|---|---|
| Customer chat | Customers | `http://<your-pc-ip>:8001/` |
| Admin | The owner | `http://localhost:8001/admin` (from other devices, set `SHADOW_ACCESS_CODE`) |

**How it learns:**
- Every question Shadow can't answer is saved under **"Questions Shadow couldn't answer"** on the admin page, with how often it was asked. Write an answer, and Shadow knows it from then on, including differently worded versions.
- In **Teach & test**, try questions as a customer. When Shadow doesn't know, type the answer. Or write `if someone asks "do you have parking?" say "Yes, behind the shop."`
- Edit the business details, opening hours, products and prices, and all learned Q&As on the same page, then click **Save changes**.

### Templates for trades

On the admin page, **Type of business** loads a ready-made template:

| Template | Includes |
|---|---|
| Plumber | Call-outs, leaks, blockages, boilers; burst pipe and gas leak emergencies |
| Electrician | Fault finding, sockets, fuse boxes, EV chargers; sparks, shocks, fallen power lines |
| Heating & air conditioning | Boiler and AC service and repair; gas leak and carbon monoxide alarms |
| Car mechanic / garage | Services, brakes, diagnostics, tyres; roadside breakdowns |
| Handyman / repairs | Furniture assembly, shelves, painting, small jobs |
| Cleaning service | Regular, deep and end-of-tenancy cleans |
| Gardening / landscaping | Maintenance, hedges, trees, clearance; fallen trees |
| Veterinary clinic | Consultations, vaccinations, neutering; poisoning, breathing problems, injuries |
| Hair salon / barber | Cuts, colour, highlights, walk-ins, patch tests |

Each template fills in typical services and example prices, common customer questions, emergency advice and booking questions.
**Change the prices and details to match the business**, then click **Save changes**. Templates are plain JSON files in `templates/`, so you can add new trades.

### What trade customers get

- **Emergencies first:** "my pipe burst", "I smell gas", "my dog ate chocolate" get immediate safety steps and the phone number. The advice is deliberately simple and points to the local emergency number when lives may be at risk. Owners can edit it in **Emergencies**.
- **Service area:** "do you cover Getafe?" → "Yes, we cover Getafe." (set **Areas you cover**).
- **Booking, quote and call-back requests:** "can someone come out?", "book an appointment", "I'd like a quote" or "call me back" start a short chat: name → phone → what they need → when. The request pops up on the owner's PC and appears under **Booking & call-back requests**, with a tap-to-call number. Customers are told it isn't booked until the business confirms.
- When Shadow can't answer, it offers a call-back as well as saving the question for the owner.

The example bakery (from `business.example.json`) is what you start with. Everything is saved in `data/business.json`.
The business server is separate from your personal Shadow: customers can't see your chats, to-dos or memory.

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
  rules.py         Shadow's brain: the if/else rules, plus learning from you
  learning.py      matching questions to what Shadow has learned
  business.py      the business brain (emergencies, hours, area, prices, bookings, learned Q&As)
  business_web.py  the business server: customer chat + admin page
  planner.py       to-do list and reminders rules
  weather.py       weather rules (Open-Meteo)
  voice.py         talk out loud on your PC
  notify.py        PC pop-up notifications
  autostart.py     start Shadow when you log in
templates/         ready-made business templates (plumber, electrician, vet, hair salon, ...)
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
