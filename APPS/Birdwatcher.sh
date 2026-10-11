#!/bin/sh
# BIRDWATCHER · ADS-B flight tracker · launcher
DIR="$(cd "$(dirname "$0")" && pwd)/Birdwatcher"
cd "$DIR" || exit 1
PY="$(command -v python3 || echo /usr/bin/python3)"
"$PY" main.py >"$DIR/log.txt" 2>&1
