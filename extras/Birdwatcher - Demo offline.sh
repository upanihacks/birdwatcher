#!/bin/sh
# BIRDWATCHER · simulated traffic, for testing without WiFi
DIR="$(cd "$(dirname "$0")" && pwd)/Birdwatcher"
cd "$DIR" || exit 1
PY="$(command -v python3 || echo /usr/bin/python3)"
"$PY" main.py --demo >"$DIR/log.txt" 2>&1
