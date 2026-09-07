#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.9 or later from python.org. See docs/INSTALLATION.md."
  read -r answer
  exit 1
fi
python3 install.py "$@"
result=$?
echo "Press Return to close."
read -r answer
exit "$result"
