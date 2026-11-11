"""Step 4a: places the measured traffic counts on the SUMO network.

    .venv/bin/python scripts/make_counts.py

Inputs
  data/raw/traffic/doh-aadt-2562.csv   กรมทางหลวง AADT ปี 2562 รายจุดสำรวจ (ทางหลวงแผ่นดิน, กม. ของจุด)
  data/raw/traffic/drr-aadt-2569.csv   กรมทางหลวงชนบท AADT ปี 2569 รายสายทาง (ภก.xxxx)
  data/processed/phuket-roads.osm       ref ของถนนแต่ละเส้น
  network/phuket.net.xml
Outputs
  data/processed/count_stations.csv     จุดนับ: ตำแหน่ง edges สองทิศ และ AADT แยกประเภทรถ
  docs/img/step4-count-stations.png
"""
import csv
import heapq
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sumolib
from matplotlib.collections import LineCollection

ROOT = Path(__file__).resolve().parent.parent
TRAFFIC = ROOT / 'data' / 'raw' / 'traffic'

# Vehicle groups used in the simulation, from the DOH / DRR count classes.
DOH_CLASSES = {
    'car': ['รถยนต์นั่ง (ไม่เกิน 7 คน)', 'รถยนต์นั่ง (เกิน 7 คน)', '   รถบรรทุกขนาดเล็ก    ( 4 ล้อ)'],
    'bus': ['รถโดยสารขนาดเล็ก', 'รถโดยสารขนาดกลาง', 'รถโดยสารขนาดใหญ่'],
    'truck': ['รถบรรทุกขนาด 2 เพลา  (6 ล้อ)', '     รถบรรทุกขนาด 3 เพลา (10 ล้อ)',
              '   รถบรรทุกพ่วง  (มากกว่า 3 เพลา)', '   รถบรรทุกกึ่งพ่วง (มากกว่า 3 เพลา)'],
    'motorcycle': ['สามล้อเครื่องและจักรยานยนต์'],
}
# DRR columns (กรมทางหลวงชนบท): MC motorcycle, SV car, SVT pickup, TB2/TB3 bus, the rest trucks.
DRR_CLASSES = {
    'car': ['SV', 'SVT'],
    'bus': ['TB2', 'TB3'],
    'truck': ['T4', 'ART3', 'ART4', 'ART5', 'ART6', 'BD', 'DRT'],
    'motorcycle': ['MC'],
}

# Where kilometre 0 of each DOH highway lies, used to place a survey point "km X" along the road.
# 'north' / 'east' = the northernmost / easternmost end of the road inside Phuket, from the section names.
# ทล.402 starts at โคกกลอย in Phang Nga, so it is anchored at its junctions with DRR roads whose names
# give the ทล.402 kilometre (e.g. ภก.3001 "แยกทางหลวงหมายเลข 402 (กม.ที่ 43+500)"); km increase southwards.
KM_ORIGIN = {
    '402': ('junction', {'ภก.3033': 14.0, 'ภก.3034': 15.6, 'ภก.3029': 28.2, 'ภก.3015': 35.2,
                         'ภก.3032': 36.7, 'ภก.3030': 40.0, 'ภก.3001': 43.5}, None),
    '4021': ('town', None, 0.0),   # เมืองภูเก็ต - ห้าแยกฉลอง
    '4023': ('town', None, 0.0),   # เมืองภูเก็ต - แหลมพันวา
    '4024': ('north', None, 0.0),  # บางคู - ตีนเขา - หาดราไวย์
    '4025': ('east', None, 0.0),   # ท่าเรือ - เชิงทะเล
    '4026': ('east', None, 0.0),   # ทางเข้าสนามบิน (from ทล.402)
    '4027': ('north', None, 0.0),  # ท่าเรือ - เมืองใหม่
    '4028': ('east', None, 0.0),   # ห้าแยกฉลอง - กะรน
    '4029': ('east', None, 0.0),   # กะทู้ - ป่าตอง
    '4030': ('north', None, 0.0),  # ถลาง - หาดราไวย์
    '4031': ('north', None, 0.0),  # มุดดอกขาว - สนามบิน
}
TOWN = (98.3923, 7.8847)  # ศาลากลางจังหวัดภูเก็ต (approx.)


def osm_refs():
    """OSM way id -> list of refs, and ref -> list of way geometries (lon/lat)."""
    root = ET.parse(ROOT / 'data' / 'processed' / 'phuket-roads.osm').getroot()
    nodes = {n.get('id'): (float(n.get('lon')), float(n.get('lat'))) for n in root.iter('node')}
    way_refs, geoms = {}, defaultdict(list)
    for way in root.iter('way'):
        tags = {t.get('k'): t.get('v') for t in way.iter('tag')}
        if 'ref' not in tags:
            continue
        refs = [r.strip() for r in tags['ref'].split(';')]
        way_refs[way.get('id')] = refs
        coords = [nodes[nd.get('ref')] for nd in way.iter('nd') if nd.get('ref') in nodes]
        for r in refs:
            geoms[r].append(coords)
    return way_refs, geoms


def dist_m(a, b):
    return math.hypot((a[0] - b[0]) * 111320 * math.cos(math.radians(7.9)), (a[1] - b[1]) * 110574)


def distances_from(geoms, start, gap=60):
    """Shortest distance along the road (both carriageways, undirected) from `start` to every vertex.
    Pieces of the road closer than `gap` metres are linked, because junctions and roundabouts in OSM
    often do not carry the road's ref and would otherwise split it."""
    graph = defaultdict(list)
    for coords in geoms:
        for a, b in zip(coords, coords[1:]):
            d = dist_m(a, b)
            graph[a].append((b, d))
            graph[b].append((a, d))
    ends = [c for coords in geoms for c in (coords[0], coords[-1])]
    cell = defaultdict(list)
    for v in graph:
        cell[(round(v[0] / 0.0005), round(v[1] / 0.0005))].append(v)
    for a in ends:
        cx, cy = round(a[0] / 0.0005), round(a[1] / 0.0005)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for b in cell[(cx + dx, cy + dy)]:
                    d = dist_m(a, b)
                    if 0 < d < gap:
                        graph[a].append((b, d))
                        graph[b].append((a, d))
    best, queue = {start: 0.0}, [(0.0, start)]
    while queue:
        d, v = heapq.heappop(queue)
        if d > best[v]:
            continue
        for w, step in graph[v]:
            if d + step < best.get(w, math.inf):
                best[w] = d + step
                heapq.heappush(queue, (d + step, w))
    return best


def locate_km(ref, km, geoms):
    """Lon/lat of kilometre `km` on DOH highway `ref`, or None if it falls outside Phuket."""
    kind, anchors, _ = KM_ORIGIN[ref]
    vertices = {v for coords in geoms[ref] for v in coords}
    if kind == 'junction':
        # Nearest anchor junction by km, then walk |km - anchor km| along the road, south if km is larger.
        other, anchor_km = min(anchors.items(), key=lambda kv: abs(kv[1] - km))
        if other not in geoms:
            return None
        other_vertices = [v for coords in geoms[other] for v in coords]
        anchor = min(vertices, key=lambda v: min(dist_m(v, o) for o in other_vertices))
        dist = distances_from(geoms[ref], anchor)
        target = abs(km - anchor_km) * 1000
        side = [v for v in dist if (v[1] < anchor[1]) == (km > anchor_km)] or list(dist)
        best = min(side, key=lambda v: abs(dist[v] - target))
        return best if abs(dist[best] - target) < 500 else None
    if kind == 'north':
        start = max(vertices, key=lambda v: v[1])
    elif kind == 'east':
        start = max(vertices, key=lambda v: v[0])
    else:
        start = min(vertices, key=lambda v: dist_m(v, TOWN))
    dist = distances_from(geoms[ref], start)
    target = km * 1000
    best = min(dist, key=lambda v: abs(dist[v] - target))
    return best if abs(dist[best] - target) < 500 else None


def midpoint(ref, geoms):
    """Point halfway along a road, for DRR roads that have one AADT for the whole road."""
    vertices = {v for coords in geoms[ref] for v in coords}
    start = max(vertices, key=lambda v: v[1])
    dist = distances_from(geoms[ref], start)
    half = max(dist.values()) / 2
    return min(dist, key=lambda v: abs(dist[v] - half))


def way_id(edge_id):
    return re.sub(r'^-', '', edge_id).split('#')[0].split('-Added')[0]


def edges_at(net, lonlat, ref, way_refs):
    """The nearest edge of `ref` in each travel direction at a point (one for a one-way road)."""
    x, y = net.convertLonLat2XY(*lonlat)
    near = [(e, d) for e, d in net.getNeighboringEdges(x, y, r=200)
            if ref in way_refs.get(way_id(e.getID()), []) and e.allows('passenger')]
    near.sort(key=lambda t: t[1])
    chosen = []
    for e, _ in near:
        (x1, y1), (x2, y2) = e.getShape()[0], e.getShape()[-1]
        heading = (x2 - x1, y2 - y1)
        if all(heading[0] * h[0] + heading[1] * h[1] > 0 for _, h in chosen) and chosen:
            continue  # same direction as an edge already chosen
        chosen.append((e, heading))
        if len(chosen) == 2:
            break
    return [e.getID() for e, _ in chosen]


def main():
    net = sumolib.net.readNet(str(ROOT / 'network' / 'phuket.net.xml'))
    way_refs, geoms = osm_refs()
    stations = []

    for r in csv.DictReader(open(TRAFFIC / 'doh-aadt-2562.csv', encoding='utf-8-sig')):
        if r['จังหวัด'].strip() != 'ภูเก็ต':
            continue
        ref = r['ทางหลวงสาย'].strip()
        km = float(r['จุดสำรวจ'].replace('+', '.'))  # "11+206" -> 11.206 km
        if ref not in KM_ORIGIN or ref not in geoms:
            print(f'skip DOH {ref} km {km}: road not in OSM / no km origin')
            continue
        point = locate_km(ref, km, geoms)
        if point is None:
            print(f'skip DOH {ref} km {km}: outside Phuket')
            continue
        aadt = {g: sum(int(float(r[c] or 0)) for c in cols) for g, cols in DOH_CLASSES.items()}
        stations.append({'id': f'DOH-{ref}-{r["จุดสำรวจ"]}', 'source': 'กรมทางหลวง 2562', 'ref': ref,
                         'name': r['ชื่อสายทาง'].strip(), 'lon': point[0], 'lat': point[1], **aadt})

    for r in csv.DictReader(open(TRAFFIC / 'drr-aadt-2569.csv', encoding='utf-8-sig')):
        ref = r['road_code'].strip()
        if not ref.startswith('ภก.'):
            continue
        if ref not in geoms:
            print(f'skip DRR {ref}: not tagged in OSM')
            continue
        point = midpoint(ref, geoms)
        aadt = {g: sum(int(float(r[c] or 0)) for c in cols) for g, cols in DRR_CLASSES.items()}
        stations.append({'id': f'DRR-{ref}', 'source': 'กรมทางหลวงชนบท 2569', 'ref': ref,
                         'name': r['road_name'].strip(), 'lon': point[0], 'lat': point[1], **aadt})

    rows = []
    for s in stations:
        edges = edges_at(net, (s['lon'], s['lat']), s['ref'], way_refs)
        if not edges:
            print(f'skip {s["id"]}: no network edge with this ref near the point')
            continue
        rows.append({**s, 'edges': ' '.join(edges), 'directions': len(edges)})

    out = ROOT / 'data' / 'processed' / 'count_stations.csv'
    fields = ['id', 'source', 'ref', 'name', 'lon', 'lat', 'edges', 'directions', 'car', 'bus', 'truck', 'motorcycle']
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} count stations -> {out.relative_to(ROOT)}')

    fig, ax = plt.subplots(figsize=(7, 13))
    shapes = [e.getShape() for e in net.getEdges() if e.getPriority() >= 7 or e.getType().endswith(('primary', 'secondary'))]
    ax.add_collection(LineCollection(shapes, colors='#bbbbbb', linewidths=0.5))
    for s in rows:
        x, y = net.convertLonLat2XY(s['lon'], s['lat'])
        total = s['car'] + s['bus'] + s['truck'] + s['motorcycle']
        ax.scatter(x, y, s=12 + total / 800, c='#c0392b' if s['source'].startswith('กรมทางหลวง 2') else '#2980b9',
                   alpha=0.75, edgecolor='white', zorder=5)
        ax.annotate(s['ref'].replace('ภก.', 'PK'), (x, y), fontsize=6, xytext=(4, 2), textcoords='offset points')
    ax.scatter([], [], c='#c0392b', label='DOH survey point (AADT 2019)')
    ax.scatter([], [], c='#2980b9', label='DRR road (AADT 2026)')
    ax.autoscale(); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc='lower left'); ax.set_title('Traffic count stations (size = AADT incl. motorcycles)')
    fig.tight_layout(); fig.savefig(ROOT / 'docs' / 'img' / 'step4-count-stations.png', dpi=110)


if __name__ == '__main__':
    main()
