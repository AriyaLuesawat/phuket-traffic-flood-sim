"""Step 7a: flood depth on every road edge for every hour of a flood run, and the speed limit it implies.

    .venv/bin/python scripts/road_flood_depth.py                  # main run of step 6
    .venv/bin/python scripts/road_flood_depth.py <flood run folder>

Edge depth = deepest grid cell under the edge's centre line (sampled every 5 m), following Pregnolato et al.
(2017), who take the maximum depth along a journey. Bridges and tunnels (OSM bridge=* / tunnel=*) are given
depth 0: the DEM has no bridge decks, so a road crossing a stream would otherwise read the stream depth.
Stream crossings without a bridge tag (mostly culverts) have the same problem, so road cells within
CROSSING_BUFFER cells of an OSM waterway line (river, stream, canal, drain, ditch) are left out of the edge
depth (ASSUMPTION: the road passes over the water there). OSM maps only part of the streams.

Depth-speed function (Pregnolato et al. 2017, eq. 4, w in mm, v in km/h, fitted for 0 <= w < 300 mm):
    v(w) = 0.0009 w^2 - 0.5529 w + 86.9448
v(w) is a safe upper speed, so it caps the edge speed limit: new limit = min(limit, v(w)).
Roads are never closed: in Phuket, rain floods last a few hours and roads stay open (the provincial disaster
office reported water back to normal by 10:00 on 29 Oct 2569). At w >= AVOID_MM (300 mm, where a passenger
car starts to float, their Table 1, row 10) the speed is held at v(300 mm) = 2.1 km/h (ASSUMPTION). Drivers
then avoid the road because it is slow ("standing water, waiting to drain"), not because it is closed.

The rain labelled hour T in the rain file is the total of the preceding hour (Open-Meteo convention), so the
depth stored after model hour i is the state at time times[i].

Outputs: output/flood_traffic/edge_depth_<run>.npz (edges, times, depth_m [hour x edge], length_m),
         docs/road-flood.md
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import rasterio
import sumolib

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / 'output' / 'flood' / 'oct2569_drain80_soilC_dem_fabdem_conditioned_roads_78h'
OSM = ROOT / 'data' / 'processed' / 'phuket-roads.osm'
WATERWAYS = ROOT / 'data' / 'processed' / 'phuket-waterways.geojsonseq'  # osmium tags-filter + export, see main()
CROSSING_BUFFER = 1  # cells (30 m)
OUT = ROOT / 'output' / 'flood_traffic'
AVOID_MM = 300.0  # depth at which the road is reported as 'avoid: standing water'


def pregnolato_kmh(depth_m):
    """Upper safe speed (km/h) for flood depth (m), held at v(AVOID_MM) for deeper water."""
    w = np.minimum(np.asarray(depth_m, float) * 1000, AVOID_MM)
    return 0.0009 * w ** 2 - 0.5529 * w + 86.9448


def bridge_ways():
    ways = set()
    for _, el in ET.iterparse(OSM):
        if el.tag == 'way':
            tags = {t.get('k'): t.get('v') for t in el.iter('tag')}
            if tags.get('bridge', 'no') != 'no' or tags.get('tunnel', 'no') != 'no':
                ways.add(el.get('id'))
            el.clear()
    return ways


def waterway_mask(transform, shape):
    """Cells crossed by an OSM waterway line, widened by CROSSING_BUFFER cells."""
    import json
    from pyproj import Transformer
    from rasterio.features import rasterize
    from scipy import ndimage
    from shapely.geometry import shape as geom
    from shapely.ops import transform as reproject
    to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32647', always_xy=True).transform
    lines = [reproject(to_utm, geom(json.loads(row.strip('\x1e'))['geometry'])) for row in open(WATERWAYS)]
    mask = rasterize(lines, out_shape=shape, transform=transform, all_touched=True).astype(bool)
    return ndimage.binary_dilation(mask, iterations=CROSSING_BUFFER)


def edge_cells(net, transform, shape):
    """Grid cells (flat indices) under each edge's centre line, sampled every 5 m as in road_mask()."""
    ox, oy = net.getLocationOffset()
    cells = {}
    for edge in net.getEdges():
        pts = np.array(edge.getShape()) - (ox, oy)  # net x,y -> UTM 47N
        idx = []
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            k = max(int(np.hypot(x1 - x0, y1 - y0) / 5), 1)
            cols, rows = ~transform * (np.linspace(x0, x1, k + 1), np.linspace(y0, y1, k + 1))
            rows, cols = rows.astype(int), cols.astype(int)
            ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
            idx.append(rows[ok] * shape[1] + cols[ok])
        cells[edge.getID()] = np.unique(np.concatenate(idx)) if idx else np.array([], int)
    return cells


def main(run):
    data = np.load(run / 'depth_hourly.npz')
    depth, times = data['depth'].astype('float32'), data['times']
    transform = rasterio.Affine(*data['transform'])
    net = sumolib.net.readNet(str(ROOT / 'network' / 'phuket.net.xml'))
    bridges = bridge_ways()
    water = waterway_mask(transform, depth.shape[1:]).ravel()
    edges, lengths, table = [], [], []
    flat = depth.reshape(len(depth), -1)
    n_cells = n_crossing = 0
    for eid, idx in edge_cells(net, transform, depth.shape[1:]).items():
        n_cells += len(idx)
        n_crossing += water[idx].sum()
        idx = idx[~water[idx]]
        edges.append(eid)
        lengths.append(net.getEdge(eid).getLength())
        way = eid.lstrip('-').split('#')[0]
        table.append(np.zeros(len(depth)) if way in bridges or not len(idx) else flat[:, idx].max(axis=1))
    table = np.array(table, 'float32').T  # hour x edge
    lengths = np.array(lengths)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / f'edge_depth_{run.name}.npz', edges=np.array(edges), times=times, depth_m=table,
                        length_m=lengths)
    n_bridge = sum(e.lstrip('-').split('#')[0] in bridges for e in edges)

    lines = ['# ความลึกน้ำบนถนน (ขั้นที่ 7)', '',
             f'จากผลแบบจำลองน้ำท่วม `{run.name}` · ถนน {len(edges):,} edge ยาวรวม {lengths.sum() / 1000:,.0f} กม. '
             f'(ไม่นับสะพานและอุโมงค์ {n_bridge} edge และเซลล์ถนนในระยะ {CROSSING_BUFFER} เซลล์จากลำน้ำ OSM '
             f'{n_crossing:,} จาก {n_cells:,} เซลล์) · ความลึกของ edge = ค่ามากสุดของเซลล์ใต้เส้นถนน · '
             'สร้างโดย `scripts/road_flood_depth.py`', '',
             '| เวลา | ถนนน้ำ ≥ 0.1 ม. (กม.) | ถนนน้ำ ≥ 0.3 ม. ควรเลี่ยง (กม.) | edge ที่ควรเลี่ยง |', '|---|---|---|---|']
    km = lambda m: float(lengths[m].sum()) / 1000  # noqa: E731
    for i, t in enumerate(times):
        if i % 3 == 2 or i == len(times) - 1:
            lines.append(f'| {t} | {km(table[i] >= 0.1):.1f} | {km(table[i] >= 0.3):.1f} | {(table[i] >= 0.3).sum():,} |')
    peak = int(np.argmax([km(r >= 0.3) for r in table]))
    lines += ['', f'ถนนน้ำ ≥ 0.3 ม. มากที่สุด {km(table[peak] >= 0.3):.1f} กม. เวลา {times[peak]} (ไม่ปิดถนน ใช้ลดความเร็ว)', '']
    (ROOT / 'docs' / 'road-flood.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RUN)
