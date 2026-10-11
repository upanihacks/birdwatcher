#!/bin/sh
# BIRDWATCHER · checks what the firmware provides and writes Birdwatcher/diagnostics.txt
DIR="$(cd "$(dirname "$0")" && pwd)/Birdwatcher"
OUT="$DIR/diagnostics.txt"
cd "$DIR" || exit 1
{
  echo "== BIRDWATCHER diagnostics $(date)"
  echo "== system"; uname -a; cat /etc/os-release 2>/dev/null | head -3
  echo "== python"; command -v python3; python3 --version 2>&1
  python3 -c "import struct,platform;print(struct.calcsize('P')*8,'bit',platform.machine())" 2>&1
  echo "== libSDL2 on the system"
  ls /usr/lib/libSDL2* /usr/lib32/libSDL2* /usr/lib/*/libSDL2* /mnt/vendor/lib/libSDL2* 2>/dev/null
  echo "== SDL from python (ctypes)"
  python3 -c "
import sdl
print('SDL',sdl.version(),'at',sdl.LIB_PATH,'| float lines:',sdl.HAS_LINESF,'| geometry:',sdl.HAS_GEOMETRY)
g=sdl.Gfx(640,480,'diag')
print('render targets:',g.can_target,'| gamepads:',g.joystick_info())
g.quit()
" 2>&1
  echo "== ssl"; python3 -c "import ssl;print(ssl.OPENSSL_VERSION)" 2>&1
  echo "== network"; ip -4 addr 2>/dev/null | grep inet
  echo "== adsb.lol (https)"
  python3 -c "import urllib.request,json;d=json.load(urllib.request.urlopen('https://api.adsb.lol/v2/point/25.25/55.36/50',timeout=10));print('OK',len(d.get('ac',[])),'aircraft')" 2>&1 | tail -1
  echo "== airplanes.live (http)"
  python3 -c "import urllib.request,json;d=json.load(urllib.request.urlopen('http://api.airplanes.live/v2/point/25.25/55.36/50',timeout=10));print('OK',len(d.get('ac',[])),'aircraft')" 2>&1 | tail -1
} >"$OUT" 2>&1
