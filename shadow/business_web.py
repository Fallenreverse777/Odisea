"""Shadow for a business: a customer chat page plus a private admin page.

    python -m shadow.business_web               start and open the admin page
    python -m shadow.business_web --no-browser  start without opening a browser

Customers use  http://<this-pc>:8001/        (no access to your personal Shadow)
The owner uses http://localhost:8001/admin   (needs SHADOW_ACCESS_CODE from another device)
"""


from __future__ import annotations
import argparse
import hmac
import socket
import threading
import webbrowser
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import business, config
from .learning import parse_teaching
from .notify import notify

STATIC = Path(__file__).parent / "static"
PORT = 8001

app = FastAPI(title="Shadow for business")


def new_request(request: dict) -> None:
    """A customer asked to be booked in or called back: tell the owner on this PC."""
    threading.Thread(target=notify, args=(f"New request from {request['name']} ({request['phone']}): {request['details']}",),
                     daemon=True).start()


kb, brain = business.load(on_request=new_request)


def owner_only(request: Request, x_access_code: str = Header(default="")) -> None:
    """The admin page needs the access code, or must be opened on this PC when none is set."""
    if config.ACCESS_CODE:
        if not hmac.compare_digest(x_access_code, config.ACCESS_CODE):
            raise HTTPException(status_code=401, detail="Wrong access code")
    elif request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="Set SHADOW_ACCESS_CODE in .env to use the admin page from another device")


class Question(BaseModel):
    message: str = Field(max_length=500)
    session: str = Field(default="", max_length=64)


class Status(BaseModel):
    status: str = Field(pattern="^(new|done|delete)$")


class Lesson(BaseModel):
    q: str = Field(max_length=500)
    a: str = Field(max_length=2000)


# --- customers ---------------------------------------------------------------

@app.get("/")
def customer_page():
    return FileResponse(STATIC / "business.html")


@app.get("/api/info")
def info():
    data = kb.data
    return {"name": data["name"], "about": data["about"], "bookings": data.get("bookings", False),
            "booking_label": data.get("booking_label", ""), "service_area": bool(data.get("service_area")),
            "emergencies": bool(data.get("emergencies"))}


@app.post("/api/ask")
def ask(body: Question):
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    return {"reply": brain.answer(text, session=body.session)}


# --- owner -------------------------------------------------------------------

@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html")


@app.get("/api/admin/kb", dependencies=[Depends(owner_only)])
def get_kb():
    return kb.data


@app.put("/api/admin/kb", dependencies=[Depends(owner_only)])
def put_kb(data: dict):
    # Unanswered questions and requests are handled separately, so new ones aren't lost on save.
    with kb.lock:
        data["unanswered"] = kb.data.get("unanswered", [])
        data["requests"] = kb.data.get("requests", [])
    kb.replace(data)
    return kb.data


@app.get("/api/admin/templates", dependencies=[Depends(owner_only)])
def templates():
    return business.list_templates()


@app.get("/api/admin/templates/{template_id}", dependencies=[Depends(owner_only)])
def get_template(template_id: str):
    tpl = business.template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="No such template")
    return tpl


@app.post("/api/admin/requests/{request_id}", dependencies=[Depends(owner_only)])
def set_request(request_id: str, body: Status):
    kb.set_request_status(request_id, None if body.status == "delete" else body.status)
    return {"ok": True}


@app.get("/api/admin/links", dependencies=[Depends(owner_only)])
def links():
    return {"customer": f"http://{lan_ip()}:{PORT}/"}


@app.post("/api/admin/dismiss", dependencies=[Depends(owner_only)])
def dismiss(body: Question):
    kb.dismiss(body.message)
    return {"ok": True}


@app.post("/api/admin/teach", dependencies=[Depends(owner_only)])
def teach(body: Lesson):
    if not body.q.strip() or not body.a.strip():
        raise HTTPException(status_code=400, detail="Both a question and an answer are needed")
    kb.teach(body.q, body.a)
    return {"ok": True}


@app.post("/api/admin/chat", dependencies=[Depends(owner_only)])
def owner_chat(body: Question):
    """The owner tests Shadow or teaches it ("if someone asks X, say Y")."""
    taught = parse_teaching(body.message)
    if taught:
        kb.teach(*taught)
        return {"reply": f"Learned! When a customer asks “{taught[0]}”, I'll say: {taught[1]}", "known": True}
    reply = brain.lookup(body.message)
    if reply:
        return {"reply": reply, "known": True}
    return {"reply": "I don't know that yet. What should I answer?", "known": False}


# --- start -------------------------------------------------------------------

def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Shadow for a business.")
    parser.add_argument("--no-browser", action="store_true", help="don't open the admin page")
    args = parser.parse_args()
    admin_url = f"http://localhost:{PORT}/admin"

    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            print(f"Shadow for business is already running. Opening {admin_url}")
            if not args.no_browser:
                webbrowser.open(admin_url)
            return

    print(f"\nShadow for {kb.data['name']} is running.\n"
          f"  Admin page (you):   {admin_url}\n"
          f"  Customer chat:      http://{lan_ip()}:{PORT}/   (same Wi-Fi)\n")
    print("Leave this window open. Close it (or Ctrl+C) to stop.\n")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(admin_url,)).start()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
