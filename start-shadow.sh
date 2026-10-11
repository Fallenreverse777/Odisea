#!/usr/bin/env bash
# Start Shadow on Mac or Linux. The first run sets everything up.
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
    echo "First run: setting Shadow up. This takes a minute..."
    if ! python3 -m venv .venv; then
        echo "Python 3 was not found. Install it from https://www.python.org/downloads/ and try again."
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

.venv/bin/python -m shadow.web
