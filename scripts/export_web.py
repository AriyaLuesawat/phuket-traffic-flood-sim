"""Step 9b: exports the step 8 scenarios and the city model for the playback web page (web/app).

    .venv/bin/python scripts/export_web.py              # everything; runs not finished yet are skipped
    .venv/bin/python scripts/export_web.py runs         # only the scenario runs (after more playback runs finish)
    .venv/bin/python scripts/export_web.py basemap      # only basemap.json
    .venv/bin/python scripts/export_web.py roads        # only roads.bin / roads.json
    cd web/app && ../../.venv/bin/python -m http.server 8000      # then open http://localhost:8000

Exports (web/app/data/, generated, not committed):
  roads.bin / roads.json   every road edge open to cars or motorcycles: vertices (lon, lat, ground m) as
                           float32, vertex offsets, length, road kind, name (main roads)
  runs/<period>_<scenario>.bin   per 5-minute frame and edge, from output/playback (run_playback.py):
                           mean speed km/h (uint8, 0 = no vehicle), mean vehicles on the edge (uint8, capped
                           at 255) and, for the flood scenarios, water depth on the road in cm (uint8, capped)
  water.bin / water.json   30 m cells of the step 6 flood run with >= WATER_MIN_M of water at 07:00, 08:00 or
                           09:00 on 29 Oct 2569 (the hours the flood scenario uses): lon, lat, ground, depth
  terrain.json             ground lines every TERRAIN_STEP cells (FABDEM, land cells only)
  buildings.json           OSM building footprints with height: the height tag, else building:levels x
                           LEVEL_M, else one level (ASSUMPTION for display only: 95% of OSM buildings in Phuket
                           carry no height)
  basemap.json             coastline of Phuket island (edge of the land cells of the flood grid) and the
                           OSM place=city/town names, for the 2D map
  meta.json                periods, scenarios, frame times, network series per run, step 8 summary
                           (5 seeds) and the news flood spots
"""
import csv
import json
import statistics
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path

import numpy as np
import rasterio
import sumolib
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_demand import PERIODS, WARMUP  # noqa: E402
from road_flood_depth import RUN  # noqa: E402
from run_baseline import NET  # noqa: E402
from run_flood_traffic import Flood  # noqa: E402
from run_playback import OUT as PLAYBACK, PLAYBACK_S, done  # noqa: E402
from run_scenarios import FLOOD_AT, FLOODS, SCENARIOS  # noqa: E402

WEB = ROOT / 'web' / 'app' / 'data'
DEM = ROOT / 'data' / 'processed' / 'flood' / 'dem_fabdem.tif'
SEA = ROOT / 'data' / 'processed' / 'flood' / 'sea.tif'
OSM = ROOT / 'data' / 'raw' / 'osm' / 'thailand-latest.osm.pbf'
ISLAND = (98.25, 7.75, 98.48, 8.20)  # lon/lat box of Phuket island for the OSM building extract
TO_LL = Transformer.from_crs('EPSG:32647', 'EPSG:4326', always_xy=True)
TO_UTM = Transformer.from_crs('EPSG:4326', 'EPSG:32647', always_xy=True)
MAIN_ROADS = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']
WATER_MIN_M = 0.05
TERRAIN_STEP = 7  # 210 m
LEVEL_M = 3.0  # ASSUMPTION: storey height for display
LABELS = {'dry': 'ไม่มีฝน', 'light': 'ฝนเล็กน้อย', 'medium': 'ฝนปานกลาง', 'heavy': 'ฝนหนัก',
          'heavy_reports': 'ฝนหนัก + น้ำจุดข่าว', 'heavy_flood': 'ฝนหนัก + น้ำบนถนน (แบบจำลอง)'}


class Ground:
    def __init__(self):
        self.r = rasterio.open(DEM)
        self.z = self.r.read(1)

    def at_utm(self, x, y):
        rows, cols = rasterio.transform.rowcol(self.r.transform, x, y)
        rows = np.clip(rows, 0, self.z.shape[0] - 1)
        cols = np.clip(cols, 0, self.z.shape[1] - 1)
        z = self.z[rows, cols]
        return np.where(z == self.r.nodata, 0, np.maximum(z, 0))


def kind(edge):
    k = edge.getType().replace('highway.', '').replace('_link', '')
    return MAIN_ROADS.index(k) if k in MAIN_ROADS else len(MAIN_ROADS)


def roads(ground):
    net = sumolib.net.readNet(str(NET))
    ox, oy = net.getLocationOffset()
    edges = [e for e in net.getEdges() if e.getFunction() != 'internal'
             and (e.allows('passenger') or e.allows('motorcycle'))]
    coords, offsets, meta = [], [0], {'ids': [], 'length': [], 'kind': [], 'name': [], 'lanes': []}
    for e in edges:
        xy = np.array(e.getShape(True)) - (ox, oy)  # with the junction centres, so roads join on the map
        lon, lat = TO_LL.transform(xy[:, 0], xy[:, 1])
        z = ground.at_utm(xy[:, 0], xy[:, 1])
        coords.append(np.column_stack([lon, lat, z]))
        offsets.append(offsets[-1] + len(xy))
        meta['ids'].append(e.getID())
        meta['length'].append(round(e.getLength(), 1))
        meta['kind'].append(kind(e))
        meta['name'].append(e.getName() if kind(e) < len(MAIN_ROADS) else '')
        meta['lanes'].append(e.getLaneNumber())
    v = np.concatenate(coords).astype('float32')
    (WEB / 'roads.bin').write_bytes(np.array([len(edges), len(v)], 'uint32').tobytes()
                                    + np.array(offsets, 'uint32').tobytes() + v.tobytes())
    meta['kinds'] = MAIN_ROADS + ['other']
    (WEB / 'roads.json').write_text(json.dumps(meta, ensure_ascii=False, separators=(',', ':')))
    print(f'roads: {len(edges):,} edges, {len(v):,} vertices')
    return meta['ids']


def frame_starts(period):
    hour = PERIODS[period]
    begin = hour * 3600 - WARMUP
    return [begin + k * PLAYBACK_S for k in range((WARMUP + 3600) // PLAYBACK_S)]


def run(period, scenario, index):
    """Frames of one playback run; returns the network series (mean speed, vehicles, avoid km)."""
    out = PLAYBACK / period / scenario
    starts = frame_starts(period)
    n, f = len(index), len(starts)
    speed = np.zeros((f, n), 'uint8')
    veh = np.zeros((f, n), 'uint8')
    series = {'speed_kmh': [0.0] * f, 'vehicles': [0.0] * f, 'avoid_km': [0.0] * f}
    dist, secs = np.zeros(f), np.zeros(f)
    k = -1
    for _, el in ET.iterparse(out / 'edgedata_playback.xml', events=('start',)):
        if el.tag == 'interval':
            k = starts.index(int(float(el.get('begin'))))
        elif el.tag == 'edge':
            s = float(el.get('sampledSeconds', 0))
            secs[k] += s
            dist[k] += float(el.get('distance', 0))
            i = index.get(el.get('id'))
            if i is not None and s > 0:
                speed[k, i] = min(255, max(1, round(float(el.get('speed')) * 3.6)))
                veh[k, i] = min(255, round(s / PLAYBACK_S))
            el.clear()
    series['speed_kmh'] = [round(d / s * 3.6, 1) if s else 0 for d, s in zip(dist, secs)]
    series['vehicles'] = [round(s / PLAYBACK_S) for s in secs]
    parts = [speed.tobytes(), veh.tobytes()]
    if scenario in FLOODS:
        flood = Flood(FLOODS[scenario])
        keep = np.array([e in index for e in flood.edges])
        cols = np.array([index[e] for e in flood.edges if e in index])
        depth = np.zeros((f, n), 'uint8')
        hour = PERIODS[period]
        for k, t in enumerate(starts):  # as run_case: the study-hour start maps to FLOOD_AT
            d = flood.at(FLOOD_AT + timedelta(seconds=t - hour * 3600))
            depth[k, cols] = np.clip(np.round(d[keep] * 100), 0, 255)
            series['avoid_km'][k] = round(float(flood.length[d >= 0.3].sum()) / 1000, 1)
        parts.append(depth.tobytes())
    (WEB / 'runs' / f'{period}_{scenario}.bin').write_bytes(b''.join(parts))
    return series


def runs(ids):
    (WEB / 'runs').mkdir(parents=True, exist_ok=True)
    index = {e: i for i, e in enumerate(ids)}
    result = {}
    for p in PERIODS:
        for sc in SCENARIOS:
            if done(PLAYBACK / p / sc, sc):
                result[f'{p}_{sc}'] = run(p, sc, index)
                print('run', p, sc, flush=True)
    return result


def step8_summary():
    rows = list(csv.DictReader(open(ROOT / 'output' / 'scenarios' / 'runs.csv', encoding='utf-8')))
    out = {}
    for p in PERIODS:
        for sc in SCENARIOS:
            r = [x for x in rows if x['period'] == p and x['scenario'] == sc]
            if not r:
                continue
            sp = [float(x['speed_kmh']) for x in r]
            out[f'{p}_{sc}'] = {'seeds': len(r), 'speed_kmh': round(statistics.mean(sp), 1),
                                'speed_min': round(min(sp), 1), 'speed_max': round(max(sp), 1),
                                'trip_min': round(statistics.mean(float(x['duration_s']) for x in r) / 60, 1),
                                'avoid_km': round(statistics.mean(float(x['avoid_km']) for x in r), 1),
                                'congested_km': round(statistics.mean(float(x['congested_km']) for x in r), 1)}
    return out


def water(ground):
    d = np.load(RUN / 'depth_hourly.npz')
    times = [str(t) for t in d['times']]
    hours = [FLOOD_AT + timedelta(hours=h) for h in (-1, 0, 1)]
    depth = np.stack([d['depth'][times.index(t.strftime('%Y-%m-%dT%H:%M'))] for t in hours]).astype('float32')
    rows, cols = np.nonzero((depth >= WATER_MIN_M).any(axis=0))
    a, _, c, _, e, f = d['transform']
    x, y = c + a * (cols + 0.5), f + e * (rows + 0.5)
    lon, lat = TO_LL.transform(x, y)
    z = ground.at_utm(x, y)
    cells = np.column_stack([lon, lat, z]).astype('float32')
    dep = np.clip(np.round(depth[:, rows, cols] * 100), 0, 65535).astype('uint16')  # cm, [hour, cell]
    (WEB / 'water.bin').write_bytes(np.array([len(rows)], 'uint32').tobytes() + cells.tobytes() + dep.tobytes())
    (WEB / 'water.json').write_text(json.dumps({'run': RUN.name, 'hours': [t.isoformat() for t in hours],
                                                'cell_m': float(a), 'min_m': WATER_MIN_M}))
    print(f'water: {len(rows):,} cells')


def terrain(ground):
    z = ground.z.astype('float32')
    sea = rasterio.open(SEA).read(1).astype(bool)
    land = (z != ground.r.nodata) & ~sea & (z > 0)
    t = ground.r.transform
    lines = []
    for axis in (0, 1):
        for i in range(0, z.shape[axis], TERRAIN_STEP):
            idx = np.arange(0, z.shape[1 - axis], TERRAIN_STEP)
            r, c = (np.full_like(idx, i), idx) if axis == 0 else (idx, np.full_like(idx, i))
            ok = land[r, c]
            run_ = []
            for rr, cc, k in zip(r, c, ok):
                if k:
                    x, y = t * (cc + 0.5, rr + 0.5)
                    lo, la = TO_LL.transform(x, y)
                    run_.append([round(lo, 5), round(la, 5), round(float(z[rr, cc]), 1)])
                elif run_:
                    if len(run_) > 1:
                        lines.append(run_)
                    run_ = []
            if len(run_) > 1:
                lines.append(run_)
    (WEB / 'terrain.json').write_text(json.dumps(lines, separators=(',', ':')))
    print(f'terrain: {len(lines):,} lines')


def buildings(ground):
    tmp = WEB.parent / 'build_tmp'
    tmp.mkdir(exist_ok=True)
    box = tmp / 'island.osm.pbf'
    subprocess.run(['osmium', 'extract', '-b', ','.join(map(str, ISLAND)), str(OSM), '-o', str(box),
                    '--overwrite'], check=True)
    subprocess.run(['osmium', 'tags-filter', str(box), 'w/building', 'r/building', '-o',
                    str(tmp / 'buildings.osm.pbf'), '--overwrite'], check=True)
    subprocess.run(['osmium', 'export', str(tmp / 'buildings.osm.pbf'), '-f', 'geojsonseq', '--geometry-types',
                    'polygon', '-o', str(tmp / 'buildings.geojsonseq'), '--overwrite'], check=True)
    out, tagged = [], 0
    for line in open(tmp / 'buildings.geojsonseq', encoding='utf-8'):
        g = json.loads(line.strip('\x1e'))
        tags = g['properties']
        h = None
        try:
            h = float(str(tags.get('height', '')).replace('m', '').strip())
        except ValueError:
            try:
                h = float(tags.get('building:levels')) * LEVEL_M
            except (TypeError, ValueError):
                pass
        tagged += h is not None
        polys = g['geometry']['coordinates'] if g['geometry']['type'] == 'MultiPolygon' else [g['geometry']['coordinates']]
        for poly in polys:
            ring = np.array(poly[0])
            x, y = TO_UTM.transform(ring[:, 0].mean(), ring[:, 1].mean())
            base = float(ground.at_utm(np.array([x]), np.array([y]))[0])
            out.append([[[round(a, 6), round(b, 6), round(base, 1)] for a, b in ring], round(h or LEVEL_M, 1),
                        int(h is not None)])
    (WEB / 'buildings.json').write_text(json.dumps(out, separators=(',', ':')))
    print(f'buildings: {len(out):,} footprints, {tagged:,} with height or levels')


def basemap(ground):
    import contourpy
    sea = rasterio.open(SEA).read(1).astype(bool)
    land = ((ground.z != ground.r.nodata) & ~sea).astype('float32')
    t = ground.r.transform
    coast = []
    for line in contourpy.contour_generator(z=land).lines(0.5):
        if len(line) < 20:  # small islets and single cells
            continue
        xs, ys = t * (line[::2, 0] + 0.5, line[::2, 1] + 0.5)
        lo, la = TO_LL.transform(xs, ys)
        coast.append([[round(a, 5), round(b, 5)] for a, b in zip(lo, la)])
    tmp = WEB.parent / 'build_tmp'  # island.osm.pbf is written by buildings()
    subprocess.run(['osmium', 'tags-filter', str(tmp / 'island.osm.pbf'), 'n/place=city,town', '-o',
                    str(tmp / 'places.osm.pbf'), '--overwrite'], check=True)
    places = subprocess.run(['osmium', 'export', str(tmp / 'places.osm.pbf'), '-f', 'geojsonseq'], check=True,
                            capture_output=True, text=True).stdout
    names = []
    for line in places.split('\x1e'):
        if not line.strip():
            continue
        f = json.loads(line)
        if f['properties'].get('name'):
            lo, la = f['geometry']['coordinates']
            names.append({'name': f['properties']['name'], 'kind': f['properties']['place'], 'lon': lo, 'lat': la})
    (WEB / 'basemap.json').write_text(json.dumps({'coast': coast, 'places': names}, ensure_ascii=False,
                                                 separators=(',', ':')))
    print(f'basemap: {len(coast)} coast lines, {len(names)} places')


def news():
    rows = [r for r in csv.DictReader(open(ROOT / 'data' / 'validation' / 'flood-reports-2569-10-29.csv',
                                           encoding='utf-8')) if r['lat']]
    return [{'id': r['id'], 'location': r['location'], 'severity': r['severity'], 'source': r['source'],
             'lon': float(r['lon']), 'lat': float(r['lat'])} for r in rows]


def main(what):
    WEB.mkdir(parents=True, exist_ok=True)
    ground = Ground()
    if what == 'all':
        ids = roads(ground)
        water(ground)
        terrain(ground)
        buildings(ground)
        basemap(ground)
    elif what == 'basemap':
        basemap(ground)
        return
    elif what == 'roads':  # geometry only; edge order is the same, so the run files stay valid
        roads(ground)
        return
    else:
        ids = json.loads((WEB / 'roads.json').read_text())['ids']
    series = runs(ids)
    frames = {p: [f'{t // 3600:02d}:{t % 3600 // 60:02d}' for t in frame_starts(p)] for p in PERIODS}
    meta = {'periods': {p: f'{h:02d}:00' for p, h in PERIODS.items()}, 'scenarios': SCENARIOS, 'labels': LABELS,
            'floods': list(FLOODS), 'frame_s': PLAYBACK_S, 'warmup_frames': WARMUP // PLAYBACK_S,
            'frames': frames, 'series': series, 'step8': step8_summary(), 'news': news()}
    (WEB / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False))
    print(f'{len(series)} runs -> {WEB}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'all')
