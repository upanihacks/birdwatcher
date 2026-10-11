#!/usr/bin/env python3
"""Rebuild the offline route database in data/routes from the Virtual Radar Server standing data (CC0).

  git clone --depth 1 https://github.com/vradarserver/standing-data
  python3 tools/build_routes.py standing-data

Output: one gzip file per callsign first character with "CALLSIGN,ICAO-ICAO[-ICAO…]" lines,
and airports.json.gz mapping ICAO -> [IATA, name, city, country, lat, lon] for the airports used.
"""
import collections
import csv
import glob
import gzip
import json
import os
import sys

OUT = os.path.join(os.path.dirname(__file__), '..', 'APPS', 'Birdwatcher', 'data', 'routes')
sd = sys.argv[1] if len(sys.argv) > 1 else 'standing-data'

airports = {}
for f in glob.glob(os.path.join(sd, 'airports', 'schema-01', '*', '*.csv')):
    with open(f, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            try:
                airports[r['ICAO'] or r['Code']] = [r['IATA'], r['Name'], r['Location'], r['CountryISO2'],
                                                    round(float(r['Latitude']), 4), round(float(r['Longitude']), 4)]
            except (ValueError, KeyError):
                pass

shards = collections.defaultdict(list)
used = set()
for f in glob.glob(os.path.join(sd, 'routes', 'schema-01', '*', '*.csv')):
    with open(f, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            cs = (r['Callsign'] or '').strip().upper()
            codes = (r['AirportCodes'] or '').strip()
            if not cs or not codes or codes == 'unknown':
                continue
            parts = codes.split('-')
            if not all(p in airports for p in parts):
                continue
            used.update(parts)
            shards[cs[0] if cs[0].isalnum() else '_'].append(cs + ',' + codes)

os.makedirs(OUT, exist_ok=True)
for old in glob.glob(os.path.join(OUT, '*.gz')):
    os.remove(old)
total = 0
for k, lines in shards.items():
    lines.sort()
    with gzip.open(os.path.join(OUT, k + '.gz'), 'wt', compresslevel=9) as g:
        g.write('\n'.join(lines))
    total += len(lines)
with gzip.open(os.path.join(OUT, 'airports.json.gz'), 'wt', compresslevel=9) as g:
    json.dump({k: airports[k] for k in used}, g, ensure_ascii=False, separators=(',', ':'))
print(total, 'routes,', len(used), 'airports')
