# BIRDWATCHER · ADS-B flight tracker for the Anbernic RG35XX SP

An amber wireframe globe showing aircraft in flight in real time, pulled over WiFi from
**adsb.lol** (falling back to **airplanes.live** if the first one fails). Written in plain
Python: it draws with the system's libSDL2 through ctypes, so there is no pygame and nothing
to install. Runs at 640×480.

## Install (stock firmware)

1. Copy the contents of the zip's `APPS` folder into `Roms/APPS` on the SD card. The `.sh`
   launchers and the `Birdwatcher` folder must sit side by side.
2. Turn WiFi on and run **Birdwatcher** from the apps section.

If a button doesn't respond as expected, run **Birdwatcher - Button setup** and press the
buttons in the order shown. They are saved to `Birdwatcher/config.json`. The bottom line of
that screen shows the raw event each button sends.

If something fails on launch, the error ends up in `Birdwatcher/log.txt`.

## Controls

| Button | Action |
|---|---|
| D-pad | rotate the globe (hold) |
| L / R | zoom out / zoom in |
| A | lock the aircraft nearest the reticle; press again for the next one |
| B | release the aircraft or stop following it |
| X | filter: all · military (global query) · private · alert |
| Y | full-screen card of the locked aircraft: big callsign, origin → destination, km flown / to go, ETA and live data (B to go back). With nothing locked, Y cycles the labels: auto · on · off |
| START | follow the locked aircraft |
| SELECT | help |
| MENU or SELECT + START | quit (saves the view) |

Colours: amber commercial · cyan military · magenta business jet · red squawk 7700 / 7600 / 7500.

## How it works

- Every 6 seconds it asks for the aircraft within up to 250 NM of the screen centre
  (`/v2/point`). That is the API maximum, so with the whole globe in view you only see aircraft
  inside the circle marked **capture zone**. Rotate the globe and the zone moves with you.
- Between polls each aircraft moves by dead reckoning from its speed and track.
- Every ~13 s it queries one emergency squawk worldwide (7700, 7600, 7500 in turn) and logs it.
- With the **MILITARY** filter it also queries `/v2/mil` worldwide every 30 s.
- Routes come from a bundled copy of the Virtual Radar Server standing data (about 620,000
  callsigns, `data/routes`), so they show up instantly and work without network. Only if a
  callsign isn't there does it ask adsb.lol online. The full-screen card uses the route to show
  where the flight comes from and where it's going, distance flown and left, and an ETA from the
  current ground speed. If the aircraft is far from the route on file (schedules change), the card
  says so and hides the distances.

For an offline demo with simulated traffic, run `python3 main.py --demo` from the `Birdwatcher`
folder.

Everything is tunable in `config.json`: `poll_seconds`, `home` (starting view), `scanlines`,
`fps`, `feeds`.

## Without pygame

`sdl.py` loads the `libSDL2` the firmware's emulators already use and draws with it (lines,
rectangles, triangles and textures). Text comes from pre-rendered BMP atlases in `fonts/`
(Share Tech Mono and VT323), so SDL_ttf isn't needed either. If the library lives somewhere
unusual, set `BIRDWATCHER_SDL_LIB=/path/to/libSDL2-2.0.so.0` in `Birdwatcher.sh`.

## Limits and licences

- airplanes.live is for non-commercial use and allows 1 request per second; Birdwatcher keeps to that.
- adsb.lol is free for now; they have announced an API key will be required in future.
- Map: Natural Earth via world-atlas (public domain / ISC). Routes and airports: Virtual Radar
  Server standing data (CC0), github.com/vradarserver/standing-data. Fonts: Share Tech Mono and VT323 (SIL OFL).
