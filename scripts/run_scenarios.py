"""Step 8: every period x rain scenario, summarised in one table.

    .venv/bin/python scripts/run_rain.py --reroute 0.2 --classes dry,light,medium,heavy   # rain-only scenarios
    .venv/bin/python scripts/run_scenarios.py run                  # 'heavy + flood' scenario, every period
    .venv/bin/python scripts/run_scenarios.py run morning_peak
    .venv/bin/python scripts/run_scenarios.py run --scenario heavy_reports   # water at the reported places
    .venv/bin/python scripts/run_scenarios.py summary              # docs/scenarios.md from finished runs

Scenarios (5 seeds each, 20% of vehicles rerouting as in steps 5 and 7):
  dry, light, medium, heavy   steady rain of the class on the whole island, no water on the roads
                              (output/rain_reroute_p20/<period>/<class>/, from run_rain.py)
  heavy_flood                 heavy-rain factors plus the water on the roads of the 29 Oct 2569 event at
                              08:00-09:00 (the hour of step 7), whatever the period: the study hour of every
                              period maps to that flood state so that only the traffic demand differs
                              (ASSUMPTION: the same flood at another time of day); vehicles that meet standing
                              water detour as in step 7 (output/scenarios/<period>/heavy_flood/)
  heavy_reports               as heavy_flood, but water (0.3 m) only on the roads at the 14 places the news
                              reported (scripts/reported_flood.py, 17 km of road instead of 126 km): the lower
                              bound of the flood extent, heavy_flood the upper (output/scenarios/<period>/heavy_reports/)
Measures, beyond those of step 7:
  congested_km  road length whose mean speed in the study hour is below CONGESTED_KMH (our definition of a
                queue, since the mesoscopic model has no queue output)
  breakdowns    runs whose network speed is below BREAKDOWN of the dry mean of the same period (our
                definition of a run that jammed)
"""
import csv
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_demand import PERIODS  # noqa: E402
from run_baseline import NET  # noqa: E402
from road_flood_depth import RUN  # noqa: E402
from run_flood_traffic import case_row, run_case  # noqa: E402
from run_rain import SEEDS, finished, metrics, rain_classes  # noqa: E402

RAIN_DIR = ROOT / 'output' / 'rain_reroute_p20'
OUT = ROOT / 'output' / 'scenarios'
FLOOD_DATE = '2026-10-29'
FLOOD_AT = datetime(2026, 10, 29, 8)
FLOODS = {'heavy_flood': RUN.name, 'heavy_reports': 'reports_d300'}  # scenario -> edge depth input
SCENARIOS = ['dry', 'light', 'medium', 'heavy', *FLOODS]
CONGESTED_KMH = 10
BREAKDOWN = 0.8


def flood_dir(period, seed, scenario='heavy_flood'):
    return OUT / period / scenario / f'seed{seed}'


def run_flood(period, seed, scenario='heavy_flood'):
    out = flood_dir(period, seed, scenario)
    if finished(out) and (out / 'standing_water.json').exists():
        return
    run_case(period, FLOOD_DATE, 'flood', seed, rain='heavy', flood_at=FLOOD_AT, out=out, flood=FLOODS[scenario])
    print(period, scenario, seed, 'done', flush=True)


def edge_lengths():
    cache = OUT / 'edge_length_m.json'
    if not cache.exists():
        import sumolib
        net = sumolib.net.readNet(str(NET))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({e.getID(): e.getLength() for e in net.getEdges()}))
    return json.loads(cache.read_text())


def congested_km(out, length):
    return sum(length.get(e.get('id'), 0) for e in ET.parse(out / 'edgedata.xml').getroot().iter('edge')
               if float(e.get('sampledSeconds', 0)) > 0 and float(e.get('speed', 99)) * 3.6 < CONGESTED_KMH) / 1000


def run_row(period, scenario, seed, length):
    if scenario in FLOODS:
        out = flood_dir(period, seed, scenario)
        c = next(k for k in rain_classes() if k['class'] == 'heavy')
        m = case_row('flood', seed, None, c, out)
    else:
        out = RAIN_DIR / period / scenario / f'seed{seed}'
        m = {**metrics(out), 'avoid_km': 0.0, 'detoured': 0}
    keep = ['speed_kmh', 'duration_s', 'timeloss_s', 'trips_done', 'running_end', 'teleports', 'avoid_km',
            'detoured']
    return {'period': period, 'scenario': scenario, 'seed': seed, **{k: m[k] for k in keep},
            'congested_km': congested_km(out, length)}


def summary(periods):
    length = edge_lengths()
    rows, missing = [], []
    for period in periods:
        for sc in SCENARIOS:
            for s in SEEDS:
                d = flood_dir(period, s, sc) if sc in FLOODS else RAIN_DIR / period / sc / f'seed{s}'
                if finished(d) and (sc not in FLOODS or (d / 'standing_water.json').exists()):
                    rows.append(run_row(period, sc, s, length))
                else:  # not run yet, still running, or stopped part-way
                    missing.append(f'{period}/{sc}/seed{s}')
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / 'runs.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    names = {'dry': 'ไม่มีฝน', 'light': 'ฝนเล็กน้อย', 'medium': 'ฝนปานกลาง', 'heavy': 'ฝนหนัก',
             'heavy_flood': 'ฝนหนัก + น้ำบนถนน (แบบจำลอง)', 'heavy_reports': 'ฝนหนัก + น้ำจุดข่าว'}
    lines = ['# สถานการณ์จำลอง: ช่วงเวลา × ระดับฝน (ขั้นที่ 8)', '',
             f'แต่ละกรณีรัน {len(SEEDS)} seed ทุกกรณีให้รถ 20% หาเส้นทางใหม่ทุก 300 วินาที '
             f'"ฝนหนัก + น้ำบนถนน" ใช้น้ำบนถนนของเหตุการณ์ 29 ต.ค. 2569 เวลา 08:00–09:00 กับทุกช่วงเวลา '
             'และให้รถที่เจอน้ำขังข้างหน้าเลี่ยง (เหมือนขั้นที่ 7) "ฝนหนัก + น้ำจุดข่าว" ใช้น้ำ 0.3 ม. เฉพาะถนนรอบ 14 จุดที่ข่าวรายงาน '
             '(`docs/reported-flood.md`) เวลาเดียวกัน สร้างโดย `scripts/run_scenarios.py`', '',
             f'- ความเร็ว: ค่าเฉลี่ยของ seed (ต่ำสุด–สูงสุด) · เปลี่ยน: เทียบกับไม่มีฝนของช่วงเวลาเดียวกัน',
             f'- ถนนรถติด: ความยาวถนนที่ความเร็วเฉลี่ยในชั่วโมงศึกษาต่ำกว่า {CONGESTED_KMH} กม./ชม. (นิยามของงานนี้ ใช้แทนความยาวแถวคอย)',
             f'- รอบที่รถติดสะสม: จำนวน seed ที่ความเร็วต่ำกว่า {BREAKDOWN:.0%} ของค่าเฉลี่ยไม่มีฝนของช่วงเวลาเดียวกัน (นิยามของงานนี้)',
             '- ถนนที่ควรเลี่ยง: น้ำ ≥ 0.3 ม. (ไม่ปิดถนน) เฉลี่ยตลอดชั่วโมงจำลอง', '',
             '| ช่วงเวลา | สถานการณ์ | ความเร็ว (กม./ชม.) | เปลี่ยน | เวลาเดินทาง (นาที) | เปลี่ยน | ถนนรถติด (กม.) | '
             'ถนนที่ควรเลี่ยง (กม.) | รถค้างตอนจบ | teleport | รอบที่รถติดสะสม |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for period in periods:
        base = [r for r in rows if r['period'] == period and r['scenario'] == 'dry']
        b_speed = statistics.mean(r['speed_kmh'] for r in base) if base else None
        b_dur = statistics.mean(r['duration_s'] for r in base) if base else None
        for sc in SCENARIOS:
            rs = [r for r in rows if r['period'] == period and r['scenario'] == sc]
            if not rs:
                continue
            m = {k: statistics.mean(r[k] for r in rs) for k in ('speed_kmh', 'duration_s', 'congested_km',
                                                               'avoid_km', 'running_end', 'teleports')}
            sp = [r['speed_kmh'] for r in rs]
            ch = f"{100 * (m['speed_kmh'] / b_speed - 1):+.1f}%" if b_speed else '–'
            chd = f"{100 * (m['duration_s'] / b_dur - 1):+.1f}%" if b_dur else '–'
            bd = f"{sum(x < BREAKDOWN * b_speed for x in sp)}/{len(rs)}" if b_speed else '–'
            lines.append(f"| {period} | {names[sc]} | {m['speed_kmh']:.1f} ({min(sp):.1f}–{max(sp):.1f}) | {ch} | "
                         f"{m['duration_s'] / 60:.1f} | {chd} | {m['congested_km']:.1f} | {m['avoid_km']:.1f} | "
                         f"{m['running_end']:,.0f} | {m['teleports']:.0f} | {bd} |")
    if missing:
        lines += ['', f'ยังไม่มีผล {len(missing)} รอบ']
    (ROOT / 'docs' / 'scenarios.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


def main():
    args = sys.argv[1:]
    scenario = 'heavy_flood'
    if '--scenario' in args:
        i = args.index('--scenario')
        scenario = args[i + 1]
        del args[i:i + 2]
    cmd, periods = (args[0] if args else 'summary'), (args[1:] or list(PERIODS))
    if cmd == 'run':
        jobs = [(p, s, scenario) for p in periods for s in SEEDS]
        with ProcessPoolExecutor(5) as pool:
            list(pool.map(run_flood, *zip(*jobs)))
    summary(list(PERIODS))


if __name__ == '__main__':
    main()
