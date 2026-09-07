#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.9 or later, then run this file again. Open START_HERE.html for the walkthrough."
  exit 1
fi
exec python3 install.py "$@"
