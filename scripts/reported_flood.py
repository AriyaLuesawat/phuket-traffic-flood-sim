"""Step 7 (alternative flood input): water on the roads only at the places the news reported on 29 Oct 2569.

    .venv/bin/python scripts/reported_flood.py            # depth 0.3 m (main)
    .venv/bin/python scripts/reported_flood.py 0.1        # sensitivity
    .venv/bin/python scripts/reported_flood.py 0.3 50     # sensitivity of the radius (m), step 10

The flood model of step 6 put 126 km of 'avoid' road in the wrong places (0 of 14 reported places at >= 0.3 m,
docs/flood-check.md) and satellite flood maps (GISTDA) show no flood in Phuket for the event, so this input
uses the reported places instead: a lower bound on the extent, since the news names only notable places.
  places   the 14 geocoded rows of data/validation/flood-reports-2569-10-29.csv (geocoded from place names; F17
           and F18 are approximate)
  edges    every road edge open to cars within RADIUS m of a place (ASSUMPTION: the reported water covers the
           road around the named place); a place with no such edge (a shop or park set back from the road)
           takes the nearest edge and every edge up to FALLBACK_SLACK m farther, i.e. the road in front
  depth    the same depth at every place (ASSUMPTION: most reports give no depth; 0.3 m = 'avoid', the
           depth of 'knee level' and 'small cars cannot pass' reports is not measured)
  time     water from 07:00 to 09:00 on 29 Oct, linear to 0 at 06:00 and 10:00 (reports at 07:45 to 08:10 and
           'morning'; back to normal by 10:00, Spacebar 29 Oct 2569, see docs/step7-method.md)

Outputs: output/flood_traffic/edge_depth_reports_d<mm>[_r<radius m>].npz (same format as road_flood_depth.py),
         docs/reported-flood.md (main radius only)
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import sumolib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from road_flood_depth import OUT, RUN  # noqa: E402
from run_baseline import NET  # noqa: E402

POINTS = ROOT / 'data' / 'validation' / 'flood-reports-2569-10-29.csv'
RADIUS = 100.0
FALLBACK, FALLBACK_SLACK = 500.0, 30.0
WET = (datetime(2026, 10, 29, 7), datetime(2026, 10, 29, 9))


def main(depth_m=0.3, radius=RADIUS):
    name = f'reports_d{round(depth_m * 1000):03d}' + ('' if radius == RADIUS else f'_r{round(radius):03d}')
    net = sumolib.net.readNet(str(NET))
    points = [p for p in csv.DictReader(open(POINTS, encoding='utf-8')) if p['lat']]
    edges, per_point = {}, []
    for p in points:
        x, y = net.convertLonLat2XY(float(p['lon']), float(p['lat']))
        near = [(d, e) for e, d in net.getNeighboringEdges(x, y, FALLBACK)
                if e.getFunction() != 'internal' and e.allows('passenger')]
        nearest = min(d for d, _ in near)
        near = [e for d, e in near if d <= max(radius, nearest + FALLBACK_SLACK)]
        for e in near:
            edges[e.getID()] = e.getLength()
        per_point.append((p, len(near), sum(e.getLength() for e in near) / 1000))
    times = np.load(OUT / f'edge_depth_{RUN.name}.npz')['times']  # same hours as the main flood run
    when = [datetime.fromisoformat(str(t)) for t in times]
    level = np.array([1.0 if WET[0] <= t <= WET[1] else 0.0 for t in when])
    ids = sorted(edges)
    depth = (level[:, None] * depth_m * np.ones((1, len(ids)))).astype('float32')
    np.savez_compressed(OUT / f'edge_depth_{name}.npz', edges=np.array(ids), times=times, depth_m=depth,
                        length_m=np.array([edges[e] for e in ids]))

    km = sum(edges.values()) / 1000
    if radius != RADIUS:
        print(f'{name}: {len(ids)} edges, {km:.1f} km')
        return
    lines = [f'# น้ำบนถนนจากจุดที่ข่าวรายงาน ({name})', '',
             f'ถนนที่รถยนต์ใช้ได้ในรัศมี {RADIUS:.0f} ม. จากจุดข่าว {len(points)} จุด ความลึก {depth_m} ม. ทุกจุด '
             f'(จุดที่ไม่มีถนนในรัศมีนั้นใช้ถนนที่ใกล้ที่สุดและถนนที่ห่างกว่านั้นไม่เกิน {FALLBACK_SLACK:.0f} ม.) '
             f'มีน้ำ {WET[0]:%d %b %H:%M}–{WET[1]:%H:%M} (ค่อย ๆ ขึ้นจาก 06:00 และลดเป็น 0 ที่ 10:00) '
             'สร้างโดย `scripts/reported_flood.py`', '',
             f'รวม {len(ids)} edge ยาว {km:.1f} กม. (นับทั้งสองทิศทาง) เทียบกับแบบจำลองน้ำท่วมขั้นที่ 6 ที่มีถนนที่ควรเลี่ยง 126.3 กม.', '',
             '| จุด | สถานที่ | ข่าวรายงาน | edge | ความยาว (กม.) | หมายเหตุพิกัด |', '|---|---|---|---|---|---|']
    lines += [f"| {p['id']} | {p['location']} | {p['severity']} | {n} | {k:.2f} | {p['geocoded_as'][:60]} |"
              for p, n, k in per_point]
    (ROOT / 'docs' / 'reported-flood.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.3, float(sys.argv[2]) if len(sys.argv) > 2 else RADIUS)
