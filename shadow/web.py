"""Shadow's server: chat from your PC's browser or your phone.

    python -m shadow.web               start and open the chat in your browser
    python -m shadow.web --no-browser  start without opening a browser
    python -m shadow.web --background  quiet mode used when starting with your PC (logs to data/shadow.log)

On your phone (same Wi-Fi), open the address it prints.
"""

import argparse
import hmac
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import config
from .brain import Shadow
from .notify import notify
from .planner import pop_due_reminders

STATIC = Path(__file__).parent / "static"
PORT = 8000

app = FastAPI(title="Shadow")
shadow = Shadow()

# Reminders that have gone off, so every open page (PC and phone) can show them.
alerts: list[dict] = []
alerts_lock = threading.Lock()
alert_ids = iter(range(1, 10**9))


def check_access(x_access_code: str = Header(default="")) -> None:
    if config.ACCESS_CODE and not hmac.compare_digest(x_access_code, config.ACCESS_CODE):
        raise HTTPException(status_code=401, detail="Wrong access code")


class ChatIn(BaseModel):
    message: str


class FactIn(BaseModel):
    fact: str


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/history", dependencies=[Depends(check_access)])
def history():
    return [
        {"role": m["role"], "content": m["content"], "device": m.get("device", "")}
        for m in shadow.memory.all_messages()[-100:]
    ]


@app.post("/api/chat", dependencies=[Depends(check_access)])
def chat(body: ChatIn):
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    return StreamingResponse(shadow.chat(text, device="web"), media_type="text/plain; charset=utf-8")


@app.get("/api/alerts", dependencies=[Depends(check_access)])
def get_alerts(after: int = 0):
    """Reminders that went off after alert number `after`."""
    with alerts_lock:
        return [a for a in alerts if a["id"] > after]


@app.post("/api/remember", dependencies=[Depends(check_access)])
def remember(body: FactIn):
    shadow.memory.remember(body.fact.strip())
    return {"ok": True}


def deliver_reminders(stop: threading.Event) -> None:
    """Every 15 seconds: pop up due reminders on the PC and queue them for open pages."""
    while not stop.wait(15):
        for text in pop_due_reminders(shadow.memory):
            with alerts_lock:
                alerts.append({"id": next(alert_ids), "text": text})
                del alerts[:-50]
            notify(text.removeprefix("⏰ "))


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def already_running() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Shadow's chat server.")
    parser.add_argument("--no-browser", action="store_true", help="don't open the chat in a browser")
    parser.add_argument("--background", action="store_true", help="quiet mode for starting with your PC")
    args = parser.parse_args()
    local_url = f"http://localhost:{PORT}"

    if already_running():
        # Shadow is already on (e.g. it started with the PC): just open the chat.
        if not args.background:
            print(f"Shadow is already running. Opening {local_url}")
            if not args.no_browser:
                webbrowser.open(local_url)
        return

    if args.background:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(config.DATA_DIR / "shadow.log", "a", buffering=1, encoding="utf-8")

    print(f"\nShadow is running.\n  On this PC:   {local_url}\n  On your phone: http://{lan_ip()}:{PORT}  (same Wi-Fi)\n")
    if not config.ACCESS_CODE:
        print("Warning: SHADOW_ACCESS_CODE is not set, so anyone on your network can chat with Shadow.\n")
    print("Leave this window open while you use Shadow. Close it (or Ctrl+C) to stop.\n")

    stop = threading.Event()
    threading.Thread(target=deliver_reminders, args=(stop,), daemon=True).start()
    if not (args.no_browser or args.background):
        threading.Timer(1.5, webbrowser.open, args=(local_url,)).start()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
    stop.set()


if __name__ == "__main__":
    main()
