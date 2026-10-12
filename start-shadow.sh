#!/usr/bin/env bash
# Start Shadow on Mac or Linux. The first run sets everything up.
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
    echo "First run: setting Shadow up. This takes a minute..."
    if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
        echo "Shadow needs Python 3.9 or newer."
        echo "Install it from https://www.python.org/downloads/ (on a Mac, the macOS installer), then run this again."
        read -r -p "Press Enter to close."
        exit 1
    fi
    if ! python3 -m venv .venv; then
        rm -rf .venv
        echo "Couldn't set up Python for Shadow. Try installing Python from https://www.python.org/downloads/ and run this again."
        read -r -p "Press Enter to close."
        exit 1
    fi
fi

if ! .venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt; then
    echo "Installing Shadow's packages failed. Check your internet connection and try again."
    read -r -p "Press Enter to close."
    exit 1
fi
[ -f .env ] || cp .env.example .env

.venv/bin/python -m "shadow.${SHADOW_APP:-web}"
