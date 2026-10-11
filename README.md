# Odisea: Shadow

Shadow is a personal AI companion, powered by Claude. You can talk to it from your PC's terminal or from your phone's browser, and both share the same memory.

## Setup (on your PC)

1. Get an API key at https://platform.claude.com (Settings → API Keys).
2. Install and configure:

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env             # Windows: copy .env.example .env
   ```

3. Open `.env` and set `ANTHROPIC_API_KEY`. Also set `SHADOW_ACCESS_CODE` if you'll use your phone.

## Talk to Shadow

**On your PC (terminal):**

```bash
python -m shadow.cli
```

**On your phone:** start the server on your PC:

```bash
python -m shadow.web
```

It prints an address like `http://192.168.1.20:8000`. Open that on your phone while it's on the same Wi-Fi. On iPhone, use Share → "Add to Home Screen". On Android, use ⋮ → "Add to Home screen". Shadow then opens like an app.
If your phone can't connect, allow Python through your PC's firewall on port 8000.

## Commands

| Command | What it does |
|---|---|
| `/remember <fact>` | Shadow always keeps this in mind (works on phone too) |
| `/facts` | List what Shadow remembers (terminal) |
| `/forget <n>` | Remove a fact (terminal) |
| `/clear` | Wipe the conversation, keep facts (terminal) |

## How it's built

```
shadow/
  persona.py   who Shadow is (edit this to change its personality)
  memory.py    conversation + facts, saved in data/memory.json
  brain.py     sends the conversation to Claude and streams the reply
  cli.py       terminal chat
  web.py       web server for the phone
  static/      the phone chat page
```

Shadow sees your last 40 messages (`SHADOW_HISTORY_WINDOW`) plus all remembered facts on every turn.

## Roadmap

- [x] Text chat with a personality and memory, on PC and phone
- [ ] Shadow saves important facts on its own
- [ ] Tools: weather, calendar, reminders, web search
- [ ] Voice: speech-to-text, text-to-speech, wake word
- [ ] Reach Shadow away from home (e.g. Tailscale or a small cloud server)
