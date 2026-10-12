"""Start Shadow automatically when you log in to your PC.

    python -m shadow.autostart on      turn it on
    python -m shadow.autostart off     turn it off
    python -m shadow.autostart         show whether it's on

Run these with the Python inside .venv (the launcher creates it), e.g.
    Windows:    .venv\\Scripts\\python -m shadow.autostart on
    Mac/Linux:  .venv/bin/python -m shadow.autostart on
"""


from __future__ import annotations
import os
import platform
import subprocess
import sys
from pathlib import Path

from .config import ROOT

SYSTEM = platform.system()


def _python(windowless: bool = False) -> str:
    exe = Path(sys.executable)
    if windowless and SYSTEM == "Windows" and (exe.parent / "pythonw.exe").exists():
        return str(exe.parent / "pythonw.exe")  # runs without a console window
    return str(exe)


def _entry() -> Path:
    if SYSTEM == "Windows":
        return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/Shadow.vbs"
    if SYSTEM == "Darwin":
        return Path.home() / "Library/LaunchAgents/com.odisea.shadow.plist"
    return Path.home() / ".config/autostart/shadow.desktop"


def _contents() -> str:
    if SYSTEM == "Windows":
        return (
            'Set shell = CreateObject("WScript.Shell")\r\n'
            f'shell.CurrentDirectory = "{ROOT}"\r\n'
            f'shell.Run """{_python(windowless=True)}"" -m shadow.web --background", 0, False\r\n'
        )
    if SYSTEM == "Darwin":
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.odisea.shadow</string>
    <key>ProgramArguments</key>
    <array>
        <string>{_python()}</string><string>-m</string><string>shadow.web</string><string>--background</string>
    </array>
    <key>WorkingDirectory</key><string>{ROOT}</string>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
"""
    return f"""[Desktop Entry]
Type=Application
Name=Shadow
Comment=Your companion
Path={ROOT}
Exec="{_python()}" -m shadow.web --background
X-GNOME-Autostart-enabled=true
"""


def turn_on() -> None:
    entry = _entry()
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(_contents(), encoding="utf-8")
    if SYSTEM == "Darwin":
        subprocess.run(["launchctl", "load", str(entry)], capture_output=True)
    print("Shadow will now start by itself when you log in.")
    print("It runs quietly in the background. Open http://localhost:8000 to chat,")
    print("or double-click the launcher (it notices Shadow is already running).")


def turn_off() -> None:
    entry = _entry()
    if SYSTEM == "Darwin" and entry.exists():
        subprocess.run(["launchctl", "unload", str(entry)], capture_output=True)
    entry.unlink(missing_ok=True)
    print("Shadow will no longer start by itself.")
    print("If it's running right now, it stops next time you restart your PC.")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "on":
        turn_on()
    elif command == "off":
        turn_off()
    else:
        print("Start with PC is", "ON" if _entry().exists() else "OFF", f"({_entry()})")
        print("Use: python -m shadow.autostart on | off")


if __name__ == "__main__":
    main()
