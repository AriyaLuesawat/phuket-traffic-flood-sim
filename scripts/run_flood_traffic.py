"""Step 7b: runs one traffic period during a flood event, with flood depth applied to the roads through TraCI.

    .venv/bin/python scripts/run_flood_traffic.py morning_peak 2026-10-28
    .venv/bin/python scripts/run_flood_traffic.py morning_peak 2026-10-28 --seeds 1
    .venv/bin/python scripts/run_flood_traffic.py morning_peak 2026-10-29 --cases flood   # reuse the rain runs
    .venv/bin/python scripts/run_flood_traffic.py morning_peak 2026-10-29 --cases flood --flood reports_d300

Two cases per seed, both with the rain of the study hour (step 5 factors) and vehicle rerouting switched on:
  rain   no flood on the roads
  flood  every UPDATE_S seconds each edge gets the depth interpolated between the hourly flood snapshots;
         speed limit = min(original limit, Pregnolato v(w)); no road is closed (see road_flood_depth.py), so
         vehicles avoid flooded roads only because they are slow, and the original limit returns when the
         water drops
Rerouting: a share REROUTE_P of the vehicles gets a rerouting device (SUMO), period REROUTE_S, routing on
current travel times. Every vehicle (share 1) moved a third of the traffic off the counted main roads (GEH
< 5 at 23-30% of stations); 20% kept GEH < 5 at 92-96% (docs/step5-method.md, section 5).
Avoiding standing water (flood case): every vehicle whose remaining route (after its current edge) uses an
'avoid' edge (depth >= AVOID_MM) gets a rerouting device too, checked at every flood update and one step
after it departs; the device then reroutes it like the 20% (ASSUMPTION: drivers learn of standing water
ahead, e.g. from news or seeing it, and take a detour; with only the 20% share, 80% of the vehicles drove
through 2.1 km/h roads and the network jammed). Rerouting such vehicles directly with
traci.vehicle.rerouteTraveltime crashed SUMO 1.28 meso (segmentation fault, reproducible at the same vehicle
and step), so the device is added at run time instead (vehicle parameter has.rerouting.device).
Edge depths come from scripts/road_flood_depth.py.

Outputs: output/flood_traffic/<period>_<date>/<case>/seed<N>/..., docs/flood-traffic-<period>-<date>.md
"""
import argparse
import csv
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import traci

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_demand import PERIODS, WARMUP  # noqa: E402
from road_flood_depth import AVOID_MM, OUT, RUN, pregnolato_kmh  # noqa: E402
from run_baseline import sumo_cmd  # noqa: E402
from run_rain import MESO_TAU, finished, metrics, rain_classes, write_vtypes  # noqa: E402

RAIN = ROOT / 'data' / 'raw' / 'rain' / 'era5_phuket_town_2000_2026.json'
UPDATE_S = 300
REROUTE_S = 300
REROUTE_P = 0.2


def hour_rain_class(start):
    """Rain class of the hour [start, start + 1 h): the value labelled start + 1 h (preceding-hour total)."""
    data = json.loads(RAIN.read_text())['hourly']
    p = data['precipitation'][data['time'].index((start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))] or 0.0
    for c in rain_classes():
        if p >= float(c['min_mm_h']) and (not c['max_mm_h'] or p < float(c['max_mm_h'])):
            return p, c
    raise ValueError(p)


class Flood:
    """Edge depth at any time, interpolated linearly between the hourly snapshots."""

    def __init__(self, name=RUN.name):
        d = np.load(OUT / f'edge_depth_{name}.npz')
        self.edges, self.depth, self.length = list(d['edges']), d['depth_m'], d['length_m']
        self.t0 = datetime.fromisoformat(str(d['times'][0]))

    def at(self, when):
        x = (when - self.t0).total_seconds() / 3600
        i = int(np.clip(np.floor(x), 0, len(self.depth) - 1))
        j = min(i + 1, len(self.depth) - 1)
        f = float(np.clip(x - i, 0, 1))
        return (1 - f) * self.depth[i] + f * self.depth[j]


def run_case(period, date, case, seed, rain=None, flood_at=None, out=None, flood=RUN.name, min_kmh=None):
    """rain: rain class name (default: the class of the study hour on date); flood_at: time in the flood event
    that the start of the study hour maps to (default: the study hour on date); out: output folder;
    flood: edge depth input, edge_depth_<flood>.npz (default: the main flood run of step 6); min_kmh: lowest
    speed limit on a wet road instead of v(AVOID_MM) = 2.1 km/h (sensitivity, step 10)."""
    hour = PERIODS[period]
    start = datetime.fromisoformat(date) + timedelta(hours=hour)
    p, c = hour_rain_class(start)
    if rain:
        p, c = None, next(k for k in rain_classes() if k['class'] == rain)
    shift = flood_at - start if flood_at else timedelta(0)
    out = out or folder(period, date, flood) / case / f'seed{seed}'
    if finished(out) and (out / 'standing_water.json').exists():  # done earlier: read, do not rerun
        return case_row(case, seed, p, c, out)
    out.mkdir(parents=True, exist_ok=True)
    caf = float(c['capacity_factor'])
    extra = [arg for k, v in MESO_TAU.items() for arg in (f'--meso-{k}', f'{v / caf:.4f}')]
    extra += ['--device.rerouting.probability', REROUTE_P, '--device.rerouting.period', REROUTE_S,
              '--device.rerouting.threads', '2', '--seed', seed]
    cmd = sumo_cmd(period, out, write_vtypes(out / 'vtypes.add.xml', float(c['speed_factor'])), extra)
    traci.start(cmd, label=f'{case}{seed}')
    flood = Flood(flood)
    midnight = datetime.fromisoformat(date)
    original = {}  # edge -> original max speed
    avoid_log = []
    avoid = set()  # edges with standing water >= AVOID_MM now
    departed = ()

    informed = set()  # vehicles given a rerouting device because of standing water ahead

    def detour(vehicles):
        n = 0
        for v in vehicles:
            road = traci.vehicle.getRoadID(v)
            if v in informed or not road or road.startswith(':'):  # teleporting or inside a junction
                continue
            if traci.vehicle.getParameter(v, 'has.rerouting.device') == 'true':
                continue
            route = traci.vehicle.getRoute(v)[traci.vehicle.getRouteIndex(v) + 1:]
            if avoid.intersection(route):
                traci.vehicle.setParameter(v, 'has.rerouting.device', 'true')
                informed.add(v)
                n += 1
        return n

    while (now := traci.simulation.getTime()) < (hour + 1) * 3600:
        if case == 'flood' and now % UPDATE_S == 0:
            depth = flood.at(midnight + shift + timedelta(seconds=now))
            vmax = pregnolato_kmh(depth) / 3.6
            if min_kmh:
                vmax = np.maximum(vmax, min_kmh / 3.6)
            avoid_km = 0.0
            for k in np.flatnonzero((depth > 0) | np.isin(flood.edges, list(original))):
                e = flood.edges[k]
                if e not in original:
                    original[e] = traci.lane.getMaxSpeed(f'{e}_0')
                avoid_km += flood.length[k] / 1000 * (depth[k] * 1000 >= AVOID_MM)
                traci.edge.setMaxSpeed(e, min(original[e], vmax[k]) if depth[k] > 0 else original[e])
            avoid = {flood.edges[k] for k in np.flatnonzero(depth * 1000 >= AVOID_MM)}
            avoid_log.append({'time_s': now, 'avoid_km': round(avoid_km, 1), 'avoid_edges': len(avoid),
                              'detoured': detour(traci.vehicle.getIDList())})
        traci.simulationStep()
        if avoid:  # vehicles that departed in the previous step
            running = set(traci.vehicle.getIDList()) if departed else set()
            avoid_log[-1]['detoured'] += detour(v for v in departed if v in running)
        departed = traci.simulation.getDepartedIDList()
    traci.close()
    (out / 'standing_water.json').write_text(json.dumps(avoid_log))
    return case_row(case, seed, p, c, out)


def folder(period, date, flood=RUN.name):
    """Output folder of a period and day; another flood input gets its own folder (the rain case too)."""
    return ROOT / 'output' / 'flood_traffic' / (f'{period}_{date}' + ('' if flood == RUN.name else f'_{flood}'))


def case_row(case, seed, p, c, out):
    """Metrics of one finished run, read from its output files."""
    avoid_log = json.loads((out / 'standing_water.json').read_text())
    m = metrics(out)
    stats = ET.parse(out / 'stats.xml').getroot()
    m['not_inserted'] = int(stats.find('vehicles').get('loaded')) - int(stats.find('vehicles').get('inserted'))
    m['avoid_km'] = float(statistics.mean(r['avoid_km'] for r in avoid_log)) if avoid_log else 0.0
    m['detoured'] = sum(r.get('detoured', 0) for r in avoid_log)
    return {'case': case, 'seed': seed, 'rain_mm': p, 'rain_class': c['class'], **m}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('period', choices=list(PERIODS))
    ap.add_argument('date', help='day of the flood event, e.g. 2026-10-28')
    ap.add_argument('--seeds', type=int, default=5)
    ap.add_argument('--cases', default='rain,flood', help='cases to run; the others are read from earlier runs')
    ap.add_argument('--flood', default=RUN.name, help='edge depth input, e.g. reports_d300 (scripts/reported_flood.py)')
    a = ap.parse_args()
    run = a.cases.split(',')
    jobs = [(a.period, a.date, case, s) for case in run for s in range(1, a.seeds + 1)]
    with ProcessPoolExecutor(5) as pool:
        done = dict(zip(jobs, pool.map(run_case, *zip(*jobs), [None] * len(jobs), [None] * len(jobs),
                                       [None] * len(jobs), [a.flood] * len(jobs))))
    out = folder(a.period, a.date, a.flood)
    p, c = hour_rain_class(datetime.fromisoformat(a.date) + timedelta(hours=PERIODS[a.period]))
    rows = [done.get((a.period, a.date, case, s)) or case_row(case, s, p, c, out / case / f'seed{s}')
            for case in ('rain', 'flood') for s in range(1, a.seeds + 1)]
    with open(out / 'runs.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    hour = PERIODS[a.period]
    keys = ['speed_kmh', 'duration_s', 'timeloss_s', 'trips_done', 'running_end', 'teleports', 'not_inserted',
            'avoid_km', 'detoured']
    mean = {case: {k: statistics.mean(r[k] for r in rows if r['case'] == case) for k in keys}
            for case in ('rain', 'flood')}
    rng = {case: (min(r['speed_kmh'] for r in rows if r['case'] == case),
                  max(r['speed_kmh'] for r in rows if r['case'] == case)) for case in mean}
    r0 = rows[0]
    lines = [f'# ฝนและน้ำท่วมกับการจราจร: {a.period} วันที่ {a.date} (ขั้นที่ 7)', '',
             f"ชั่วโมงศึกษา {hour:02d}:00–{hour + 1:02d}:00 · ฝน {r0['rain_mm']:.1f} มม./ชม. (ระดับ {r0['rain_class']}) · "
             f'{a.seeds} seed ต่อกรณี · ทุกกรณีให้รถ {REROUTE_P:.0%} หาเส้นทางใหม่ทุก {REROUTE_S} วินาที · '
             f'อัปเดตน้ำท่วมทุก {UPDATE_S} วินาที · น้ำบนถนน `edge_depth_{a.flood}.npz` · สร้างโดย `scripts/run_flood_traffic.py`', '',
             '| ตัวชี้วัด | ฝนอย่างเดียว | ฝน + น้ำท่วม | เปลี่ยน |', '|---|---|---|---|']
    labels = {'speed_kmh': 'ความเร็วเฉลี่ยในชั่วโมงศึกษา (กม./ชม.)', 'duration_s': 'เวลาเดินทางเฉลี่ยของเที่ยวที่จบ (นาที)',
              'timeloss_s': 'เวลาที่เสียเฉลี่ย (นาที)', 'trips_done': 'เที่ยวที่จบ', 'running_end': 'รถที่ยังวิ่งตอนจบ',
              'teleports': 'teleport', 'not_inserted': 'รถที่ออกเดินทางไม่ได้', 'avoid_km': 'ถนนน้ำ ≥ 0.3 ม. ควรเลี่ยง เฉลี่ย (กม.)',
              'detoured': 'รถที่ได้รับข้อมูลน้ำขังและเลี่ยง (คัน)'}
    for k in keys:
        x, y = mean['rain'][k], mean['flood'][k]
        div = 60 if k in ('duration_s', 'timeloss_s') else 1
        change = f'{100 * (y / x - 1):+.1f}%' if x else '–'
        lines.append(f'| {labels[k]} | {x / div:,.1f} | {y / div:,.1f} | {change} |')
    lines += ['', f"ช่วงความเร็วของ seed: ฝนอย่างเดียว {rng['rain'][0]:.1f}–{rng['rain'][1]:.1f} · "
              f"ฝน + น้ำท่วม {rng['flood'][0]:.1f}–{rng['flood'][1]:.1f} กม./ชม.", '']
    tag = '' if a.flood == RUN.name else f'-{a.flood}'
    (ROOT / 'docs' / f'flood-traffic-{a.period}-{a.date}{tag}.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
