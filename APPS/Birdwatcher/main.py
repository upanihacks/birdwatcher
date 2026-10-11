#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BIRDWATCHER — cyberdeck-style ADS-B flight tracker for 640x480 screens.

Live data over WiFi from adsb.lol (with airplanes.live as a fallback).
Needs only Python 3 and the system libSDL2 (no pygame).

Usage:
  python3 main.py               tracker
  python3 main.py --demo        simulated traffic, no network
  python3 main.py --calibrate   map the gamepad buttons (saved to config.json)
  python3 main.py --windowed    windowed mode for testing on a computer
"""
import os
import sys
import json
import math
import time
import random
import threading
import gzip
import collections
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import sdl

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config.json")
STATE = os.path.join(BASE, "state.json")
VERSION = "1.2.1"

W, H = 640, 480
HDR, PX, FOOT = 24, 432, 78
GY0, GY1 = HDR, H - FOOT
GCX, GCY = PX // 2, (GY0 + GY1) // 2
BASER = 168
RE = 6371.0
DEG = math.pi / 180

COL = {
    'amb': (255, 176, 0), 'ambD': (168, 111, 0), 'ambDD': (74, 50, 0), 'grid': (43, 30, 5),
    'cyan': (77, 225, 255), 'mag': (224, 140, 255), 'red': (255, 59, 59), 'redD': (122, 16, 16),
    'white': (255, 244, 220), 'panel': (13, 9, 4), 'bg': (6, 4, 3), 'dim': (122, 90, 28),
    'globe': (16, 11, 3), 'land_glow': (90, 60, 0),
}

DEFAULT_CONFIG = {
    "buttons": {"A": 3, "B": 4, "X": 6, "Y": 5, "L": 7, "R": 8, "SELECT": 9, "START": 10, "MENU": 11},
    "feeds": [
        {"name": "adsb.lol", "base": "https://api.adsb.lol/v2"},
        {"name": "airplanes.live", "base": "http://api.airplanes.live/v2"}
    ],
    "routes_url": "https://api.adsb.lol/api/0/routeset",
    "poll_seconds": 6,
    "alerts_seconds": 40,
    "mil_seconds": 30,
    "scanlines": True,
    "fps": 30,
    "home": {"lat": 51.47, "lon": -0.45, "zoom": 6.0}
}
CALIB_ORDER = ["A", "B", "X", "Y", "L", "R", "SELECT", "START", "MENU"]

BIZJETS = {
    'GLF4', 'GLF5', 'GLF6', 'GL5T', 'GL6T', 'GL7T', 'GLEX', 'G280', 'GA5C', 'GA6C', 'GA7C', 'GA8C',
    'F900', 'FA7X', 'FA8X', 'F2TH', 'FA50', 'FA6X', 'C68A', 'C700', 'C750', 'C680', 'C56X', 'C560',
    'C25A', 'C25B', 'C25C', 'C510', 'C525', 'CL30', 'CL35', 'CL60', 'LJ35', 'LJ45', 'LJ60', 'LJ75',
    'E35L', 'E50P', 'E55P', 'E545', 'E550', 'PC12', 'PC24', 'H25B', 'BE40', 'PRM1', 'HDJT', 'SF50',
    'B737', 'BBJ2', 'A319'  # A319/B737 only count as private when they don't carry an airline callsign
}
AIRLINE_ONLY = {'B737', 'BBJ2', 'A319'}

# [IATA, city, lat, lon]
AIRPORTS = [
    ('DXB', 'DUBAI', 25.253, 55.365), ('DWC', 'DUBAI WORLD C.', 24.896, 55.161), ('AUH', 'ABU DHABI', 24.433, 54.651),
    ('SHJ', 'SHARJAH', 25.329, 55.517), ('RKT', 'RAS AL KHAIMAH', 25.613, 55.939), ('FJR', 'FUJAIRAH', 25.112, 56.324),
    ('AAN', 'AL AIN', 24.262, 55.609), ('DOH', 'DOHA', 25.273, 51.608), ('BAH', 'BAHRAIN', 26.271, 50.634),
    ('KWI', 'KUWAIT', 29.227, 47.969), ('MCT', 'MUSCAT', 23.593, 58.284), ('RUH', 'RIYADH', 24.958, 46.699),
    ('JED', 'JEDDAH', 21.680, 39.157), ('DMM', 'DAMMAM', 26.471, 49.798), ('MED', 'MEDINA', 24.553, 39.705),
    ('IKA', 'TEHRAN', 35.416, 51.152), ('KHI', 'KARACHI', 24.907, 67.161), ('DEL', 'DELHI', 28.566, 77.103),
    ('BOM', 'MUMBAI', 19.089, 72.868), ('BKK', 'BANGKOK', 13.690, 100.750), ('SIN', 'SINGAPORE', 1.359, 103.989),
    ('HKG', 'HONG KONG', 22.308, 113.918), ('PVG', 'SHANGHAI', 31.143, 121.805), ('PEK', 'BEIJING', 40.080, 116.585),
    ('ICN', 'SEOUL', 37.460, 126.440), ('HND', 'TOKYO', 35.552, 139.780), ('SYD', 'SYDNEY', -33.946, 151.177),
    ('IST', 'ISTANBUL', 41.275, 28.752), ('CAI', 'CAIRO', 30.122, 31.406), ('ATH', 'ATHENS', 37.936, 23.947),
    ('FCO', 'ROME', 41.800, 12.239), ('FRA', 'FRANKFURT', 50.033, 8.571), ('MUC', 'MUNICH', 48.354, 11.786),
    ('ZRH', 'ZURICH', 47.465, 8.549), ('AMS', 'AMSTERDAM', 52.310, 4.768), ('CDG', 'PARIS', 49.010, 2.548),
    ('LHR', 'LONDON', 51.470, -0.454), ('DUB', 'DUBLIN', 53.421, -6.270), ('MAD', 'MADRID', 40.472, -3.561),
    ('BCN', 'BARCELONA', 41.297, 2.078), ('PMI', 'PALMA', 39.552, 2.739), ('AGP', 'MALAGA', 36.675, -4.499),
    ('SVQ', 'SEVILLE', 37.418, -5.893), ('VLC', 'VALENCIA', 39.489, -0.482), ('LIS', 'LISBOA', 38.774, -9.134),
    ('OPO', 'PORTO', 41.248, -8.681), ('FAO', 'FARO', 37.014, -7.966), ('CMN', 'CASABLANCA', 33.367, -7.590),
    ('ADD', 'ADDIS ABABA', 8.978, 38.799), ('NBO', 'NAIROBI', -1.319, 36.928), ('JNB', 'JOHANNESBURG', -26.139, 28.246),
    ('JFK', 'NEW YORK', 40.641, -73.778), ('ATL', 'ATLANTA', 33.637, -84.428), ('ORD', 'CHICAGO', 41.974, -87.907),
    ('LAX', 'LOS ANGELES', 33.942, -118.408), ('SFO', 'SAN FRANCISCO', 37.621, -122.379), ('MIA', 'MIAMI', 25.796, -80.287),
    ('YYZ', 'TORONTO', 43.678, -79.625), ('MEX', 'MEXICO CITY', 19.436, -99.072), ('BOG', 'BOGOTA', 4.702, -74.147),
    ('GRU', 'SAO PAULO', -23.432, -46.469), ('EZE', 'BUENOS AIRES', -34.822, -58.536), ('SCL', 'SANTIAGO', -33.393, -70.786),
]
SQK_TXT = {'7700': 'EMERGENCY', '7600': 'RADIO FAILURE', '7500': 'UNLAWFUL INTERFERENCE'}
FILTERS = ['ALL', 'MILITARY', 'PRIVATE', 'ALERT']
LBL = ['AUTO', 'ON', 'OFF']


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(CONFIG) as fh:
            user = json.load(fh)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    except Exception:
        pass
    return cfg


def save_json(path, data):
    try:
        tmp = path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def utc():
    return time.strftime('%H:%M:%SZ', time.gmtime())


def vec(lat, lon):
    a, b = lat * DEG, lon * DEG
    return (math.cos(a) * math.cos(b), math.cos(a) * math.sin(b), math.sin(a))


def fl(alt):
    if alt is None:
        return '----'
    if alt == 'ground' or (isinstance(alt, (int, float)) and alt < 500):
        return 'GND'
    return 'FL%03d' % int(round(alt / 100.0))


def num(n):
    return '{:,}'.format(int(n))


def clip(s, n):
    s = s or ''
    return s if len(s) <= n else s[:n - 1] + '…'


def haversine(la1, lo1, la2, lo2):
    a = math.sin((la2 - la1) * DEG / 2) ** 2 + math.cos(la1 * DEG) * math.cos(la2 * DEG) * math.sin((lo2 - lo1) * DEG / 2) ** 2
    return 2 * RE * math.asin(min(1.0, math.sqrt(a)))


# ---------------------------------------------------------------- map
class CoastMap:
    """Precomputed coastline/border arcs, each with a bounding cap for fast culling."""

    def __init__(self, path, q):
        with open(path) as fh:
            arcs = json.load(fh)
        self.arcs = []
        for a in arcs:
            pts = []
            sx = sy = sz = 0.0
            for j in range(0, len(a), 2):
                lo, la = a[j] / q * DEG, a[j + 1] / q * DEG
                cl, sl, cL, sL = math.cos(la), math.sin(la), math.cos(lo), math.sin(lo)
                pts.append((cl, sl, cL, sL))
                sx += cl * cL
                sy += cl * sL
                sz += sl
            n = math.sqrt(sx * sx + sy * sy + sz * sz) or 1
            c = (sx / n, sy / n, sz / n)
            rad = 0.0
            for cl, sl, cL, sL in pts:
                d = c[0] * cl * cL + c[1] * cl * sL + c[2] * sl
                rad = max(rad, math.acos(max(-1.0, min(1.0, d))))
            self.arcs.append((c, rad, pts))


class View:
    def __init__(self, lat, lon, zoom):
        self.lat, self.lon, self.z, self.zt = lat, lon, zoom, zoom
        self.setup()

    def setup(self):
        self.c0, self.s0 = math.cos(self.lat * DEG), math.sin(self.lat * DEG)
        self.cl0, self.sl0 = math.cos(self.lon * DEG), math.sin(self.lon * DEG)
        self.R = BASER * self.z
        self.cvec = vec(self.lat, self.lon)
        # visible angle from the centre (out to the corner of the globe area)
        self.vang = math.asin(min(1.0, 300.0 / self.R)) if self.R > 300 else math.pi / 2

    def proj_trig(self, cl, sl, cL, sL):
        cd = cL * self.cl0 + sL * self.sl0
        cc = self.s0 * sl + self.c0 * cl * cd
        return (GCX + self.R * cl * (sL * self.cl0 - cL * self.sl0), GCY - self.R * (self.c0 * sl - self.s0 * cl * cd), cc)

    def proj(self, lat, lon):
        la, lo = lat * DEG, lon * DEG
        return self.proj_trig(math.cos(la), math.sin(la), math.cos(lo), math.sin(lo))

    def km_per_px(self):
        return RE / self.R

    def capture_nm(self):
        return min(250, max(10, int(self.vang * RE / 1.852)))


# ---------------------------------------------------------------- network
class Feed(threading.Thread):
    """Thread that polls the APIs and queues results for the main loop."""

    def __init__(self, cfg, demo=False):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.demo = demo
        self.lock = threading.Lock()
        self.want = (51.47, -0.45, 250)
        self.want_mil = False
        self.want_route = None
        self.out = collections.deque()
        self.status = 'STARTING'
        self.source = '—'
        self.ok = False
        self.last_ok = 0
        self.stop = False
        self.feed_idx = 0
        self.routes = {}
        self._demo_planes = []

    def request(self, path):
        feeds = self.cfg['feeds']
        last_err = None
        for k in range(len(feeds)):
            f = feeds[(self.feed_idx + k) % len(feeds)]
            url = f['base'].rstrip('/') + path
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Birdwatcher/%s (RG35XX SP)' % VERSION})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode('utf-8'))
                self.feed_idx = (self.feed_idx + k) % len(feeds)
                self.source = f['name']
                return data
            except Exception as e:
                last_err = e
                time.sleep(1.1)
        raise last_err or RuntimeError('no feeds')

    def get_route(self, cs, lat, lon):
        body = json.dumps({'planes': [{'callsign': cs, 'lat': lat, 'lng': lon}]}).encode()
        req = urllib.request.Request(self.cfg['routes_url'], data=body, method='POST',
                                     headers={'Content-Type': 'application/json', 'User-Agent': 'Birdwatcher/%s' % VERSION})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode('utf-8'))
        if isinstance(data, list) and data:
            d = data[0]
            iata = d.get('_airport_codes_iata') or d.get('airport_codes') or ''
            names, aps = [], []
            for ap in d.get('_airports', []) or []:
                code = ap.get('iata') or ap.get('icao') or ''
                names.append((code, (ap.get('location') or ap.get('name') or '').upper()))
                aps.append({'code': code, 'icao': ap.get('icao') or '', 'city': (ap.get('location') or '').upper(),
                            'name': ap.get('name') or '', 'country': ap.get('countryiso2') or '',
                            'lat': ap.get('lat'), 'lon': ap.get('lon')})
            return {'codes': iata.split('-') if iata else [], 'names': names, 'airports': aps,
                    'plausible': bool(d.get('plausible', True))}
        return {'codes': [], 'names': [], 'airports': []}

    def run(self):
        if self.demo:
            return self.run_demo()
        t_alert = 0
        t_mil = 0
        sq_cycle = ['7700', '7600', '7500']
        sq_i = 0
        while not self.stop:
            with self.lock:
                lat, lon, rad = self.want
                mil = self.want_mil
                route = self.want_route
                self.want_route = None
            try:
                data = self.request('/point/%.4f/%.4f/%d' % (lat, lon, rad))
                self.out.append(('point', data.get('ac') or []))
                self.ok, self.last_ok = True, time.time()
                self.status = 'OK'
            except Exception as e:
                self.ok = False
                self.status = 'NO NETWORK' if isinstance(e, urllib.error.URLError) else 'ERROR'
                self.out.append(('log', 'FEED X %s' % str(e)[:60], 'red'))
            time.sleep(1.1)
            if route:
                cs, la, lo = route
                try:
                    rt = self.get_route(cs, la, lo)
                    rt['source'] = 'adsb.lol'
                    self.routes[cs] = rt
                except Exception as e:
                    print('route lookup %s failed: %r' % (cs, e), flush=True)
                    self.routes[cs] = {'codes': [], 'names': [], 'airports': [], 'error': str(e)[:60]}
                time.sleep(1.1)
            now = time.time()
            if now - t_alert > self.cfg['alerts_seconds'] / 3.0:
                t_alert = now
                sq = sq_cycle[sq_i % 3]
                sq_i += 1
                try:
                    data = self.request('/sqk/%s' % sq)
                    self.out.append(('alerts', sq, data.get('ac') or []))
                except Exception:
                    pass
                time.sleep(1.1)
            if mil and now - t_mil > self.cfg['mil_seconds']:
                t_mil = now
                try:
                    data = self.request('/mil')
                    self.out.append(('mil', data.get('ac') or []))
                except Exception:
                    pass
                time.sleep(1.1)
            wait = max(0.0, self.cfg['poll_seconds'] - 2.2)
            t0 = time.time()
            while time.time() - t0 < wait and not self.stop:
                time.sleep(0.2)

    # --- demo mode: simulated traffic around the centre, in the same format as the API
    def run_demo(self):
        cs_pref = ['UAE', 'FDB', 'ETD', 'QTR', 'SVA', 'GFA', 'OMA', 'IAW', 'PIA', 'AIC', 'BAW', 'DLH', 'THY', 'KLM']
        types = ['B77W', 'A388', 'B789', 'A35K', 'B38M', 'A320', 'A321', 'B738', 'A20N']
        rnd = random.Random(7)
        planes = []
        lat0, lon0 = self.want[0], self.want[1]
        for i in range(260):
            kind = rnd.random()
            p = {'hex': '%06x' % rnd.randrange(16 ** 6), 'lat': lat0 + rnd.uniform(-6, 6), 'lon': lon0 + rnd.uniform(-7, 7),
                 'track': rnd.uniform(0, 360), 'gs': rnd.uniform(380, 500), 'alt_baro': rnd.choice(range(24000, 41000, 1000)),
                 'baro_rate': rnd.choice([0, 0, 0, 1280, -960]), 'squawk': '%04o' % rnd.randrange(0o1000, 0o7000)}
            if kind < 0.04:
                p.update(flight='RCH%d' % rnd.randrange(100, 999), t=rnd.choice(['C17', 'K35R']), dbFlags=1, r='—', hex='ae%04x' % rnd.randrange(16 ** 4))
            elif kind < 0.09:
                p.update(flight='A6%s' % ''.join(rnd.choice('ABCDEFGHJKLMNPRSTUVWXYZ') for _ in range(3)), t=rnd.choice(['GLF6', 'GL7T', 'C68A']), r='A6-PRV', dbFlags=0)
            else:
                p.update(flight='%s%d' % (rnd.choice(cs_pref), rnd.randrange(1, 999)), t=rnd.choice(types), r='A6-%s' % ''.join(rnd.choice('ABCDEFGHJKLMNPRSTUVWXYZ') for _ in range(3)), dbFlags=0)
            planes.append(p)
        planes[5]['squawk'] = '7700'
        last = time.time()
        self.source = 'DEMO'
        while not self.stop:
            now = time.time()
            dt = now - last
            last = now
            for p in planes:
                d = p['gs'] * 1.852 / 3600 * dt
                p['lat'] += d * math.cos(p['track'] * DEG) / 111.2
                p['lon'] += d * math.sin(p['track'] * DEG) / (111.2 * max(0.2, math.cos(p['lat'] * DEG)))
            with self.lock:
                route = self.want_route
                self.want_route = None
            if route:
                a, b = rnd.sample(AIRPORTS, 2)
                aps = [{'code': x[0], 'icao': '', 'city': x[1], 'name': x[1].title() + ' International Airport',
                        'country': '', 'lat': x[2], 'lon': x[3]} for x in (a, b)]
                self.routes[route[0]] = {'codes': [a[0], b[0]], 'names': [(a[0], a[1]), (b[0], b[1])], 'airports': aps, 'plausible': True}
            self.out.append(('point', [dict(p) for p in planes]))
            self.ok, self.last_ok, self.status = True, now, 'DEMO'
            time.sleep(self.cfg['poll_seconds'])


# ---------------------------------------------------------------- offline routes
class RouteDB:
    """Offline route lookup from the Virtual Radar Server standing data (CC0), bundled in data/routes.

    Routes are split by the callsign's first character into gzip files that load on demand.
    """

    def __init__(self, base):
        self.base = base
        self.lock = threading.Lock()
        self.airports = None
        self.shards = {}

    def available(self):
        return os.path.exists(os.path.join(self.base, 'airports.json.gz'))

    def _airports(self):
        if self.airports is None:
            with gzip.open(os.path.join(self.base, 'airports.json.gz'), 'rt', encoding='utf-8') as fh:
                self.airports = json.load(fh)
        return self.airports

    def _shard(self, ch):
        key = ch if ch.isalnum() else '_'
        if key not in self.shards:
            d = {}
            path = os.path.join(self.base, key + '.gz')
            if os.path.exists(path):
                with gzip.open(path, 'rt', encoding='utf-8') as fh:
                    for line in fh:
                        cs, _, codes = line.rstrip('\n').partition(',')
                        d[cs] = codes
            self.shards[key] = d
        return self.shards[key]

    def lookup(self, cs, pos=None):
        cs = cs.strip().upper()
        if not cs:
            return None
        cands = [cs]
        i = 0
        while i < len(cs) and cs[i].isalpha():
            i += 1
        if 0 < i < len(cs) and cs[i:].isdigit():
            cands.append(cs[:i] + str(int(cs[i:])))  # UAE001 -> UAE1
        with self.lock:
            shard = self._shard(cs[0])
            codes = next((shard[c] for c in cands if c in shard), None)
            if not codes:
                return None
            apdb = self._airports()
        aps = []
        for icao in codes.split('-'):
            a = apdb.get(icao)
            if not a:
                continue
            iata, name, city, cc, lat, lon = a
            aps.append({'code': iata or icao, 'icao': icao, 'city': (city or '').upper(), 'name': name,
                        'country': cc, 'lat': lat, 'lon': lon})
        if len(aps) < 2:
            return None
        return {'codes': [a['code'] for a in aps], 'names': [(a['code'], a['city']) for a in aps], 'airports': aps,
                'plausible': plausible(aps, pos) if pos else True, 'source': 'offline'}


def plausible(aps, pos):
    """True if the aircraft sits reasonably close to one of the route's legs."""
    la, lo = pos
    for a, b in zip(aps, aps[1:]):
        seg = haversine(a['lat'], a['lon'], b['lat'], b['lon'])
        d13 = haversine(a['lat'], a['lon'], la, lo) / RE
        if seg < 1:
            continue
        t13, t12 = bearing(a['lat'], a['lon'], la, lo), bearing(a['lat'], a['lon'], b['lat'], b['lon'])
        xt = math.asin(max(-1.0, min(1.0, math.sin(d13) * math.sin(t13 - t12))))
        at = math.acos(max(-1.0, min(1.0, math.cos(d13) / max(1e-9, math.cos(xt))))) * RE
        if abs(xt * RE) < max(250.0, seg * 0.2) and at < seg + 150 and math.cos(t13 - t12) > -0.2:
            return True
    return False


def bearing(la1, lo1, la2, lo2):
    y = math.sin((lo2 - lo1) * DEG) * math.cos(la2 * DEG)
    x = math.cos(la1 * DEG) * math.sin(la2 * DEG) - math.sin(la1 * DEG) * math.cos(la2 * DEG) * math.cos((lo2 - lo1) * DEG)
    return math.atan2(y, x)


# ---------------------------------------------------------------- aircraft
class Plane:
    __slots__ = ('hex', 'cs', 'reg', 'type', 'lat', 'lon', 'alt', 'gs', 'trk', 'sq', 'vr', 'flags', 't_pos',
                 'last_seen', 'trail', 'kind', 'alert', 'emerg')

    def __init__(self, hx):
        self.hex = hx
        self.cs = self.reg = self.type = ''
        self.lat = self.lon = None
        self.alt = None
        self.gs = self.trk = self.vr = None
        self.sq = ''
        self.flags = 0
        self.t_pos = self.last_seen = 0
        self.trail = collections.deque(maxlen=40)
        self.kind = 'air'
        self.alert = False
        self.emerg = ''

    def update(self, a, now):
        self.cs = (a.get('flight') or self.cs or '').strip()
        self.reg = a.get('r') or self.reg
        self.type = a.get('t') or self.type
        alt = a.get('alt_baro', a.get('alt_geom'))
        if alt is not None:
            self.alt = alt
        for src, dst in (('gs', 'gs'), ('track', 'trk'), ('baro_rate', 'vr')):
            if a.get(src) is not None:
                setattr(self, dst, a[src])
        if a.get('squawk'):
            self.sq = a['squawk']
        self.flags = a.get('dbFlags', self.flags) or 0
        self.emerg = a.get('emergency') or ''
        lat, lon = a.get('lat'), a.get('lon')
        if lat is not None and lon is not None:
            seen = float(a.get('seen_pos') or 0)
            if self.lat is None or abs(lat - self.lat) + abs(lon - self.lon) > 0.002:
                self.trail.append((lat, lon))
            self.lat, self.lon = lat, lon
            self.t_pos = now - min(seen, 30)
        self.last_seen = now
        if self.flags & 1:
            self.kind = 'mil'
        elif self.type in BIZJETS and not (self.type in AIRLINE_ONLY and len(self.cs) >= 4 and self.cs[:3].isalpha() and self.cs[3:].isdigit()):
            self.kind = 'priv'
        else:
            self.kind = 'air'
        self.alert = self.sq in SQK_TXT or (self.emerg not in ('', 'none'))

    def pos(self, now):
        """Estimated position (dead reckoning from the last report)."""
        if self.lat is None:
            return None
        if not self.gs or self.trk is None or self.alt == 'ground':
            return self.lat, self.lon
        dt = min(60.0, max(0.0, now - self.t_pos))
        d = self.gs * 1.852 / 3600.0 * dt
        la = self.lat + d * math.cos(self.trk * DEG) / 111.2
        lo = self.lon + d * math.sin(self.trk * DEG) / (111.2 * max(0.2, math.cos(self.lat * DEG)))
        return la, lo

    @property
    def label(self):
        return self.cs or self.reg or self.hex.upper()


# ---------------------------------------------------------------- app
class App:
    def __init__(self, gfx, cfg, demo):
        self.g = gfx
        self.cfg = cfg
        st = {}
        try:
            with open(STATE) as fh:
                st = json.load(fh)
        except Exception:
            pass
        home = st.get('view') or cfg['home']
        self.v = View(home['lat'], home['lon'], home['zoom'])
        self.filter = st.get('filter', 0)
        self.labels = st.get('labels', 0)
        self.planes = {}
        self.alerts_seen = set()
        self.sel = None
        self.follow = False
        self.help = False
        self.card = False
        self.mode = 'boot'
        self.boot_t = 0
        self.frame = 0
        self.held = set()
        self.log = collections.deque(maxlen=40)
        self.toast_txt, self.toast_t = '', 0
        self.fonts = {}
        self.tcache = {}
        self.cache = None
        self.cache_key = None
        self.last_key = None
        self.feed = Feed(cfg, demo)
        self.routedb = RouteDB(os.path.join(BASE, 'data', 'routes'))
        self.route_pending = set()
        self.feed.want = (self.v.lat, self.v.lon, self.v.capture_nm())
        self.map_lo = self.map_hi = None
        self.scan_rects = [(0, y, W, 1) for y in range(0, H, 3)] if cfg.get('scanlines', True) else None
        self.addlog('BIRDWATCHER %s · %s' % (VERSION, 'DEMO MODE' if demo else 'link adsb.lol'))

    # ---------- helpers
    def font(self, kind, size):
        key = (kind, size)
        if key not in self.fonts:
            self.fonts[key] = sdl.Font(self.g, os.path.join(BASE, 'fonts', '%s%d' % (kind, size)))
        return self.fonts[key]

    def text(self, s, x, y, kind, size, col, align='left'):
        return self.font(kind, size).draw(s, int(x), int(y), col, align)

    def reset_textures(self):
        for f in self.fonts.values():
            f.flush()
        if self.cache:
            self.cache.destroy()
        self.cache = None
        self.cache_key = None

    def addlog(self, s, col='amb'):
        self.log.append(('[%s] %s' % (utc(), s), col))

    def toast(self, s):
        self.toast_txt, self.toast_t = s, time.time()

    def visible(self, p):
        if self.filter == 1:
            return p.kind == 'mil'
        if self.filter == 2:
            return p.kind == 'priv'
        if self.filter == 3:
            return p.alert
        return True

    def color(self, p):
        if p.alert:
            return COL['red'] if self.frame % 30 < 15 else COL['redD']
        return COL['cyan'] if p.kind == 'mil' else COL['mag'] if p.kind == 'priv' else COL['amb']

    # ---------- input
    def press(self, k):
        if self.mode == 'boot':
            if k in ('START', 'A', 'B', 'X'):
                self.mode = 'run'
            return
        if self.help:
            if k in ('B', 'SELECT', 'START', 'A'):
                self.help = False
            return
        if self.card:
            if k in ('B', 'Y', 'A'):
                self.card = False
            elif k == 'START' and self.sel:
                self.follow = not self.follow
                self.toast(('FOLLOWING ' + self.sel.label) if self.follow else 'FOLLOW OFF')
            elif k == 'SELECT':
                self.help = True
            return
        v = self.v
        if k == 'R':
            v.zt = min(80.0, v.zt * 1.6)
        elif k == 'L':
            v.zt = max(0.9, v.zt / 1.6)
        elif k == 'A':
            self.lock_nearest()
        elif k == 'B':
            if self.follow:
                self.follow = False
                self.toast('FOLLOW OFF')
            elif self.sel:
                self.sel = None
                self.toast('TRACK RELEASED')
        elif k == 'X':
            self.filter = (self.filter + 1) % 4
            self.addlog('FILTER > ' + FILTERS[self.filter] + (' · querying global /mil' if self.filter == 1 else ''))
            if self.sel and not self.visible(self.sel):
                self.sel, self.follow, self.card = None, False, False
        elif k == 'Y':
            if self.sel:
                self.card = True
                self.request_route(self.sel)
            else:
                self.labels = (self.labels + 1) % 3
                self.toast('LABELS > ' + LBL[self.labels])
        elif k == 'START':
            if self.sel:
                self.follow = not self.follow
                self.toast(('FOLLOWING ' + self.sel.label) if self.follow else 'FOLLOW OFF')
                if self.follow and v.zt < 6:
                    v.zt = 8
            else:
                self.toast('LOCK AN AIRCRAFT FIRST (A)')
        elif k == 'SELECT':
            self.help = True

    def lock_nearest(self):
        now = time.time()
        cands = []
        for p in self.planes.values():
            if not self.visible(p):
                continue
            ps = p.pos(now)
            if not ps:
                continue
            x, y, cc = self.v.proj(*ps)
            if cc <= 0:
                continue
            d = math.hypot(x - GCX, y - GCY)
            if d < 70:
                cands.append((d, p))
        cands.sort(key=lambda e: e[0])
        if not cands:
            self.toast('NO CONTACTS IN RETICLE')
            return
        p = cands[0][1]
        if self.sel and len(cands) > 1:
            for i, (_, q) in enumerate(cands):
                if q is self.sel:
                    p = cands[(i + 1) % len(cands)][1]
                    break
        self.sel = p
        self.addlog('LOCKED %s · %s · %s · %s' % (p.label, p.type or '?', p.hex.upper(), fl(p.alt)),
                    'cyan' if p.kind == 'mil' else 'mag' if p.kind == 'priv' else 'amb')
        self.request_route(p)

    def request_route(self, p):
        """Offline database first (instant, no network); adsb.lol only if the callsign isn't there."""
        if not p.cs or p.cs in self.feed.routes or p.cs in self.route_pending:
            return
        ps = p.pos(time.time())
        if not ps:
            return
        self.route_pending.add(p.cs)
        threading.Thread(target=self._route_job, args=(p.cs, ps), daemon=True).start()

    def _route_job(self, cs, ps):
        rt = None
        try:
            if self.routedb.available():
                rt = self.routedb.lookup(cs, ps)
        except Exception as e:
            print('offline route lookup %s failed: %r' % (cs, e), flush=True)
        if rt:
            self.feed.routes[cs] = rt
        else:
            with self.feed.lock:
                self.feed.want_route = (cs, ps[0], ps[1])
        self.route_pending.discard(cs)

    # ---------- data
    def ingest(self):
        now = time.time()
        while self.feed.out:
            item = self.feed.out.popleft()
            kind = item[0]
            if kind == 'log':
                self.addlog(item[1], item[2])
                continue
            acs = item[2] if kind == 'alerts' else item[1]
            for a in acs:
                hx = (a.get('hex') or '').lower()
                if not hx or a.get('lat') is None:
                    continue
                p = self.planes.get(hx)
                if p is None:
                    p = self.planes[hx] = Plane(hx)
                was = p.alert
                p.update(a, now)
                if p.alert and not was and (hx, p.sq) not in self.alerts_seen:
                    self.alerts_seen.add((hx, p.sq))
                    self.addlog('SQK %s %s · %s · %s %s' % (p.sq, SQK_TXT.get(p.sq, p.emerg.upper()), p.label, p.type or '?', fl(p.alt)), 'red')
        # drop aircraft we no longer hear
        if self.frame % 60 == 0:
            for hx in [h for h, p in self.planes.items() if now - p.last_seen > 120 and p is not self.sel]:
                del self.planes[hx]
            if self.sel and now - self.sel.last_seen > 180:
                self.addlog('LOST %s' % self.sel.label)
                self.sel, self.follow, self.card = None, False, False

    # ---------- update
    def update(self, dt):
        v = self.v
        sp = 60.0 / (v.z ** 0.85) * dt
        cosl = max(0.25, math.cos(v.lat * DEG))
        if 'left' in self.held:
            v.lon -= sp / cosl
        if 'right' in self.held:
            v.lon += sp / cosl
        if 'up' in self.held:
            v.lat = min(85.0, v.lat + sp)
        if 'down' in self.held:
            v.lat = max(-85.0, v.lat - sp)
        if self.held and self.follow:
            self.follow = False
            self.toast('FOLLOW OFF')
        v.lon = ((v.lon + 540.0) % 360.0) - 180.0
        if self.follow and self.sel:
            ps = self.sel.pos(time.time())
            if ps:
                d = ((ps[1] - v.lon + 540) % 360) - 180
                k = min(1.0, dt * 4)
                v.lon += d * k
                v.lat += (ps[0] - v.lat) * k
        v.z += (v.zt - v.z) * min(1.0, dt * 6)
        if abs(v.z - v.zt) < 0.002:
            v.z = v.zt
        v.setup()
        with self.feed.lock:
            self.feed.want = (v.lat, v.lon, v.capture_nm())
            self.feed.want_mil = self.filter == 1

    # ---------- drawing: cached base layer (globe, grid, coastlines, airports)
    def base_layer(self):
        v = self.v
        key = (round(v.lat, 3), round(v.lon, 3), round(v.z, 3))
        moving = key != self.last_key
        self.last_key = key
        key = key + (moving,)
        if key == self.cache_key and self.cache is not None:
            return self.cache
        g = self.g
        if self.cache is None:
            self.cache = g.new_target(PX, GY1 - GY0)
        s = self.cache
        if s is not None:
            g.target(s)
            oy = GY0
        else:  # no render targets: draw straight to screen every frame
            oy = 0
            g.set_clip((0, GY0, PX, GY1 - GY0))
        g.fill(COL['bg'], (0, GY0 - oy, PX, GY1 - GY0))
        R = v.R
        g.disc(COL['globe'], GCX, GCY - oy, R)
        self.draw_grid(s, oy)
        if R < 4000:
            g.circle(COL['ambD'], GCX, GCY - oy, R)
        # while moving: light map with no glow to stay smooth; when still: detailed map
        cmap = self.map_lo if (v.z < 3.2 or moving) else self.map_hi
        self.draw_coast(s, oy, cmap, not moving)
        self.draw_capture(s, oy)
        if v.z >= 3.2:
            for code, name, la, lo in AIRPORTS:
                x, y, cc = v.proj(la, lo)
                if cc <= 0 or not (0 <= x < PX and GY0 <= y < GY1):
                    continue
                g.rect(COL['ambD'], (int(x) - 3, int(y) - 3 - oy, 7, 7))
                if v.z >= 5:
                    self.text(code, x - 9, y + 15 - oy, 'M', 11, COL['dim'])
        if s is not None:
            g.target(None)
            self.cache_key = key
        else:
            g.set_clip(None)
        return s

    def draw_coast(self, s, oy, cmap, hq=True):
        v = self.v
        cv = v.cvec
        lim = v.vang
        c0, s0, cl0, sl0, R = v.c0, v.s0, v.cl0, v.sl0, v.R
        col, glow = COL['amb'], COL['land_glow']
        runs = []
        for c, rad, pts in cmap.arcs:
            d = math.acos(max(-1.0, min(1.0, c[0] * cv[0] + c[1] * cv[1] + c[2] * cv[2])))
            if d - rad > lim:
                continue
            run = []
            cy = GCY - oy
            for cl, sl, cL, sL in pts:
                cd = cL * cl0 + sL * sl0
                if s0 * sl + c0 * cl * cd < 0:
                    if len(run) > 2:
                        runs.append(run)
                    run = []
                    continue
                run.append(GCX + R * cl * (sL * cl0 - cL * sl0))
                run.append(cy - R * (c0 * sl - s0 * cl * cd))
            if len(run) > 2:
                runs.append(run)
        g = self.g
        if hq:  # phosphor glow: the same line offset in a darker tone
            for run in runs:
                g.lines_flat(glow, [v + 1 for v in run])
                g.lines_flat(glow, [v - 1 for v in run])
        for run in runs:
            g.lines_flat(col, run)

    def draw_grid(self, s, oy):
        v = self.v
        step = 15 if v.z < 4 else 5 if v.z < 12 else 1
        fine = step < 5
        lor = 60.0 / v.z + 5 if fine else 180
        lar = 40.0 / v.z + 5 if fine else 90
        inc = 0.5 if fine else 3

        g = self.g

        def line(pts):
            run = []
            for la, lo in pts:
                x, y, cc = v.proj(la, lo)
                if cc < 0:
                    g.lines_flat(COL['grid'], run)
                    run = []
                    continue
                run.append(x)
                run.append(y - oy)
            g.lines_flat(COL['grid'], run)

        lo = math.floor((v.lon - lor) / step) * step
        while lo <= v.lon + lor:
            la_a, la_b = max(-88.0, v.lat - lar), min(88.0, v.lat + lar)
            n = int((la_b - la_a) / inc) + 1
            line([(la_a + i * inc, lo) for i in range(n + 1)])
            lo += step
        la = math.ceil(max(-88.0, v.lat - lar) / step) * step
        while la <= min(88.0, v.lat + lar):
            n = int(2 * lor / inc) + 1
            line([(la, v.lon - lor + i * inc) for i in range(n + 1)])
            la += step

    def draw_capture(self, s, oy):
        """Capture circle: the API only returns aircraft within 250 NM."""
        v = self.v
        nm = v.capture_nm()
        if nm < 250:
            return
        ang = nm * 1.852 / RE
        la0, lo0 = v.lat * DEG, v.lon * DEG
        pts = []
        for i in range(73):
            b = i * 5 * DEG
            la = math.asin(math.sin(la0) * math.cos(ang) + math.cos(la0) * math.sin(ang) * math.cos(b))
            lo = lo0 + math.atan2(math.sin(b) * math.sin(ang) * math.cos(la0), math.cos(ang) - math.sin(la0) * math.sin(la))
            x, y, cc = v.proj(la / DEG, lo / DEG)
            pts.append((x, y - oy))
        for i in range(0, len(pts) - 1, 2):
            self.g.line(COL['ambD'], pts[i], pts[i + 1])
        self.text('CAPTURE ZONE 250 NM', pts[0][0], pts[0][1] - 4, 'M', 11, COL['ambD'], 'center')

    # ---------- per-frame drawing
    def draw_planes(self):
        v = self.v
        now = time.time()
        icons = v.z >= 2.6
        show_l = self.labels == 1 or (self.labels == 0 and v.z >= 5)
        trails = v.z >= 4.5
        g = self.g
        labels = []
        tris = {}
        n = 0
        for p in self.planes.values():
            if not self.visible(p):
                continue
            ps = p.pos(now)
            if not ps:
                continue
            x, y, cc = v.proj(*ps)
            if cc <= 0 or x < -10 or x > PX + 10 or y < GY0 - 10 or y > GY1 + 10:
                continue
            n += 1
            col = self.color(p)
            is_sel = p is self.sel
            if (trails or is_sel) and len(p.trail) > 1:
                pts = []
                for la, lo in list(p.trail)[-(40 if is_sel else 10):]:
                    tx, ty, tc = v.proj(la, lo)
                    if tc > 0:
                        pts.append((tx, ty))
                pts.append((x, y))
                if len(pts) > 1:
                    g.lines(COL['white'] if is_sel else COL['ambDD'] if p.kind == 'air' else col, pts)
            if icons and p.trk is not None:
                a = p.trk * DEG
                sz = 4.5 if v.z >= 8 else 3.2
                sa, ca = math.sin(a), math.cos(a)
                pts = [(0, -sz * 1.4), (sz, sz), (0, sz * 0.45), (-sz, sz)]
                q = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
                tris.setdefault(COL['white'] if is_sel else col, []).extend((q[0], q[1], q[2], q[0], q[2], q[3]))
            else:
                g.fill(col, (int(x) - 1, int(y) - 1, 2, 2))
            if icons and not is_sel and (show_l or p.alert):
                labels.append((p.alert, math.hypot(x - GCX, y - GCY), x, y, p, col))
        for col, t in tris.items():
            g.triangles(col, t)
        labels.sort(key=lambda e: (not e[0], e[1]))
        occ = []
        for _, _, x, y, p, col in labels:
            if len(occ) >= 28:
                break
            r = (int(x) + 6, int(y) - 12, 56, 24)
            if any(r[0] < o[0] + o[2] and r[0] + r[2] > o[0] and r[1] < o[1] + o[3] and r[1] + r[3] > o[1] for o in occ):
                continue
            occ.append(r)
            self.text(p.label, x + 7, y - 2, 'M', 12, col)
            self.text(fl(p.alt), x + 7, y + 10, 'M', 11, COL['ambD'])
        if self.sel:
            p = self.sel
            ps = p.pos(now)
            if ps:
                x, y, cc = v.proj(*ps)
                if cc > 0:
                    r = int(9 + math.sin(self.frame / 8.0) * 2)
                    g.circle(COL['white'], x, y, r, 3)
                    self.text(p.label, x + r + 4, y - 3, 'M', 13, COL['white'])
                    self.text(fl(p.alt), x + r + 4, y + 10, 'M', 12, COL['amb'])
        return n

    def draw_globe(self):
        g = self.g
        base = self.base_layer()
        if base is not None:
            g.blit(base, 0, GY0)
        g.set_clip((0, GY0, PX, GY1 - GY0))
        n = self.draw_planes()
        # reticle
        c = COL['amb']
        for s, e in ((-22, -8), (8, 22)):
            g.line(c, (GCX + s, GCY), (GCX + e, GCY))
            g.line(c, (GCX, GCY + s), (GCX, GCY + e))
        g.fill_rects(COL['ambDD'], [(int(GCX + 70 * math.cos(i * DEG)), int(GCY + 70 * math.sin(i * DEG)), 2, 2) for i in range(0, 360, 8)])
        # radar sweep
        a = (self.frame / 45.0) % (2 * math.pi)
        g.line(COL['ambDD'], (GCX, GCY), (GCX + 150 * math.cos(a), GCY + 150 * math.sin(a)))
        g.set_clip(None)
        v = self.v
        g.fill((8, 5, 1), (0, GY0, 158, 36))
        g.fill((8, 5, 1), (PX - 132, GY0, 132, 36))
        self.text('%s%05.2f  %s%06.2f' % ('N' if v.lat >= 0 else 'S', abs(v.lat), 'E' if v.lon >= 0 else 'W', abs(v.lon)), 8, GY0 + 16, 'M', 13, COL['amb'])
        self.text('ZOOM %.1f×  ·  %d NM' % (v.z, v.capture_nm()), 8, GY0 + 31, 'M', 12, COL['ambD'])
        fc = [COL['amb'], COL['cyan'], COL['mag'], COL['red']][self.filter]
        self.text('FILTER ' + FILTERS[self.filter], PX - 8, GY0 + 16, 'M', 13, fc, 'right')
        self.text('%s IN VIEW' % num(n), PX - 8, GY0 + 31, 'M', 12, COL['ambD'], 'right')
        km = v.km_per_px() * 100
        nice = next((x for x in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000) if x >= km * 0.6), 5000)
        ln = int(nice / km * 100)
        g.fill_rects(COL['ambD'], [(8, GY1 - 12, ln, 2), (8, GY1 - 16, 1, 6), (8 + ln, GY1 - 16, 1, 6)])
        self.text('%s km' % num(nice), 12 + ln, GY1 - 8, 'M', 11, COL['ambD'])
        if self.follow:
            self.text('[ FOLLOWING ]', PX - 8, GY1 - 8, 'M', 12, COL['white'] if self.frame % 40 < 28 else COL['ambD'], 'right')
        if time.time() - self.toast_t < 1.8:
            w = self.font('M', 15).width(self.toast_txt) + 20
            r = (GCX - w // 2, GY1 - 48, w, 22)
            g.fill((8, 5, 1), r)
            g.rect(COL['amb'], r)
            self.text(self.toast_txt, GCX, GY1 - 32, 'M', 15, COL['amb'], 'center')

    def draw_header(self):
        s = self.g
        s.fill(COL['panel'], (0, 0, W, HDR))
        s.fill(COL['ambDD'], (0, HDR - 1, W, 1))
        self.text('BIRDWATCHER', 8, 17, 'M', 16, COL['amb'])
        self.text('> ADS-B OSINT', 120, 17, 'M', 13, COL['ambD'])
        f = self.feed
        age = time.time() - f.last_ok if f.last_ok else None
        if f.ok:
            st = ('*' if self.frame % 60 < 40 else ' ') + ' %s · %ds ago' % (f.source, int(age))
            col = COL['ambD']
        else:
            st = 'X %s' % f.status
            col = COL['red']
        self.text(st, 330, 17, 'M', 13, col, 'center')
        self.text('%s AC  %s' % (num(len(self.planes)), utc()), W - 8, 17, 'M', 13, COL['amb'], 'right')

    def row(self, y, k, val, col=None):
        self.text(k, PX + 10, y, 'M', 12, COL['dim'])
        self.text(val, W - 10, y, 'V', 22, col or COL['amb'], 'right')

    def draw_panel(self):
        s = self.g
        s.fill(COL['panel'], (PX, GY0, W - PX, GY1 - GY0))
        s.fill(COL['ambDD'], (PX, GY0, 1, GY1 - GY0))
        now = time.time()
        p = self.sel
        if p:
            col = self.color(p)
            self.text('TRACK', PX + 10, GY0 + 18, 'M', 12, COL['dim'])
            kt = {'mil': 'MILITARY', 'priv': 'PRIVATE'}.get(p.kind, 'COMMERCIAL')
            if p.flags & 4:
                kt += ' · PIA'
            if p.flags & 8:
                kt += ' · LADD'
            self.text(kt, W - 10, GY0 + 18, 'M', 12, COL['cyan'] if p.kind == 'mil' else COL['mag'] if p.kind == 'priv' else COL['ambD'], 'right')
            self.text(p.label, PX + 10, GY0 + 50, 'V', 38, col if p.alert else COL['white'])
            y = GY0 + 72
            self.row(y, 'HEX', p.hex.upper())
            y += 20
            self.row(y, 'REG', p.reg or '—')
            y += 20
            self.row(y, 'TYPE', p.type or '—')
            y += 20
            self.row(y, 'SQUAWK', p.sq or '—', col if p.alert else None)
            y += 12
            s.fill(COL['ambDD'], (PX + 10, y, W - PX - 20, 1))
            rt = self.feed.routes.get(p.cs)
            y += 24
            if rt and len(rt['codes']) >= 2:
                a, b = rt['codes'][0], rt['codes'][-1]
                self.text(a, PX + 10, y, 'V', 26, COL['amb'])
                self.text('>>', PX + (W - PX) // 2, y, 'V', 22, COL['ambD'], 'center')
                self.text(b, W - 10, y, 'V', 26, COL['amb'], 'right')
                names = rt.get('names') or []
                if len(names) >= 2:
                    self.text(names[0][1][:14], PX + 10, y + 14, 'M', 10, COL['dim'])
                    self.text(names[-1][1][:14], W - 10, y + 14, 'M', 10, COL['dim'], 'right')
            elif rt is None and p.cs:
                self.text('ROUTE: looking up…', PX + 10, y, 'M', 12, COL['dim'])
            else:
                self.text('ROUTE: unknown', PX + 10, y, 'M', 12, COL['dim'])
            y += 34 if (rt and len(rt['codes']) >= 2) else 22
            vr = p.vr or 0
            self.row(y, 'ALTITUDE', fl(p.alt))
            y += 20
            self.row(y, 'VERT. SPEED', ('+' if vr > 0 else '') + num(vr) + ' ft/min')
            y += 20
            self.row(y, 'GROUND SPEED', ('%d kt' % p.gs) if p.gs is not None else '—')
            y += 20
            self.row(y, 'TRACK', ('%03d°' % round(p.trk)) if p.trk is not None else '—')
            ps = p.pos(now)
            y += 20
            self.text('POSITION', PX + 10, y, 'M', 12, COL['dim'])
            self.text('seen %ds ago' % int(now - p.last_seen), W - 10, y, 'M', 12, COL['dim'], 'right')
            y += 20
            if ps:
                self.text('%.3f%s  %.3f%s' % (abs(ps[0]), 'N' if ps[0] >= 0 else 'S', abs(ps[1]), 'E' if ps[1] >= 0 else 'W'), W - 10, y, 'V', 22, COL['amb'], 'right')
            self.text('B RELEASE · START FOLLOW', PX + 10, GY1 - 8, 'M', 11, COL['dim'])
        else:
            self.text('IN RETICLE', PX + 10, GY0 + 18, 'M', 12, COL['dim'])
            cands = []
            for q in self.planes.values():
                if not self.visible(q):
                    continue
                ps = q.pos(now)
                if not ps:
                    continue
                x, y, cc = self.v.proj(*ps)
                if cc <= 0:
                    continue
                d = math.hypot(x - GCX, y - GCY)
                if d < 160:
                    cands.append((d, q))
            cands.sort(key=lambda e: e[0])
            if not cands:
                msg = 'Waiting for data…' if not self.planes else 'No contacts nearby.'
                self.text(msg, PX + 10, GY0 + 46, 'V', 20, COL['ambD'])
            for i, (d, q) in enumerate(cands[:13]):
                y = GY0 + 42 + i * 22
                if d < 70:
                    s.fill(COL['ambDD'], (PX + 4, y - 15, W - PX - 8, 20))
                self.text(q.label[:8], PX + 10, y, 'V', 20, self.color(q))
                self.text((q.type or '')[:4], PX + 98, y, 'V', 18, COL['ambD'])
                self.text(fl(q.alt), W - 10, y, 'V', 20, COL['amb'], 'right')
            self.text('A LOCK NEAREST', PX + 10, GY1 - 8, 'M', 11, COL['dim'])

    def draw_footer(self):
        s = self.g
        s.fill(COL['panel'], (0, GY1, W, FOOT))
        s.fill(COL['ambDD'], (0, GY1, W, 1))
        lines = list(self.log)[-4:]
        dimc = {'red': (160, 48, 48), 'cyan': (47, 138, 160), 'mag': (138, 90, 160), 'amb': COL['ambD']}
        for i, (t, c) in enumerate(lines):
            last = i == len(lines) - 1
            self.text(t if len(t) < 86 else t[:85] + '…', 8, GY1 + 16 + i * 14, 'M', 12, COL[c] if last else dimc.get(c, COL['ambD']))
        self.text('D-PAD ROTATE · L/R ZOOM · A LOCK · Y CARD · X FILTER · START FOLLOW · SELECT HELP', 8, H - 6, 'M', 10, COL['dim'])

    def draw_help(self):
        self.g.fill((4, 3, 1, 225))
        x, w, y = 60, 520, 66
        self.g.rect(COL['amb'], (x, y - 30, w, 392))
        self.text('BIRDWATCHER · HELP', x + 16, y - 6, 'M', 16, COL['amb'])
        L = [('D-PAD', 'rotate the globe (hold)'), ('L / R', 'zoom out / zoom in'),
             ('A', 'lock the nearest aircraft; again for the next one'),
             ('B', 'release the aircraft or stop following'), ('X', 'filter: all · military (global) · private · alert'),
             ('Y', 'full-screen card · labels if nothing locked'), ('START', 'follow the locked aircraft'),
             ('MENU', 'quit · also SELECT + START'), ('', ''),
             ('AMBER', 'commercial flight'), ('CYAN', 'military'), ('MAGENTA', 'private / business jet'),
             ('RED', 'squawk 7700 · 7600 · 7500')]
        cmap = {'CYAN': COL['cyan'], 'MAGENTA': COL['mag'], 'RED': COL['red']}
        for k, val in L:
            y += 24
            self.text(k, x + 16, y, 'M', 13, cmap.get(k, COL['amb']))
            self.text(val, x + 110, y, 'V', 20, COL['ambD'])
        self.text('Data: adsb.lol · airplanes.live (non-commercial use)', x + 16, y + 34, 'V', 18, COL['dim'])
        self.text('B TO GO BACK', x + w - 16, y + 34, 'M', 12, COL['amb'] if self.frame % 40 < 28 else COL['ambD'], 'right')

    def draw_boot(self):
        self.g.clear(COL['bg'])
        f = self.feed
        lines = [('BIRDWATCHER OS %s · ANBERNIC RG35XX SP' % VERSION, 'amb'),
                 ('> python %s · SDL %s' % (sys.version.split()[0], sdl.version()), 'ambD'),
                 ('> map · %s coastline arcs ......... OK' % num(len(self.map_hi.arcs) + len(self.map_lo.arcs)), 'ambD'),
                 ('> airports · %d loaded .............. OK' % len(AIRPORTS), 'ambD')]
        if f.ok:
            lines.append(('> feed %s ................... OK' % f.source, 'ambD'))
            lines.append(('> contacts > %s aircraft' % num(len(self.planes)), 'ambD'))
        elif f.status in ('NO NETWORK', 'ERROR'):
            lines.append(('> feed ......................... %s' % f.status, 'red'))
            lines.append(('  check WiFi; the globe works without data', 'ambD'))
        else:
            lines.append(('> feed · connecting%s' % ('.' * (self.frame // 10 % 4)), 'ambD'))
        lines.append(('', 'ambD'))
        lines.append(('PRESS START', 'amb'))
        n = min(len(lines), int(self.boot_t / 0.25) + 1)
        for i in range(n):
            t, c = lines[i]
            col = COL[c]
            if i == len(lines) - 1 and self.frame % 40 >= 28:
                col = COL['ambD']
            self.text(t, 40, 92 + i * 26, 'M', 16, col)
        if self.boot_t > 6 and (f.ok or f.status in ('NO NETWORK', 'ERROR')):
            self.mode = 'run'

    def draw_card(self):
        """Full-screen card for the locked aircraft: big callsign, route and live data."""
        g = self.g
        p = self.sel
        now = time.time()
        g.clear(COL['bg'])
        col = self.color(p)
        y0 = HDR
        kind = {'mil': 'MILITARY', 'priv': 'PRIVATE'}.get(p.kind, 'COMMERCIAL')
        if p.flags & 4:
            kind += ' · PIA'
        if p.flags & 8:
            kind += ' · LADD'
        kcol = COL['cyan'] if p.kind == 'mil' else COL['mag'] if p.kind == 'priv' else COL['ambD']
        self.text(p.label, 16, y0 + 62, 'V', 64, col if p.alert else COL['white'])
        self.text(kind, W - 16, y0 + 24, 'M', 16, kcol, 'right')
        self.text(p.type or '----', W - 16, y0 + 56, 'V', 38, COL['amb'], 'right')
        self.text(p.reg or '', W - 16, y0 + 76, 'M', 15, COL['ambD'], 'right')
        if p.alert:
            self.text('SQUAWK %s · %s' % (p.sq, SQK_TXT.get(p.sq, p.emerg.upper())), 16, y0 + 88, 'M', 16, col)
        g.fill(COL['ambDD'], (16, y0 + 98, W - 32, 1))

        # route
        rt = self.feed.routes.get(p.cs)
        aps = (rt or {}).get('airports') or []
        ry = y0 + 166
        ps = p.pos(now)
        if len(aps) >= 2 and ps:
            a, b = aps[0], aps[-1]
            self.text(a['code'] or '???', 16, ry, 'V', 64, COL['amb'])
            self.text(b['code'] or '???', W - 16, ry, 'V', 64, COL['amb'], 'right')
            self.text((a['city'] or '')[:20], 16, ry + 22, 'M', 16, COL['amb'])
            self.text((b['city'] or '')[:20], W - 16, ry + 22, 'M', 16, COL['amb'], 'right')
            self.text(clip(a['name'], 30), 16, ry + 40, 'M', 12, COL['dim'])
            self.text(clip(b['name'], 30), W - 16, ry + 40, 'M', 12, COL['dim'], 'right')
            # progress along the route
            done = left = None
            if a.get('lat') is not None and b.get('lat') is not None:
                done = haversine(a['lat'], a['lon'], ps[0], ps[1])
                left = haversine(ps[0], ps[1], b['lat'], b['lon'])
            x0, x1, ly = 150, W - 150, ry - 22
            frac = done / (done + left) if done is not None and done + left > 0 else 0.5
            xp = x0 + (x1 - x0) * frac
            g.fill(COL['amb'], (x0, ly, int(xp - x0), 2))
            g.fill_rects(COL['ambDD'], [(int(x), ly, 4, 2) for x in range(int(xp) + 8, x1, 9)])
            g.fill_rects(COL['amb'], [(x0 - 3, ly - 3, 7, 7), (x1 - 3, ly - 3, 7, 7)])
            s = 7
            g.triangles(COL['white'], [(xp + s * 1.4, ly + 1), (xp - s, ly - s + 1), (xp - s * 0.45, ly + 1),
                                       (xp + s * 1.4, ly + 1), (xp - s * 0.45, ly + 1), (xp - s, ly + s + 1)])
            if len(aps) > 2:
                self.text('via ' + ' · '.join(x['code'] for x in aps[1:-1]), W // 2, ly - 12, 'M', 12, COL['dim'], 'center')
            if done is not None and rt.get('plausible', True):
                info = '%s km flown  ·  %s km to go' % (num(done), num(left))
                if p.gs and p.gs > 60 and p.alt != 'ground':
                    hrs = left / (p.gs * 1.852)
                    eta = time.strftime('%H:%MZ', time.gmtime(now + hrs * 3600))
                    info += '  ·  ETA %s (%dh %02dm)' % (eta, int(hrs), int(hrs * 60) % 60)
                self.text(info, W // 2, ry + 66, 'M', 15, COL['amb'], 'center')
            note = 'route: %s' % ('VRS standing data (offline)' if rt.get('source') == 'offline' else rt.get('source', 'adsb.lol'))
            if not rt.get('plausible', True):
                note = "route on file doesn't match the aircraft's position · may be outdated"
            self.text(note, W // 2, ry + 84, 'M', 12, COL['dim'], 'center')
        elif rt is None and p.cs:
            self.text('LOOKING UP ROUTE' + '.' * (self.frame // 10 % 4), W // 2, ry - 10, 'V', 38, COL['ambD'], 'center')
        else:
            self.text('ROUTE UNKNOWN', W // 2, ry - 10, 'V', 38, COL['ambD'], 'center')
            why = 'no route on file for this callsign' if p.cs else 'no callsign broadcast'
            if rt and rt.get('error'):
                why = 'not in offline data · online lookup failed'
            self.text(why, W // 2, ry + 18, 'M', 15, COL['dim'], 'center')
        gy = y0 + 270
        g.fill(COL['ambDD'], (16, gy - 16, W - 32, 1))

        # live data grid
        vr = p.vr or 0
        cells = [('ALTITUDE', fl(p.alt), None),
                 ('GROUND SPEED', ('%d kt' % p.gs) if p.gs is not None else '—', None),
                 ('VERT. SPEED', ('+' if vr > 0 else '') + num(vr) + ' fpm', None),
                 ('TRACK', ('%03d°' % round(p.trk)) if p.trk is not None else '—', None),
                 ('SQUAWK', p.sq or '—', col if p.alert else None),
                 ('HEX', p.hex.upper(), None)]
        cw = (W - 32) // 3
        for i, (lab, val, c) in enumerate(cells):
            x = 16 + (i % 3) * cw
            y = gy + (i // 3) * 64
            self.text(lab, x, y + 6, 'M', 13, COL['dim'])
            self.text(val, x, y + 44, 'V', 48, c or COL['amb'])
        by = gy + 150
        if ps:
            self.text('%.4f%s  %.4f%s' % (abs(ps[0]), 'N' if ps[0] >= 0 else 'S', abs(ps[1]), 'E' if ps[1] >= 0 else 'W'), 16, by, 'M', 16, COL['amb'])
        self.text('seen %ds ago' % int(now - p.last_seen), W - 16, by, 'M', 16, COL['ambD'], 'right')
        hint = 'B BACK TO GLOBE  ·  START ' + ('UNFOLLOW' if self.follow else 'FOLLOW')
        self.text(hint, 16, H - 10, 'M', 13, COL['dim'])
        if self.follow:
            self.text('[ FOLLOWING ]', W - 16, H - 10, 'M', 13, COL['white'] if self.frame % 40 < 28 else COL['ambD'], 'right')
        if time.time() - self.toast_t < 1.8:
            self.text(self.toast_txt, W // 2, H - 30, 'M', 15, COL['amb'], 'center')

    def render(self):
        if self.mode == 'boot':
            self.draw_boot()
        elif self.card and self.sel:
            self.draw_card()
            self.draw_header()
            if self.help:
                self.draw_help()
        else:
            self.card = False
            self.g.clear(COL['bg'])
            self.draw_globe()
            self.draw_panel()
            self.draw_header()
            self.draw_footer()
            if self.help:
                self.draw_help()
        if self.scan_rects:
            self.g.fill_rects((0, 0, 0, 56), self.scan_rects)

    def save_state(self):
        save_json(STATE, {'view': {'lat': round(self.v.lat, 4), 'lon': round(self.v.lon, 4), 'zoom': round(self.v.zt, 3)},
                          'filter': self.filter, 'labels': self.labels})


# ---------------------------------------------------------------- physical input
KEYS = {sdl.K_UP: 'up', sdl.K_DOWN: 'down', sdl.K_LEFT: 'left', sdl.K_RIGHT: 'right',
        ord('x'): 'A', sdl.K_SPACE: 'A', sdl.K_RETURN: 'START', ord('z'): 'B',
        ord('s'): 'X', ord('a'): 'Y', ord('q'): 'L', ord('w'): 'R',
        sdl.K_RSHIFT: 'SELECT', sdl.K_LSHIFT: 'SELECT', sdl.K_BACKSPACE: 'SELECT',
        sdl.K_ESCAPE: 'MENU'}
DIRS = ('up', 'down', 'left', 'right')


class Pad:
    """Turns keyboard and gamepad events into logical buttons and the held d-pad."""

    def __init__(self, buttons):
        self.by_index = {int(v): k for k, v in buttons.items()}
        self.held_btn = set()
        self.dirs = set()
        self.hat = set()
        self.axis = {}
        self.keys = set()

    def feed(self, ev):
        """Returns the pressed button (or None) and updates self.dirs."""
        t = ev[0]
        if t == 'key':
            _, down, sym, rep = ev
            k = KEYS.get(sym)
            if k in DIRS:
                (self.keys.add if down else self.keys.discard)(k)
                self._sync()
                return None
            return k if (down and not rep) else None
        if t == 'jbtn':
            _, down, b = ev
            k = self.by_index.get(b)
            if not k:
                return None
            if k in DIRS:  # d-pads that report as buttons
                (self.keys.add if down else self.keys.discard)(k)
                self._sync()
                return None
            if down:
                self.held_btn.add(k)
                return k
            self.held_btn.discard(k)
            return None
        if t == 'hat':
            v = ev[1]
            self.hat = {d for bit, d in ((1, 'up'), (2, 'right'), (4, 'down'), (8, 'left')) if v & bit}
            self._sync()
            return None
        if t == 'axis':
            _, ax, val = ev
            if ax in (0, 1):
                self.axis[ax] = -1 if val < -20000 else 1 if val > 20000 else 0
                self._sync()
        return None

    def _sync(self):
        d = set(self.keys) | self.hat
        a0, a1 = self.axis.get(0, 0), self.axis.get(1, 0)
        if a0 < 0:
            d.add('left')
        if a0 > 0:
            d.add('right')
        if a1 < 0:
            d.add('up')
        if a1 > 0:
            d.add('down')
        self.dirs = d

    def quit_combo(self):
        return 'SELECT' in self.held_btn and 'START' in self.held_btn


def calibrate(g):
    fonts = {k: sdl.Font(g, os.path.join(BASE, 'fonts', k)) for k in ('M18', 'V26', 'M32')}
    got = {}
    idx = 0
    done_at = None
    order = CALIB_ORDER + ['up', 'down', 'left', 'right']
    last_ev = 'gamepads: %s' % (g.joystick_info() or 'none')
    while True:
        for ev in g.events():
            if ev[0] in ('key', 'jbtn', 'hat', 'axis'):
                last_ev = 'last event: %s' % (ev,)
            if ev[0] == 'quit' or (ev[0] == 'key' and ev[1] and ev[2] == sdl.K_ESCAPE):
                return
            if ev[0] == 'hat' and idx >= len(CALIB_ORDER) and ev[1]:
                idx = len(order)  # the d-pad is a hat: no need to map it
            if ev[0] == 'jbtn' and ev[1] and idx < len(order) and ev[2] not in got.values():
                got[order[idx]] = ev[2]
                idx += 1
        if idx >= len(order) and done_at is None:
            cur = {}
            try:
                with open(CONFIG) as fh:
                    cur = json.load(fh)
            except Exception:
                pass
            cur['buttons'] = got
            save_json(CONFIG, cur)
            done_at = time.time()
        g.clear(COL['bg'])
        fonts['M18'].draw('BIRDWATCHER · BUTTON SETUP', 24, 40, COL['amb'])
        if idx < len(order):
            name = order[idx]
            nice = {'up': 'D-PAD UP', 'down': 'D-PAD DOWN', 'left': 'D-PAD LEFT', 'right': 'D-PAD RIGHT'}.get(name, name)
            fonts['M32'].draw('PRESS  ' + nice, 24, 110, COL['white'])
            fonts['V26'].draw('If the d-pad does nothing here, it already works on its own.' if idx >= len(CALIB_ORDER) else 'Escape or close to quit without saving.', 24, 150, COL['ambD'])
        else:
            fonts['M32'].draw('SAVED', 24, 110, COL['amb'])
        for i, k in enumerate(order):
            v = got.get(k)
            fonts['V26'].draw('%-7s %s' % (k, '' if v is None else 'button %d' % v), 24 if i < 9 else 330, 200 + (i % 9) * 26, COL['amb'] if v is not None else COL['dim'])
        fonts['M18'].draw(last_ev[:58], 24, 462, COL['dim'])
        g.present()
        if done_at and time.time() - done_at > 1.5:
            return
        time.sleep(1 / 30.0)


def main():
    windowed = '--windowed' in sys.argv
    demo = '--demo' in sys.argv
    cfg = load_config()
    g = sdl.Gfx(W, H, 'Birdwatcher', windowed)
    try:
        if '--calibrate' in sys.argv:
            calibrate(g)
            return
        print('SDL %s (%s) · render targets: %s · float lines: %s · geometry: %s · gamepads: %s' % (
            sdl.version(), sdl.LIB_PATH, g.can_target, sdl.HAS_LINESF, sdl.HAS_GEOMETRY, g.joystick_info()), flush=True)
        pad = Pad(cfg['buttons'])
        app = App(g, cfg, demo)
        g.clear(COL['bg'])
        app.text('BIRDWATCHER · loading maps…', 40, 92, 'M', 16, COL['amb'])
        g.present()
        app.map_lo = CoastMap(os.path.join(BASE, 'data', 'coast110.json'), 10)
        app.map_hi = CoastMap(os.path.join(BASE, 'data', 'coast50.json'), 20)
        app.feed.start()
        frame_t = 1.0 / cfg.get('fps', 30)
        running = True
        last = time.time()
        while running:
            t0 = time.time()
            dt = min(0.1, t0 - last)
            last = t0
            for ev in g.events():
                if ev[0] == 'quit':
                    running = False
                    break
                if ev[0] == 'reset':
                    app.reset_textures()
                    continue
                k = pad.feed(ev)
                if k == 'MENU' or pad.quit_combo():
                    running = False
                    break
                if k:
                    app.press(k)
            app.held = pad.dirs
            app.frame += 1
            app.ingest()
            if app.mode == 'boot':
                app.boot_t += dt
            else:
                app.update(dt)
            app.render()
            g.present()
            spare = frame_t - (time.time() - t0)
            if spare > 0:
                time.sleep(spare)
        app.feed.stop = True
        app.save_state()
    finally:
        g.quit()


if __name__ == '__main__':
    main()
