#!/bin/sh
# BIRDWATCHER · map the gamepad buttons (saved to Birdwatcher/config.json)
DIR="$(cd "$(dirname "$0")" && pwd)/Birdwatcher"
cd "$DIR" || exit 1
PY="$(command -v python3 || echo /usr/bin/python3)"
"$PY" main.py --calibrate >"$DIR/log-setup.txt" 2>&1
