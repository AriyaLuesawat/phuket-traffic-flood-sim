"""Step 3 check: summarises network/phuket.net.xml and OSM tag coverage, draws docs/img/step3-network.png.

    .venv/bin/python scripts/check_network.py
"""
import collections
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sumolib
from matplotlib.collections import LineCollection

ROOT = Path(__file__).resolve().parent.parent
net = sumolib.net.readNet(str(ROOT / 'network' / 'phuket.net.xml'), withInternal=False)
edges = [e for e in net.getEdges() if e.allows('passenger')]

# Largest strongly connected component: vehicles can only make round trips inside it.
adj = {e.getID(): [o.getID() for o in e.getOutgoing()] for e in edges}
radj = collections.defaultdict(list)
for a, outs in adj.items():
    for b in outs:
        radj[b].append(a)
order, seen = [], set()
for start in adj:  # iterative Kosaraju
    if start in seen:
        continue
    stack = [(start, iter(adj[start]))]
    seen.add(start)
    while stack:
        node, it = stack[-1]
        nxt = next((n for n in it if n not in seen and n in adj), None)
        if nxt is None:
            order.append(node)
            stack.pop()
        else:
            seen.add(nxt)
            stack.append((nxt, iter(adj[nxt])))
comp, sizes = {}, []
for start in reversed(order):
    if start in comp:
        continue
    stack, members = [start], 0
    comp[start] = len(sizes)
    while stack:
        node = stack.pop()
        members += 1
        for p in radj[node]:
            if p not in comp:
                comp[p] = len(sizes)
                stack.append(p)
    sizes.append(members)
main = max(range(len(sizes)), key=sizes.__getitem__)

by_type = collections.defaultdict(lambda: [0, 0.0, 0.0])
for e in edges:
    t = e.getType().replace('highway.', '')
    by_type[t][0] += 1
    by_type[t][1] += e.getLength() / 1000
    by_type[t][2] += e.getLength() * e.getLaneNumber() / 1000
km = sum(e.getLength() for e in edges) / 1000
main_km = sum(e.getLength() for e in edges if comp[e.getID()] == main) / 1000

# OSM tag coverage: how many road ways state lanes / maxspeed themselves rather than using defaults.
lines = subprocess.run(['osmium', 'export', str(ROOT / 'data' / 'processed' / 'phuket-roads.osm'),
                        '--geometry-types=linestring', '-f', 'geojsonseq'], capture_output=True, text=True).stdout
ways = [json.loads(l.lstrip('\x1e')) for l in lines.splitlines() if l.strip()]
tagged = collections.defaultdict(lambda: [0, 0, 0])
for w in ways:
    p = w['properties']
    t = p.get('highway', '?')
    tagged[t][0] += 1
    tagged[t][1] += 'lanes' in p
    tagged[t][2] += 'maxspeed' in p

order_types = ['trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary',
               'tertiary_link', 'unclassified', 'residential', 'living_street']
rows = ['| ประเภทถนน | edges | ความยาว (กม.) | ความยาวช่องจราจร (กม.) | OSM ways | ระบุจำนวนช่อง | ระบุความเร็วจำกัด |',
        '|---|---|---|---|---|---|---|']
for t in order_types + sorted(set(by_type) - set(order_types)):
    if t not in by_type:
        continue
    n, length, lane_km = by_type[t]
    w = tagged.get(t, [0, 0, 0])
    pct = lambda k: f'{100 * w[k] / w[0]:.0f}%' if w[0] else '–'
    rows.append(f'| {t} | {n:,} | {length:,.0f} | {lane_km:,.0f} | {w[0]:,} | {pct(1)} | {pct(2)} |')

tls = len(net.getTrafficLights())
report = f"""# รายงานโครงข่ายถนน (ขั้นที่ 3)

สร้างด้วย `scripts/build_network.py` ตรวจด้วย `scripts/check_network.py`

- ถนนที่รถยนต์วิ่งได้: {len(edges):,} edges ยาวรวม {km:,.0f} กม.
- ทางแยก: {len(net.getNodes()):,} จุด, สัญญาณไฟจราจร {tls} จุด (จากแท็ก `highway=traffic_signals` ใน OSM)
- กลุ่มที่เชื่อมถึงกันได้ทุกทิศ (strongly connected) ที่ใหญ่ที่สุด: {sizes[main]:,} edges ({100 * sizes[main] / len(edges):.1f}%), {main_km:,.0f} กม.
  ส่วนที่เหลือ {len(sizes) - 1:,} กลุ่มเล็ก ส่วนใหญ่เป็นซอยตันหรือถนนทางเดียวที่ข้อมูล OSM ต่อไม่ถึงกัน รถจะไม่ถูกสร้างใน edges เหล่านี้

{chr(10).join(rows)}

ถนนที่ OSM ไม่ระบุจำนวนช่องหรือความเร็ว ใช้ค่าเริ่มต้นตามประเภทถนนจาก `osmNetconvert.typ.xml` ของ SUMO ต้องระบุเป็นข้อจำกัดในงานวิจัย
"""
(ROOT / 'docs' / 'network-report.md').write_text(report)
print(report)

colors = {'trunk': '#c0392b', 'trunk_link': '#c0392b', 'primary': '#e67e22', 'primary_link': '#e67e22',
          'secondary': '#f1c40f', 'secondary_link': '#f1c40f', 'tertiary': '#2980b9', 'tertiary_link': '#2980b9'}
fig, ax = plt.subplots(figsize=(7, 13))
segs, cols, widths = [], [], []
for e in sorted(edges, key=lambda e: e.getType() in [f'highway.{k}' for k in colors]):
    t = e.getType().replace('highway.', '')
    segs.append(e.getShape())
    cols.append('#cc33cc' if comp[e.getID()] != main else colors.get(t, '#999999'))
    widths.append(1.4 if t in colors else 0.25)
ax.add_collection(LineCollection(segs, colors=cols, linewidths=widths))
xs, ys = zip(*[n.getCoord() for n in net.getNodes() if n.getType() == 'traffic_light'])
ax.scatter(xs, ys, s=10, c='black', zorder=5, label=f'traffic lights ({tls})')
ax.plot([], [], color='#cc33cc', label='outside main connected component')
ax.autoscale(); ax.set_aspect('equal'); ax.legend(loc='lower left'); ax.set_title('Phuket SUMO network')
ax.set_xticks([]); ax.set_yticks([])
fig.tight_layout(); fig.savefig(ROOT / 'docs' / 'img' / 'step3-network.png', dpi=110)
