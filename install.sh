#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.9 or later, then run this file again. See docs/INSTALLATION.md."
  exit 1
fi
exec python3 install.py "$@"
