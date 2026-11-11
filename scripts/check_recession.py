"""Step 7c: checks how fast road flooding drains in each flood run against the reported recession.

    .venv/bin/python scripts/check_recession.py output/flood/<run> [<run> ...]

Reported facts used (29 Oct 2569):
  - morning: about 20 flooded road spots in Chalong, Wichit, Karon, Rawai, Kamala and the town (news, see
    data/validation/flood-reports-2569-10-29.csv), so some road flooding should remain around 08:00;
  - 10:00: the provincial disaster office reported water back to normal in Patong, Rawai, Karon, Chalong,
    Mueang and Thalang (Spacebar, 29 Oct 2569 15:17), so road flooding should be near zero by 10:00.
No road lengths were reported, so 'near zero' is judged against the other runs, not a measured value.

Needs output/flood_traffic/edge_depth_<run>.npz from road_flood_depth.py.
Output: docs/flood-recession.md
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from road_flood_depth import AVOID_MM, OUT  # noqa: E402

TIMES = ['2026-10-28T09:00', '2026-10-29T06:00', '2026-10-29T08:00', '2026-10-29T10:00', '2026-10-29T12:00']


def main(runs):
    lines = ['# น้ำลดเร็วแค่ไหน เทียบกับรายงานวันที่ 29 ต.ค. 2569 (ขั้นที่ 7)', '',
             'ความยาวถนนที่มีน้ำ (กม.) ณ เวลาต่าง ๆ · ≥ 0.1 ม. / ≥ 0.3 ม. (ควรเลี่ยง) · '
             'รายงาน: เช้า 29 ต.ค. น้ำท่วมราว 20 จุด, 10:00 น้ำกลับเป็นปกติ (ปภ.ภูเก็ต) · '
             'สร้างโดย `scripts/check_recession.py`', '',
             '| แบบ | ระบาย (มม./ชม.) | ' + ' | '.join(t[5:].replace('T', ' ') for t in TIMES) + ' |',
             '|---|---|' + '---|' * len(TIMES)]
    for run in map(Path, runs):
        s = json.loads((run / 'summary.json').read_text())
        d = np.load(OUT / f'edge_depth_{run.name}.npz')
        times, depth, length = list(d['times']), d['depth_m'], d['length_m']
        cells = []
        for t in TIMES:
            if t not in times:
                cells.append('–')
                continue
            w = depth[times.index(t)]
            cells.append(f'{length[w >= 0.1].sum() / 1000:.0f} / {length[w >= AVOID_MM / 1000].sum() / 1000:.0f}')
        lines.append(f"| {run.name} | {s['drainage_mm_h']:g}{' + ถนน' if s.get('drain_roads') else ''} | "
                     + ' | '.join(cells) + ' |')
    (ROOT / 'docs' / 'flood-recession.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main(sys.argv[1:])
