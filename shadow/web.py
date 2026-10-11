"""Web chat for your phone (or any browser):  python -m shadow.web

Then open http://<your-pc-ip>:8000 on your phone while on the same Wi-Fi.
"""

import hmac
import socket
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import config
from .brain import Shadow
from .planner import pop_due_reminders

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Shadow")
shadow = Shadow()


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
    return StreamingResponse(shadow.chat(text, device="phone"), media_type="text/plain; charset=utf-8")


@app.get("/api/reminders/due", dependencies=[Depends(check_access)])
def due_reminders():
    return pop_due_reminders(shadow.memory)


@app.post("/api/remember", dependencies=[Depends(check_access)])
def remember(body: FactIn):
    shadow.memory.remember(body.fact.strip())
    return {"ok": True}


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> None:
    import uvicorn

    port = 8000
    print(f"\nShadow is listening. On your phone (same Wi-Fi), open:  http://{_lan_ip()}:{port}\n")
    if not config.ACCESS_CODE:
        print("Warning: SHADOW_ACCESS_CODE is not set, so anyone on your network can chat with Shadow.\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
