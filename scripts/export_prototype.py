"""Step 9 preview: exports the flood run and road status for the prototype web page (web/prototype).

    .venv/bin/python scripts/export_prototype.py
    cd web/prototype && ../../.venv/bin/python -m http.server 8000      # then open http://localhost:8000

Exports (web/prototype/data/):
  flood/<i>.png   flood depth of hour i as a transparent image (>= 5 cm shown), corners in meta.json
  roads.geojson   main roads plus every road that ever has >= 0.1 m of water; per-hour depth class string
                  (0 dry, 1 slower 0.1-0.3 m, 2 avoid >= 0.3 m) and the dry morning-peak speed
  news.geojson    flood spots reported in the news on 29 Oct 2569
  meta.json       hourly times, rain (ERA5), image corners, run name
Road depth classes follow road_flood_depth.py (Pregnolato et al. 2017; roads are never closed).
"""
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import sumolib
from PIL import Image
from pyproj import Transformer

import road_flood_depth as rfd

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web' / 'prototype' / 'data'
MAIN_ROADS = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'primary_link', 'secondary_link',
              'tertiary_link', 'trunk_link'}
TO_LL = Transformer.from_crs('EPSG:32647', 'EPSG:4326', always_xy=True)
# depth (m) -> RGBA, light to dark blue
DEPTH_COLOURS = [(0.05, (198, 219, 239, 150)), (0.1, (158, 202, 225, 170)), (0.3, (66, 146, 198, 190)),
                 (0.6, (33, 113, 181, 210)), (1.0, (8, 69, 148, 225))]


def flood_images(run):
    d = np.load(run / 'depth_hourly.npz')
    depth, times = d['depth'].astype('float32'), [str(t) for t in d['times']]
    a, b, c, dd, e, f = d['transform']
    rows, cols = depth.shape[1:]
    corners = [TO_LL.transform(c + a * x, f + e * y) for x, y in [(0, 0), (cols, 0), (cols, rows), (0, rows)]]
    out = WEB / 'flood'
    out.mkdir(parents=True, exist_ok=True)
    for i, h in enumerate(depth):
        rgba = np.zeros((rows, cols, 4), 'uint8')
        for threshold, colour in DEPTH_COLOURS:
            rgba[h >= threshold] = colour
        Image.fromarray(rgba, 'RGBA').save(out / f'{i}.png', optimize=True)
    return times, [list(map(float, p)) for p in corners]


def dry_speeds():
    """Mean speed (km/h) per edge in the dry morning-peak baseline run (step 4)."""
    edges = ET.parse(ROOT / 'output' / 'baseline' / 'morning_peak' / 'edgedata.xml').getroot().iter('edge')
    return {e.get('id'): round(float(e.get('speed')) * 3.6) for e in edges if e.get('speed')}


def roads(run):
    d = np.load(rfd.OUT / f'edge_depth_{run.name}.npz')
    depth, ids = d['depth_m'], list(d['edges'])
    classes = np.where(depth >= rfd.AVOID_MM / 1000, 2, np.where(depth >= 0.1, 1, 0))
    flooded = classes.max(axis=0) > 0
    net = sumolib.net.readNet(str(ROOT / 'network' / 'phuket.net.xml'))
    ox, oy = net.getLocationOffset()
    speeds = dry_speeds()
    features = []
    for k, eid in enumerate(ids):
        edge = net.getEdge(eid)
        kind = edge.getType().replace('highway.', '')
        if not (flooded[k] or kind in MAIN_ROADS):
            continue
        xy = np.array(edge.getShape()) - (ox, oy)
        lon, lat = TO_LL.transform(xy[:, 0], xy[:, 1])
        features.append({'type': 'Feature',
                         'geometry': {'type': 'LineString',
                                      'coordinates': [[round(x, 6), round(y, 6)] for x, y in zip(lon, lat)]},
                         'properties': {'id': eid, 'name': edge.getName() or '', 'kind': kind,
                                        'main': kind in MAIN_ROADS, 'limit': round(edge.getSpeed() * 3.6),
                                        'dry_speed': speeds.get(eid),
                                        'cls': ''.join(map(str, classes[:, k])),
                                        'depth_cm': [int(round(w * 100)) for w in depth[:, k]]}})
    (WEB / 'roads.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features},
                                                  ensure_ascii=False, separators=(',', ':')))
    return len(features)


def news():
    rows = [r for r in csv.DictReader(open(ROOT / 'data' / 'validation' / 'flood-reports-2569-10-29.csv',
                                           encoding='utf-8')) if r['lat']]
    features = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [float(r['lon']), float(r['lat'])]},
                 'properties': {'id': r['id'], 'location': r['location'], 'severity': r['severity'],
                                'source': r['source'], 'date': r['date']}} for r in rows]
    (WEB / 'news.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features},
                                                 ensure_ascii=False))
    return len(features)


def main():
    run = rfd.RUN
    WEB.mkdir(parents=True, exist_ok=True)
    times, corners = flood_images(run)
    rain_data = json.loads((ROOT / 'data' / 'raw' / 'rain' / 'era5_phuket_town_2000_2026.json').read_text())['hourly']
    rain = [rain_data['precipitation'][rain_data['time'].index(t)] or 0.0 for t in times]
    n_roads, n_news = roads(run), news()
    (WEB / 'meta.json').write_text(json.dumps({'run': run.name, 'times': times, 'rain_mm': rain,
                                               'corners': corners}, ensure_ascii=False))
    print(f'{len(times)} flood frames, {n_roads:,} roads, {n_news} news spots -> {WEB}')


if __name__ == '__main__':
    main()
