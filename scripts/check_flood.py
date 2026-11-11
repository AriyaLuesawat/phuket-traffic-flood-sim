"""Step 6c: compares modelled maximum depth with flood locations reported in the news, and draws maps.

    .venv/bin/python scripts/check_flood.py output/flood/<run> [<run> ...]

Reported points (data/validation/flood-reports-2569-10-29.csv) are geocoded street-level places and the news
reports flooded roads, so each point is scored by the deepest modelled ROAD cell within RADIUS m. As a
reference, the same score is computed around random road cells in built-up land: a model with skill should
flood the reported places more often than random roads.
This is a qualitative check only (9 geocoded points, no observed depths).

Outputs: <run>/points.csv, docs/flood-check.md, docs/img/step6-max-depth.png
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from pyproj import Transformer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POINTS = ROOT / 'data' / 'validation' / 'flood-reports-2569-10-29.csv'
LANDCOVER = ROOT / 'data' / 'processed' / 'flood' / 'landcover.tif'
ROADS = ROOT / 'data' / 'processed' / 'flood' / 'roads.tif'
RADIUS = 60.0
THRESHOLDS = (0.1, 0.3)
TO_UTM = Transformer.from_crs('EPSG:4326', 'EPSG:32647', always_xy=True)


def neighbourhood_max(depth, transform, x, y):
    col, row = ~transform * (x, y)
    r = int(np.ceil(RADIUS / transform.a))
    r0, c0 = int(row) - r, int(col) - r
    block = depth[max(r0, 0):int(row) + r + 1, max(c0, 0):int(col) + r + 1]
    return float(block.max()) if block.size else float('nan')


def crop(path, shape, transform):
    """Reads a full-island grid and crops it to the max_depth grid (a window of the same grid)."""
    with rasterio.open(path) as f:
        a = f.read(1)
        col0, row0 = ~f.transform * (transform.c, transform.f)
    r0, c0 = int(round(row0)), int(round(col0))
    return a[r0:r0 + shape[0], c0:c0 + shape[1]]


def built_up_road_cells(shape, transform):
    return np.argwhere((crop(LANDCOVER, shape, transform) == 50) & (crop(ROADS, shape, transform) == 1))


def check(run):
    with rasterio.open(run / 'max_depth.tif') as f:
        depth, transform = f.read(1), f.transform
    full = depth
    depth = np.where(crop(ROADS, depth.shape, transform) == 1, depth, 0.0)  # score road cells only
    points = [p for p in csv.DictReader(open(POINTS, encoding='utf-8')) if p['lat']]
    rows = []
    for p in points:
        x, y = TO_UTM.transform(float(p['lon']), float(p['lat']))
        rows.append({'id': p['id'], 'location': p['location'], 'severity': p['severity'],
                     'max_depth_m': round(neighbourhood_max(depth, transform, x, y), 2)})
    with open(run / 'points.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    rng = np.random.default_rng(42)
    cells = built_up_road_cells(depth.shape, transform)
    sample = cells[rng.choice(len(cells), 2000, replace=False)]
    ref = [neighbourhood_max(depth, transform, *(transform * (c + 0.5, r + 0.5))) for r, c in sample]
    hit = {t: sum(r['max_depth_m'] >= t for r in rows) for t in THRESHOLDS}
    base = {t: float(np.mean(np.array(ref) >= t)) for t in THRESHOLDS}
    return rows, hit, base, full, transform


def draw(run, depth, transform, rows):
    fig, axes = plt.subplots(1, 2, figsize=(13, 9), gridspec_kw={'width_ratios': [1, 1.4]})
    extent = [transform.c, transform.c + transform.a * depth.shape[1],
              transform.f + transform.e * depth.shape[0], transform.f]
    shown = np.ma.masked_less(depth, 0.05)
    points = [p for p in csv.DictReader(open(POINTS, encoding='utf-8')) if p['lat']]
    xy = [TO_UTM.transform(float(p['lon']), float(p['lat'])) for p in points]
    for ax, zoom in zip(axes, [None, (7.80, 7.92, 98.29, 98.41)]):
        ax.set_facecolor('#dfe7ee')
        im = ax.imshow(shown, extent=extent, cmap='Blues', vmin=0.05, vmax=1.0, interpolation='nearest')
        ax.scatter([p[0] for p in xy], [p[1] for p in xy], s=40, facecolor='none', edgecolor='#d62728', lw=1.5,
                   label='จุดน้ำท่วมจากข่าว 29 ต.ค. 2569')
        if zoom:
            (x0, y0), (x1, y1) = TO_UTM.transform(zoom[2], zoom[0]), TO_UTM.transform(zoom[3], zoom[1])
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            for (x, y), p in zip(xy, points):
                ax.annotate(p['id'], (x, y), xytext=(4, 4), textcoords='offset points', fontsize=8, color='#d62728')
        ax.set_xticks([])
        ax.set_yticks([])
    axes[0].legend(loc='lower left', fontsize=9, prop={'family': 'Thonburi'})
    cb = fig.colorbar(im, ax=axes, shrink=0.6)
    cb.set_label('ความลึกน้ำสูงสุด (ม.)', fontfamily='Thonburi')
    fig.suptitle(f'{run.name}: ความลึกน้ำสูงสุด (แสดงเฉพาะ ≥ 5 ซม.)', fontfamily='Thonburi')
    path = ROOT / 'docs' / 'img' / f'step6-max-depth-{run.name}.png'
    fig.savefig(path, dpi=130, bbox_inches='tight')
    return path


def main(runs):
    lines = ['# ตรวจผลแบบจำลองน้ำท่วมกับจุดที่ข่าวรายงาน (ขั้นที่ 6)', '',
             f'คะแนนของแต่ละจุด = ความลึกสูงสุดที่แบบจำลองให้ในรัศมี {RADIUS:g} ม. (เฉพาะเซลล์ถนน, พิกัดจากชื่อสถานที่ คลาดเคลื่อนได้) '
             'เทียบกับถนนในพื้นที่อาคารสุ่ม 2,000 จุด ใช้ตรวจเชิงคุณภาพเท่านั้น', '']
    for run in map(Path, runs):
        s = json.loads((run / 'summary.json').read_text())
        rows, hit, base, depth, transform = check(run)
        img = draw(run, depth, transform, rows)
        lines += [f'## {run.name}', '',
                  f"ฝนรวม {s['rain_total_mm']:.0f} มม. ใน {s['hours']} ชม. · ระบาย {s['drainage_mm_h']:g} มม./ชม. · "
                  f"กลุ่มดิน {s['soil_group']} · พื้นที่น้ำลึกสูงสุด > 0.1 ม. {s['area_max_gt_0.1m_km2']:.1f} ตร.กม., "
                  f"> 0.3 ม. {s['area_max_gt_0.3m_km2']:.1f} ตร.กม.", '',
                  '| เกณฑ์ | จุดจากข่าวที่แบบจำลองท่วม | ถนนสุ่มที่แบบจำลองท่วม |', '|---|---|---|']
        for t in THRESHOLDS:
            lines.append(f'| ≥ {t:g} ม. | {hit[t]}/{len(rows)} ({100 * hit[t] / len(rows):.0f}%) | {100 * base[t]:.0f}% |')
        lines += ['', '| จุด | สถานที่ | ข่าวรายงาน | ความลึกสูงสุดในแบบจำลอง (ม.) |', '|---|---|---|---|']
        lines += [f"| {r['id']} | {r['location']} | {r['severity']} | {r['max_depth_m']:.2f} |" for r in rows]
        lines += ['', f'![max depth](img/{img.name})', '']
        print(run.name, hit, {k: round(v, 2) for k, v in base.items()})
    (ROOT / 'docs' / 'flood-check.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
