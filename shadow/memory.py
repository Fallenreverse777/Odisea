"""Simple JSON-file memory shared by every device that talks to Shadow."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class Memory:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "memory.json"
        self._lock = threading.Lock()
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._data = {"facts": [], "messages": []}
        self._data.setdefault("profile", {})

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    # --- conversation -------------------------------------------------
    def add_message(self, role: str, text: str, device: str = "") -> None:
        with self._lock:
            self._data["messages"].append({
                "role": role,
                "content": text,
                "device": device,
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            self._save()

    def recent_messages(self, limit: int) -> list[dict]:
        """Last `limit` messages in API format, always starting with a user turn."""
        with self._lock:
            window = self._data["messages"][-limit:]
        while window and window[0]["role"] != "user":
            window = window[1:]
        return [{"role": m["role"], "content": m["content"]} for m in window]

    def all_messages(self) -> list[dict]:
        with self._lock:
            return list(self._data["messages"])

    def clear_conversation(self) -> None:
        with self._lock:
            self._data["messages"] = []
            self._save()

    # --- what Shadow has learned about the user ---------------------------
    def get(self, key: str, default=None):
        with self._lock:
            return self._data["profile"].get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data["profile"][key] = value
            self._save()

    # --- long-term facts ------------------------------------------------
    @property
    def facts(self) -> list[str]:
        with self._lock:
            return list(self._data["facts"])

    def remember(self, fact: str) -> None:
        with self._lock:
            self._data["facts"].append(fact)
            self._save()

    def forget(self, index: int) -> str:
        with self._lock:
            fact = self._data["facts"].pop(index)
            self._save()
            return fact
