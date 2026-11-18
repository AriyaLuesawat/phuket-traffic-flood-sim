"""Step 9c: packs the step 9 web data into the lighter files the viewer (web/app) reads.

    .venv/bin/python scripts/pack_web_data.py         # reads web/app/data (export_web.py), writes web/app/data-c

Reads only what export_web.py wrote (web/app/data) plus the FABDEM, sea and ESA WorldCover rasters of the flood
model (data/processed/flood). Nothing is invented: every value comes from those files, only packed smaller.

Writes web/app/data-c/ (generated, not committed):
  meta.json.gz             meta.json unchanged, gzip
  c.json                   names of the main roads, road kinds, grid of the water cells, tile ranges, file sizes
  roads.bin.gz             every road edge of roads.bin/roads.json: vertices as zigzag varint deltas of
                           lon/lat in 1e-6 degree (finer than the float32 of roads.bin) and ground in 0.1 m,
                           kind, lanes, name index and length (0.1 m, as roads.json). The SUMO edge ids are left
                           out (the viewer never shows them)
  runs/<p>_<s>.bin.gz      runs/<p>_<s>.bin with the same bytes, stored edge by edge (all frames of an edge
                           together, which gzip packs ~8x smaller) instead of frame by frame
  water.bin.gz             water.bin cells as column/row of the 30 m flood grid (cells sit exactly on it) and
                           the same depths (cm, 07:00/08:00/09:00); the ground height is left out because the
                           water is drawn on the 3D terrain
  grid.json.gz             the ground lines of terrain.json (FABDEM land cells every 210 m) as flat lon/lat
                           lines: the faint grid of the dark map style (heights come from the 3D terrain)
  land.json.gz             the coastline rings of basemap.json as land polygons (rings inside the island are
                           holes) and the place names
  dem/{z}/{x}/{y}.png      FABDEM (dem_fabdem.tif, as terrain.json) as Terrarium-encoded Web Mercator tiles,
                           zoom 8-12, for the MapLibre 3D terrain and hillshade. Sea and no-data = 0 m, as export_web
  bld/{z}/{x}/{y}.pbf.gz   buildings.json as Mapbox vector tiles, zoom 12-14: footprint, height (m) and whether
                           the height came from an OSM tag (1) or is the assumed one storey (0). Each building is
                           stored once, in the tile that holds its first vertex. The ground height is left out
                           (MapLibre puts the buildings on the terrain)
"""
import gzip
import json
import math
import shutil
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from shapely.geometry import Polygon, mapping

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'web' / 'app' / 'data'  # written by scripts/export_web.py
FLOOD = SRC.parent.parent.parent / 'data' / 'processed' / 'flood'
OUT = ROOT / 'web' / 'app' / 'data-c'
DEM_Z = range(8, 13)
BLD_Z = range(12, 15)
EXTENT = 8192
UTM = 'EPSG:32647'
TO_LL = Transformer.from_crs(UTM, 'EPSG:4326', always_xy=True)


def gz(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data, 9, mtime=0))


def zigzag(a):
    a = np.asarray(a, 'int64')
    return ((a << 1) ^ (a >> 63)).astype('uint64')


def varints(u):
    """uint64 array -> LEB128 bytes (vectorised)."""
    u = np.asarray(u, 'uint64')
    out = []
    n = np.ones(len(u), 'int64')
    t = u >> np.uint64(7)
    while t.any():
        n += t > 0
        t >>= np.uint64(7)
    total = int(n.sum())
    buf = np.zeros(total, 'uint8')
    pos = np.concatenate([[0], np.cumsum(n)[:-1]])
    v = u.copy()
    for k in range(int(n.max())):
        live = n > k
        byte = (v[live] & np.uint64(0x7F)).astype('uint8')
        more = n[live] > k + 1
        buf[pos[live] + k] = byte | (more.astype('uint8') << 7)
        v[live] >>= np.uint64(7)
    out.append(buf.tobytes())
    return b''.join(out)


# ---------------------------------------------------------------- roads
def roads():
    b = (SRC / 'roads.bin').read_bytes()
    n, nv = np.frombuffer(b, 'uint32', 2)
    off = np.frombuffer(b, 'uint32', n + 1, 8)
    v = np.frombuffer(b, 'float32', nv * 3, 8 + 4 * (n + 1)).reshape(-1, 3).astype('float64')
    rj = json.loads((SRC / 'roads.json').read_text())
    names = [''] + sorted({x for x in rj['name'] if x})
    idx = {x: i for i, x in enumerate(names)}
    lon0, lat0 = 98.0, 7.5
    q = np.column_stack([np.round((v[:, 0] - lon0) * 1e6), np.round((v[:, 1] - lat0) * 1e6),
                         np.round(np.maximum(v[:, 2], 0) * 10)]).astype('int64')
    d = np.diff(q, axis=0, prepend=np.zeros((1, 3), 'int64'))
    head = np.array([0x31434452, n, nv], 'uint32').tobytes()  # 'RDC1'
    body = (np.round(np.array(rj['length']) * 10).astype('uint32').tobytes()
            + np.array([idx[x] for x in rj['name']], 'uint16').tobytes()
            + np.diff(off).astype('uint16').tobytes()
            + np.array(rj['kind'], 'uint8').tobytes() + np.array(rj['lanes'], 'uint8').tobytes()
            + varints(zigzag(d.reshape(-1))))
    gz(OUT / 'roads.bin.gz', head + body)
    print(f'roads: {n:,} edges, {nv:,} vertices, {len(head + body):,} B raw')
    return {'n': int(n), 'nv': int(nv), 'origin': [lon0, lat0], 'names': names, 'kinds': rj['kinds']}


# ---------------------------------------------------------------- runs
def runs(meta, n):
    for f in sorted((SRC / 'runs').glob('*.bin')):
        p = f.stem
        period = next(k for k in meta['periods'] if p.startswith(k + '_'))
        fr = len(meta['frames'][period])
        a = np.frombuffer(f.read_bytes(), 'uint8').reshape(-1, fr, n)
        gz(OUT / 'runs' / (f.name + '.gz'), a.transpose(0, 2, 1).tobytes())
    print('runs:', len(list((SRC / 'runs').glob('*.bin'))))


# ---------------------------------------------------------------- water cells
def water(dem):
    wj = json.loads((SRC / 'water.json').read_text())
    b = (SRC / 'water.bin').read_bytes()
    n = int(np.frombuffer(b, 'uint32', 1)[0])
    c = np.frombuffer(b, 'float32', n * 3, 4).reshape(-1, 3).astype('float64')
    dep = np.frombuffer(b, 'uint16', 3 * n, 4 + 12 * n)
    x, y = Transformer.from_crs('EPSG:4326', UTM, always_xy=True).transform(c[:, 0], c[:, 1])
    t = dem.transform
    col = (x - t.c) / t.a - 0.5
    row = (y - t.f) / t.e - 0.5
    assert np.abs(col - np.round(col)).max() < 0.1 and np.abs(row - np.round(row)).max() < 0.1, 'cells off the grid'
    col, row = np.round(col).astype('int64'), np.round(row).astype('int64')
    c0, c1, r0, r1 = int(col.min()), int(col.max()) + 1, int(row.min()), int(row.max()) + 1
    gz(OUT / 'water.bin.gz', np.array([n], 'uint32').tobytes() + (col - c0).astype('uint16').tobytes()
       + (row - r0).astype('uint16').tobytes() + dep.tobytes())
    # 4 strips: each is drawn as one image quad, so the UTM -> Web Mercator bend stays under ~1.5 m
    strips, k = [], 4
    for i in range(k):
        a, bb = r0 + (r1 - r0) * i // k, r0 + (r1 - r0) * (i + 1) // k
        corners = [(c0, a), (c1, a), (c1, bb), (c0, bb)]  # tl, tr, br, bl
        ll = [list(map(lambda v: round(v, 7), TO_LL.transform(t.c + t.a * cc, t.f + t.e * rr))) for cc, rr in corners]
        strips.append({'row0': a - r0, 'rows': bb - a, 'coords': ll})
    print(f'water: {n:,} cells, grid {c1 - c0} x {r1 - r0}')
    return {**wj, 'n': n, 'cols': c1 - c0, 'rows': r1 - r0, 'strips': strips}


# ---------------------------------------------------------------- land polygons
def land():
    bm = json.loads((SRC / 'basemap.json').read_text())
    rings = [Polygon(r) for r in bm['coast']]
    rings = [r if r.is_valid else r.buffer(0) for r in rings]
    order = sorted(range(len(rings)), key=lambda i: -rings[i].area)
    parent = {}
    for i in order:  # smallest ring that contains this one
        cand = [j for j in order if j != i and rings[j].area > rings[i].area and rings[j].contains(rings[i])]
        parent[i] = min(cand, key=lambda j: rings[j].area) if cand else None
    depth = {}
    for i in order:
        d, p = 0, parent[i]
        while p is not None:
            d, p = d + 1, parent[p]
        depth[i] = d
    feats = []
    for i in order:
        if depth[i] % 2:
            continue
        holes = [rings[j] for j in order if parent[j] == i]
        poly = rings[i]
        for h in holes:
            poly = poly.difference(h)
        g = mapping(poly)
        feats.append({'type': 'Feature', 'properties': {}, 'geometry': json.loads(json.dumps(g))})
    fc = {'type': 'FeatureCollection', 'features': feats}
    txt = json.dumps({'land': fc, 'places': bm['places']}, ensure_ascii=False, separators=(',', ':'))
    txt = __import__('re').sub(r'(\d+\.\d{5})\d+', r'\1', txt)
    gz(OUT / 'land.json.gz', txt.encode())
    print(f'land: {len(feats)} polygons from {len(rings)} coast rings')


# ---------------------------------------------------------------- grid lines (terrain.json without heights)
def grid():
    lines = json.loads((SRC / 'terrain.json').read_text())
    txt = json.dumps({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, 'geometry': {
        'type': 'MultiLineString', 'coordinates': [[[p[0], p[1]] for p in ln] for ln in lines]}}]}, separators=(',', ':'))
    gz(OUT / 'grid.json.gz', txt.encode())
    print(f'grid: {len(lines):,} lines')


# ---------------------------------------------------------------- tiles helpers
def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def tile_bounds_3857(x, y, z):
    s = 2 * math.pi * 6378137 / 2 ** z
    o = math.pi * 6378137
    return (x * s - o, o - (y + 1) * s, (x + 1) * s - o, o - y * s)


# ---------------------------------------------------------------- terrain (FABDEM, Terrarium)
def dem_tiles(dem):
    z = dem.read(1).astype('float32')
    z = np.where(z == dem.nodata, 0, np.maximum(z, 0)).astype('float32')
    sea = rasterio.open(FLOOD / 'sea.tif').read(1).astype(bool)
    z[sea] = 0
    b = dem.bounds
    lo0, la0 = TO_LL.transform(b.left, b.bottom)
    lo1, la1 = TO_LL.transform(b.right, b.top)
    bounds = [round(lo0, 4), round(la0, 4), round(lo1, 4), round(la1, 4)]
    count = size = 0
    for zz in DEM_Z:
        x0, y1 = lonlat_to_tile(lo0, la0, zz)
        x1, y0 = lonlat_to_tile(lo1, la1, zz)
        for tx in range(int(x0), int(x1) + 1):
            for ty in range(int(y0), int(y1) + 1):
                l, bt, r, tp = tile_bounds_3857(tx, ty, zz)
                dst = np.zeros((256, 256), 'float32')
                reproject(z, dst, src_transform=dem.transform, src_crs=dem.crs,
                          dst_transform=rasterio.transform.from_bounds(l, bt, r, tp, 256, 256), dst_crs='EPSG:3857',
                          resampling=Resampling.bilinear, src_nodata=None, dst_nodata=0)
                v = dst.astype('float64') + 32768
                rgb = np.stack([np.floor(v / 256), np.floor(v) % 256, np.floor((v - np.floor(v)) * 256)], -1)
                p = OUT / 'dem' / str(zz) / str(tx) / f'{ty}.png'
                p.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(rgb.astype('uint8'), 'RGB').save(p, optimize=True)
                count += 1
                size += p.stat().st_size
    print(f'dem: {count} tiles, {size:,} B')
    return {'bounds': bounds, 'minzoom': DEM_Z[0], 'maxzoom': DEM_Z[-1]}


# ---------------------------------------------------------------- buildings (MVT)
def pb_varint(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def pb_field(num, wire, payload):
    key = pb_varint((num << 3) | wire)
    if wire == 2:
        return key + pb_varint(len(payload)) + payload
    return key + payload


def zz(v):
    return (v << 1) ^ (v >> 63)


def mvt_tile(feats):
    """feats: list of (ring as [[x, y], ...] tile ints, height, tagged). One layer 'b'."""
    values, vidx = [], {}

    def val(kind, v):
        k = (kind, v)
        if k not in vidx:
            vidx[k] = len(values)
            if kind == 'd':
                values.append(pb_field(3, 1, np.float64(v).tobytes()))
            else:
                values.append(pb_field(5, 0, pb_varint(v)))
        return vidx[k]

    out = []
    for i, (ring, h, t) in enumerate(feats):
        geom = [1 | (1 << 3)]
        px = py = 0
        for j, (x, y) in enumerate(ring):
            if j == 1:
                geom.append(2 | ((len(ring) - 1) << 3))
            geom += [zz(x - px), zz(y - py)]
            px, py = x, y
        geom.append(7 | (1 << 3))
        tags = [0, val('d', h), 1, val('u', t)]
        f = (pb_field(1, 0, pb_varint(i + 1)) + pb_field(2, 2, b''.join(pb_varint(x) for x in tags))
             + pb_field(3, 0, pb_varint(3)) + pb_field(4, 2, b''.join(pb_varint(x) for x in geom)))
        out.append(pb_field(2, 2, f))
    layer = (pb_field(15, 0, pb_varint(2)) + pb_field(1, 2, b'b') + b''.join(out)
             + pb_field(3, 2, b'h') + pb_field(3, 2, b't')
             + b''.join(pb_field(4, 2, v) for v in values) + pb_field(5, 0, pb_varint(EXTENT)))
    return pb_field(3, 2, layer)


def buildings():
    bld = json.loads((SRC / 'buildings.json').read_text())
    info, total = {}, 0
    for z in BLD_Z:
        tiles = {}
        n2 = 2 ** z
        for b in bld:
            ring = np.array(b[0], 'float64')[:, :2]
            mx = (ring[:, 0] + 180) / 360 * n2
            my = (1 - np.log(np.tan(np.radians(ring[:, 1])) + 1 / np.cos(np.radians(ring[:, 1]))) / np.pi) / 2 * n2
            tx, ty = int(mx[0]), int(my[0])
            px = np.round((mx - tx) * EXTENT).astype('int64')
            py = np.round((my - ty) * EXTENT).astype('int64')
            pts = [(int(a), int(c)) for a, c in zip(px, py)]
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            dedup = [p for k, p in enumerate(pts) if k == 0 or p != pts[k - 1]]
            if len(dedup) > 1 and dedup[0] == dedup[-1]:
                dedup = dedup[:-1]
            if len(dedup) < 3:
                continue
            area = sum(dedup[k][0] * dedup[(k + 1) % len(dedup)][1] - dedup[(k + 1) % len(dedup)][0] * dedup[k][1]
                       for k in range(len(dedup)))
            if area == 0:
                continue
            if area < 0:
                dedup = dedup[::-1]
            tiles.setdefault((tx, ty), []).append((dedup, float(b[1]), int(b[2])))
        size = 0
        for (tx, ty), feats in tiles.items():
            p = OUT / 'bld' / str(z) / str(tx) / f'{ty}.pbf.gz'
            gz(p, mvt_tile(feats))
            size += p.stat().st_size
        kept = sum(len(f) for f in tiles.values())
        info[z] = {'tiles': len(tiles), 'bytes': size, 'buildings': kept}
        total += size
        print(f'buildings z{z}: {len(tiles)} tiles, {kept:,} footprints, {size:,} B')
    return {'minzoom': BLD_Z[0], 'maxzoom': BLD_Z[-1], 'zooms': info, 'count': len(bld),
            'tagged': sum(b[2] for b in bld)}


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    meta = json.loads((SRC / 'meta.json').read_text())
    gz(OUT / 'meta.json.gz', (SRC / 'meta.json').read_bytes())
    dem = rasterio.open(FLOOD / 'dem_fabdem.tif')
    c = {'roads': roads()}
    runs(meta, c['roads']['n'])
    c['water'] = water(dem)
    land()
    grid()
    c['dem'] = dem_tiles(dem)
    c['buildings'] = buildings()
    c['files'] = {str(p.relative_to(OUT)): p.stat().st_size for p in sorted(OUT.rglob('*'))
                  if p.is_file() and (p.parent == OUT or p.parent.name == 'runs')}
    (OUT / 'c.json').write_text(json.dumps(c, ensure_ascii=False, separators=(',', ':')))
    print('->', OUT)


if __name__ == '__main__':
    main()
