#!/usr/bin/env python3
"""Rebuild data/coast110.json and data/coast50.json from the world-atlas TopoJSON files.

  npm pack world-atlas@2.0.2 && tar xzf world-atlas-2.0.2.tgz
  python3 tools/build_coastlines.py package/
"""
import json
import os
import sys

OUT = os.path.join(os.path.dirname(__file__), '..', 'APPS', 'Birdwatcher', 'data')


def arcs(path, q):
    tj = json.load(open(path))
    sx, sy = tj['transform']['scale']
    tx, ty = tj['transform']['translate']
    out = []
    for arc in tj['arcs']:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            p = (round((x * sx + tx) * q), round((y * sy + ty) * q))
            if not pts or pts[-1] != p:
                pts.append(p)
        if len(pts) > 1:
            out.append([v for p in pts for v in p])
    return out


src = sys.argv[1] if len(sys.argv) > 1 else 'package'
for name, q, dst in (('countries-110m.json', 10, 'coast110.json'), ('countries-50m.json', 20, 'coast50.json')):
    data = arcs(os.path.join(src, name), q)
    with open(os.path.join(OUT, dst), 'w') as fh:
        json.dump(data, fh, separators=(',', ':'))
    print(dst, len(data), 'arcs')
