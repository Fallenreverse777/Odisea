from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# "rules" = Shadow's own if/else logic: free, offline, no API key needed.
# "claude" = use the Claude API instead (needs ANTHROPIC_API_KEY and `pip install anthropic`).
BRAIN = os.getenv("SHADOW_BRAIN", "rules").strip().lower()

MODEL = os.getenv("SHADOW_MODEL", "claude-opus-5-5")
# Casual chat doesn't need deep reasoning; "low" keeps replies fast and cheap.
# Raise to "medium" or "high" if you want Shadow to think harder.
EFFORT = os.getenv("SHADOW_EFFORT", "low")
USER_NAME = os.getenv("SHADOW_USER_NAME", "").strip()
ACCESS_CODE = os.getenv("SHADOW_ACCESS_CODE", "").strip()

DATA_DIR = Path(os.getenv("SHADOW_DATA_DIR", ROOT / "data"))
# How many past messages Shadow sees on each turn. Older ones stay on disk.
HISTORY_WINDOW = int(os.getenv("SHADOW_HISTORY_WINDOW", "40"))
