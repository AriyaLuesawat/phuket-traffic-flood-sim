"""Step 10/11 figures for the manuscript, from results already on disk (no new runs).

    .venv/bin/python scripts/make_figures.py

  fig1-workflow.png      method overview
  fig2-count-stations.png  count stations on the main roads (data/processed/count_stations.csv)
  fig3-max-depth.png     modelled maximum depth and the 14 reported places (step 6 main run)
  fig4-scenarios.png     network speed per scenario, one panel per period, 5 seeds + mean (output/scenarios/runs.csv)
  fig5-sensitivity.png   speed and trip time change, base -> test value per assumption (output/sensitivity, step 7)
Outputs: docs/img/. Colours: blue = rain only / test value, orange = water on roads; checked with the dataviz
palette validator (both pass light-surface checks). Thai labels use TH Sarabun New from ~/Library/Fonts.
"""
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
IMG = ROOT / 'docs' / 'img'
BLUE, ORANGE, INK, MUTED, GRID = '#2a78d6', '#eb6834', '#1f1f1e', '#6b6a64', '#e4e3df'

FONT = Path.home() / 'Library' / 'Fonts' / 'THSarabunNew.ttf'
font_manager.fontManager.addfont(str(FONT))
font_manager.fontManager.addfont(str(FONT.with_name('THSarabunNew Bold.ttf')))
plt.rcParams.update({'font.family': ['TH Sarabun New', 'DejaVu Sans'], 'font.size': 15, 'axes.edgecolor': MUTED,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': INK, 'text.color': INK,
                     'axes.spines.top': False, 'axes.spines.right': False, 'savefig.dpi': 200})

PERIODS = [('night', '03:00'), ('morning_peak', '08:00'), ('late_morning', '10:00'),
           ('midday', '12:00'), ('evening_peak', '17:00'), ('evening', '20:00')]
SCENARIOS = [('dry', 'ไม่มีฝน'), ('light', 'ฝนเล็กน้อย'), ('medium', 'ฝนปานกลาง'), ('heavy', 'ฝนหนัก'),
             ('heavy_reports', 'ฝนหนัก + น้ำจุดข่าว'), ('heavy_flood', 'ฝนหนัก + น้ำแบบจำลอง')]


def fig_workflow():
    steps = ['ข้อมูลเปิด\nOSM, AADT, ERA5, FABDEM', 'โครงข่ายถนน\n(OSM → SUMO)', 'ปริมาณรถ\n(ปรับเทียบ GEH)',
             'ผลของฝน\n(HCM 2010, SHRP 2-L08)', 'แบบจำลองน้ำท่วม\n(FABDEM 30 ม.)', 'เชื่อมน้ำกับจราจร\n(TraCI, Pregnolato)',
             'สถานการณ์จำลอง\n(180 รอบ)', 'ตรวจสอบและ\nทดสอบความไว', 'หน้าแสดงผล 2D/3D']
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.set_axis_off()
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 2.2)
    w, h = 0.88, 0.62
    pos = [(i + 0.5, 1.6) for i in range(5)] + [(4.5 - i, 0.55) for i in range(4)]
    for i, (text, (x, y)) in enumerate(zip(steps, pos)):
        flood = i in (4, 5)
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle='round,pad=0,rounding_size=0.06',
                                    fc='#fff4ef' if flood else '#eef4fc', ec=ORANGE if flood else BLUE, lw=1.4))
        ax.text(x, y, text, ha='center', va='center', fontsize=14, linespacing=1.0)
        if i < len(steps) - 1:
            nx, ny = pos[i + 1]
            if ny == y:
                d = 1 if nx > x else -1
                start, end = (x + d * w / 2, y), (nx - d * w / 2, ny)
            else:
                start, end = (x, y - h / 2), (nx, ny + h / 2)
            ax.annotate('', end, start, arrowprops=dict(arrowstyle='-|>', color=MUTED, lw=1.2))
    fig.tight_layout()
    fig.savefig(IMG / 'fig1-workflow.png')
    plt.close(fig)


def fig_counts():
    import sumolib
    from matplotlib.collections import LineCollection
    net = sumolib.net.readNet(str(ROOT / 'network' / 'phuket.net.xml'))
    fig, ax = plt.subplots(figsize=(6.2, 11))
    shapes = [e.getShape() for e in net.getEdges() if e.getPriority() >= 7 or e.getType().endswith(('primary', 'secondary'))]
    ax.add_collection(LineCollection(shapes, colors='#c9c8c2', linewidths=0.6))
    with open(ROOT / 'data' / 'processed' / 'count_stations.csv', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for s in rows:
        x, y = net.convertLonLat2XY(float(s['lon']), float(s['lat']))
        total = sum(int(s[k]) for k in ('car', 'bus', 'truck', 'motorcycle'))
        doh = s['source'].startswith('กรมทางหลวง 2')
        ax.scatter(x, y, s=14 + total / 700, color=ORANGE if doh else BLUE, alpha=0.8, edgecolor='white', lw=1, zorder=5)
        ax.annotate(s['ref'], (x, y), fontsize=11, xytext=(4, 2), textcoords='offset points', color=INK)
    ax.scatter([], [], color=ORANGE, label='กรมทางหลวง (AADT 2562)')
    ax.scatter([], [], color=BLUE, label='กรมทางหลวงชนบท (AADT 2569)')
    ax.autoscale()
    ax.set_aspect('equal')
    ax.set_axis_off()
    ax.legend(loc='lower right', frameon=False, title='ขนาดจุด = AADT รวมรถจักรยานยนต์', title_fontsize=13)
    fig.tight_layout()
    fig.savefig(IMG / 'fig2-count-stations.png')
    plt.close(fig)


def fig_flood():
    import numpy as np
    import rasterio
    from pyproj import Transformer
    with rasterio.open(ROOT / 'output' / 'flood' / 'oct2569_drain80_soilC_dem_fabdem_conditioned_roads_78h' / 'max_depth.tif') as f:
        depth, t = f.read(1), f.transform
    extent = [t.c, t.c + t.a * depth.shape[1], t.f + t.e * depth.shape[0], t.f]
    to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32647', always_xy=True)
    with open(ROOT / 'data' / 'validation' / 'flood-reports-2569-10-29.csv', encoding='utf-8') as f:
        points = [p for p in csv.DictReader(f) if p['lat']]
    xy = [to_utm.transform(float(p['lon']), float(p['lat'])) for p in points]
    fig, axes = plt.subplots(1, 2, figsize=(11, 7.4), gridspec_kw={'width_ratios': [1, 1.4]})
    for ax, zoom in zip(axes, [None, (7.80, 7.92, 98.29, 98.41)]):
        ax.set_facecolor('#eceae4')
        im = ax.imshow(np.ma.masked_less(depth, 0.05), extent=extent, cmap='Blues', vmin=0.05, vmax=1.0,
                       interpolation='nearest')
        ax.scatter([p[0] for p in xy], [p[1] for p in xy], s=46, facecolor='none', edgecolor=ORANGE, lw=1.8,
                   label='จุดน้ำท่วมจากข่าว 29 ต.ค. 2569')
        if zoom:
            (x0, y0), (x1, y1) = to_utm.transform(zoom[2], zoom[0]), to_utm.transform(zoom[3], zoom[1])
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            for (x, y), p in zip(xy, points):
                ax.annotate(p['id'], (x, y), xytext=(5, 4), textcoords='offset points', fontsize=12, color=INK)
            ax.set_title('ตัวเมืองและฉลอง', fontsize=15, loc='left')
        else:
            ax.set_title('ทั้งเกาะ', fontsize=15, loc='left')
        ax.set_xticks([])
        ax.set_yticks([])
    axes[0].legend(loc='lower left', fontsize=13)
    cb = fig.colorbar(im, ax=axes, shrink=0.6)
    cb.set_label('ความลึกน้ำสูงสุด (ม.) แสดงเฉพาะ ≥ 0.05 ม.')
    fig.savefig(IMG / 'fig3-max-depth.png', bbox_inches='tight')
    plt.close(fig)


def fig_scenarios():
    runs = defaultdict(list)
    with open(ROOT / 'output' / 'scenarios' / 'runs.csv') as f:
        for r in csv.DictReader(f):
            runs[r['period'], r['scenario']].append(float(r['speed_kmh']))
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.6), sharex=True, sharey=True)
    ys = range(len(SCENARIOS))[::-1]
    for ax, (period, hour) in zip(axes.flat, PERIODS):
        dry = statistics.mean(runs[period, 'dry'])
        ax.axvline(dry, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=1)
        for y, (sc, _) in zip(ys, SCENARIOS):
            v = runs[period, sc]
            c = ORANGE if sc.startswith('heavy_') else BLUE
            ax.scatter(v, [y] * len(v), s=22, color=c, alpha=0.45, lw=0, zorder=2)
            m = statistics.mean(v)
            ax.scatter([m], [y], s=90, marker='|', color=c, lw=2.4, zorder=3)
            if sc != 'dry':
                ax.text(2, y, f'{100 * (m / dry - 1):+.0f}%', fontsize=13, color=MUTED, va='center')
        ax.set_title(f'ชั่วโมงศึกษา {hour} น.', fontsize=16, loc='left')
        ax.set_yticks(list(ys), [s[1] for s in SCENARIOS])
        ax.set_xlim(0, 85)
        ax.grid(axis='x', color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    for ax in axes[1]:
        ax.set_xlabel('ความเร็วเฉลี่ยของโครงข่าย (กม./ชม.)')
    fig.text(0.01, 0.005, 'จุดจาง = แต่ละ seed (5 seed) · ขีด = ค่าเฉลี่ย · เส้นประ = ค่าเฉลี่ยวันไม่มีฝน · '
             'ตัวเลข = เปลี่ยนเทียบวันไม่มีฝน · สีส้ม = มีน้ำบนถนน', fontsize=13, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(IMG / 'fig4-scenarios.png')
    plt.close(fig)


def fig_sensitivity():
    from run_flood_traffic import folder
    from run_rain import SEEDS
    from sensitivity import CASES, DATE, OUT, PERIOD, STEP7_RAIN, mean
    rows = [  # (label, case or folder, base, reference)
        ('รัศมีน้ำจุดข่าว 100 → 50 ม.', 'radius_50'),
        ('รัศมีน้ำจุดข่าว 100 → 200 ม.', 'radius_200'),
        ('ความลึกน้ำจุดข่าว 0.3 → 0.1 ม.', None),
        ('ความเร็วต่ำสุดในน้ำ 2.1 → 5 กม./ชม. (น้ำจุดข่าว)', 'minspeed_5_reports'),
        ('ความเร็วต่ำสุดในน้ำ 2.1 → 10 กม./ชม. (น้ำจุดข่าว)', 'minspeed_10_reports'),
        ('ความเร็วต่ำสุดในน้ำ 2.1 → 5 กม./ชม. (น้ำแบบจำลอง)', 'minspeed_5_model'),
        ('ความเร็วต่ำสุดในน้ำ 2.1 → 10 กม./ชม. (น้ำแบบจำลอง)', 'minspeed_10_model'),
        ('ตัวคูณความจุฝนหนัก 0.86 → 0.823', 'capacity_low'),
        ('ตัวคูณความจุฝนหนัก 0.86 → 0.893', 'capacity_high'),
    ]
    data = []
    for label, case in rows:
        if case:
            _, _, base, ref, _ = CASES[case]
            test = OUT / case
        else:  # step 7 run with 0.1 m at the reported places
            base, ref = folder(PERIOD, DATE, 'reports_d300') / 'flood', STEP7_RAIN
            test = folder(PERIOD, DATE, 'reports_d100') / 'flood'
        out = []
        for key in ('speed_kmh', 'duration_s'):
            r, b, t = (mean([x / f'seed{s}' for s in SEEDS], key) for x in (ref, base, test))
            out.append((100 * (b / r - 1), 100 * (t / r - 1)))
        data.append((label, out))
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6), sharey=True)
    ys = range(len(data))[::-1]
    for ax, k, title in ((axes[0], 0, 'ความเร็วเฉลี่ยเปลี่ยน (%)'), (axes[1], 1, 'เวลาเดินทางเปลี่ยน (%)')):
        for y, (_, out) in zip(ys, data):
            b, t = out[k]
            ax.annotate('', (t, y), (b, y), arrowprops=dict(arrowstyle='-|>', color=BLUE, lw=1.6, shrinkA=5, shrinkB=4))
            ax.scatter([b], [y], s=60, facecolor='white', edgecolor=MUTED, lw=1.6, zorder=3)
            ax.scatter([t], [y], s=60, color=BLUE, zorder=3)
            ax.text(t, y + 0.3, f'{t:+.1f}', ha='center', fontsize=12, color=INK)
        ax.axvline(0, color=MUTED, lw=1)
        ax.set_title(title, fontsize=16, loc='left')
        ax.grid(axis='x', color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].set_xlim(-55, 5)
    axes[1].set_xlim(-2, 50)
    axes[0].set_yticks(list(ys), [d[0] for d in data])
    fig.text(0.01, 0.01, 'วงกลมขาว = ค่าฐาน · จุดน้ำเงิน = ค่าทดสอบ · เทียบฝนอย่างเดียว (กรณีน้ำ) หรือวันไม่มีฝน (กรณีความจุ) · '
             'ช่วงเร่งด่วนเช้า 29 ต.ค. 2569 เฉลี่ย 5 seed', fontsize=13, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(IMG / 'fig5-sensitivity.png')
    plt.close(fig)
    for label, out in data:
        print(f'{label}: speed {out[0][0]:+.1f} -> {out[0][1]:+.1f}, trip {out[1][0]:+.1f} -> {out[1][1]:+.1f}')


if __name__ == '__main__':
    fig_workflow()
    fig_counts()
    fig_flood()
    fig_scenarios()
    fig_sensitivity()
