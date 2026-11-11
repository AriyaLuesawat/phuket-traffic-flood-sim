"""Step 4c: runs the no-rain simulation for each period and compares counts with the measured targets.

    .venv/bin/python scripts/run_baseline.py            # all periods with demand built
    .venv/bin/python scripts/run_baseline.py evening_peak
    .venv/bin/python scripts/run_baseline.py --reroute     # same, with vehicle rerouting (as in step 7)
    .venv/bin/python scripts/run_baseline.py --reroute 0.2 morning_peak evening_peak   # 20% of vehicles

Calibration measure: GEH = sqrt(2 (M - C)^2 / (M + C)) per station and direction for the study hour,
M = simulated vehicles, C = target count. GEH < 5 is the usual acceptance level for hourly link counts.

Runs SUMO's mesoscopic model (queues per road segment): the microscopic model gridlocked the whole island at
measured peak-hour volumes even without motorcycles (docs/calibration.md), because junctions imported from
OSM discharge far fewer vehicles than real ones.
--reroute [P] gives a share P (default 1 = every vehicle) of the vehicles SUMO's rerouting device (period
REROUTE_S, current travel times), runs the periods in parallel and writes to output/baseline_reroute[_pNN]/
and docs/calibration-reroute[-pNN].md instead.
Outputs: output/baseline/<period>/..., docs/calibration.md
"""
import csv
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_demand import GROUPS, OUT, PERIODS, WARMUP, hourly_shares  # noqa: E402
DEMAND = OUT.resolve()

NET = ROOT / 'network' / 'phuket.net.xml'
BIN = Path(sys.executable).parent
REROUTE_S = 300
REROUTE = ['--device.rerouting.probability', '1', '--device.rerouting.period', str(REROUTE_S),
           '--device.rerouting.threads', '2', '--seed', '42']


def geh(m, c):
    return math.sqrt(2 * (m - c) ** 2 / (m + c)) if m + c else 0.0


def simulate(period, out=None, vtypes=None, extra=()):
    """Runs one period. out: output folder, vtypes: vType file (default: dry weather), extra: more sumo options."""
    out = out or Path(os.environ.get("BASELINE_DIR", ROOT / "output" / "baseline")).resolve() / period
    subprocess.run(sumo_cmd(period, out, vtypes, extra), check=True, cwd=out)
    return out


def sumo_cmd(period, out, vtypes=None, extra=(), binary='sumo'):
    """The sumo command line of one period run; also used by the TraCI runs of step 7."""
    hour = PERIODS[period]
    begin, end = hour * 3600 - WARMUP, hour * 3600 + 3600
    out.mkdir(parents=True, exist_ok=True)
    # PLAYBACK_S (env): also write edge means every PLAYBACK_S seconds over the whole run, for step 9
    playback = int(os.environ.get('PLAYBACK_S', 0))
    every = (f'<edgeData id="playback" file="edgedata_playback.xml" begin="{begin}" end="{end}" '
             f'period="{playback}" excludeEmpty="true"/>' if playback else '')
    (out / 'edgedata.add.xml').write_text(
        f'<additional><edgeData id="hour" file="edgedata.xml" begin="{hour * 3600}" end="{end}" '
        f'excludeEmpty="true"/>{every}</additional>\n')
    routes = ','.join(str(DEMAND / period / f"{g}.rou.xml") for g in GROUPS)
    return [str(BIN / binary), '-n', str(NET),
            '-a', f'{vtypes or DEMAND / "vtypes.add.xml"},{out / "edgedata.add.xml"}',
            '-r', routes, '-b', str(begin), '-e', str(end),
            '--mesosim', '--meso-overtaking',  # junction control off: it jammed the network further (docs/step4-method.md)
            '--time-to-teleport', '300', '--ignore-route-errors',
            '--statistic-output', str(out / 'stats.xml'),
            '--tripinfo-output', str(out / 'tripinfo.xml'),
            '--no-step-log', '--no-warnings', *map(str, extra or ['--seed', 42])]


def compare(period, out, shares, stations):
    hour = PERIODS[period]
    # vehicles that start on an edge are not 'entered', but routeSampler counts them as passing the edge
    entered = {e.get('id'): float(e.get('entered', 0)) + float(e.get('departed', 0))
               for e in ET.parse(out / 'edgedata.xml').getroot().iter('edge')}
    rows = []
    for s in stations:
        edges = s['edges'].split()
        for edge in edges:
            target = sum(int(s[g]) for g in GROUPS) / len(edges) * shares[hour]
            sim = entered.get(edge, 0.0)
            rows.append({'station': s['id'], 'edge': edge, 'target': round(target), 'simulated': round(sim),
                         'geh': round(geh(sim, target), 2)})
    with open(out / 'calibration.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    stats = ET.parse(out / 'stats.xml').getroot()
    veh, trips, tele = stats.find('vehicles'), stats.find('vehicleTripStatistics'), stats.find('teleports')
    ss = sp = 0.0  # network mean speed in the study hour, weighted by time spent on each edge
    for e in ET.parse(out / 'edgedata.xml').getroot().iter('edge'):
        ss += float(e.get('sampledSeconds', 0))
        sp += float(e.get('sampledSeconds', 0)) * float(e.get('speed', 0))
    ok = sum(r['geh'] < 5 for r in rows)
    return {
        'period': period, 'hour': f'{hour:02d}:00–{hour + 1:02d}:00',
        'vehicles': int(veh.get('loaded')), 'teleports': int(tele.get('total')),
        'speed_kmh': round(sp / ss * 3.6, 1),
        'running_end': int(veh.get('running')),
        'geh_ok': f'{ok}/{len(rows)} ({100 * ok / len(rows):.0f}%)',
        'target_sum': sum(r['target'] for r in rows), 'sim_sum': sum(r['simulated'] for r in rows),
    }


def suffix(reroute):
    """Output name suffix: '' (fixed routes), '-reroute' (every vehicle), '-reroute-p20' (20% of vehicles)."""
    return '' if not reroute else '-reroute' if reroute == 1 else f'-reroute-p{round(reroute * 100)}'


def run_period(period, reroute=0.0):
    shares = hourly_shares()
    stations = list(csv.DictReader(open(ROOT / 'data' / 'processed' / 'count_stations.csv', encoding='utf-8')))
    out = ROOT / 'output' / f'baseline{suffix(reroute).replace("-", "_")}' / period if reroute else None
    extra = ['--device.rerouting.probability', str(reroute), *REROUTE[2:]] if reroute else ()
    result = compare(period, simulate(period, out, extra=extra), shares, stations)
    print(result, flush=True)
    return result


def main(periods, reroute=0.0):
    ready = [p for p in periods if (DEMAND / p / "car.rou.xml").exists()]
    for p in set(periods) - set(ready):
        print(f'skip {p}: run build_demand.py first')
    if reroute:
        with ProcessPoolExecutor(min(len(ready), 4)) as pool:
            results = list(pool.map(run_period, ready, [reroute] * len(ready)))
    else:
        results = [run_period(p) for p in ready]
    title = 'ผลการปรับเทียบเมื่อเปิดการหาเส้นทางใหม่ (ขั้นที่ 5 แก้ปัญหาค้าง)' if reroute else 'ผลการปรับเทียบ (ขั้นที่ 4)'
    note = f' · รถ {reroute:.0%} หาเส้นทางใหม่ทุก {REROUTE_S} วินาที' if reroute else ''
    lines = [f'# {title}', '',
             f'GEH ต่อจุดนับและทิศทาง ในชั่วโมงศึกษา เกณฑ์ยอมรับ GEH < 5{note}', '',
             '| ช่วงเวลา | ชั่วโมง | รถทั้งหมดในการจำลอง | ยังวิ่งอยู่ตอนจบ | teleport | ความเร็วเฉลี่ย (กม./ชม.) | GEH < 5 | ค่าเป้าหมายรวม | ค่าจำลองรวม |',
             '|---|---|---|---|---|---|---|---|---|']
    lines += [f"| {r['period']} | {r['hour']} | {r['vehicles']:,} | {r['running_end']:,} | {r['teleports']} | {r['speed_kmh']} | {r['geh_ok']} | "
              f"{r['target_sum']:,} | {r['sim_sum']:,} |" for r in results]
    (ROOT / 'docs' / f'calibration{suffix(reroute)}.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    args = sys.argv[1:]
    reroute = 0.0
    if '--reroute' in args:
        i = args.index('--reroute')
        share = args[i + 1] if i + 1 < len(args) and args[i + 1] not in PERIODS else None
        reroute = float(share) if share else 1.0
        del args[i:i + (2 if share else 1)]
    main(args or list(PERIODS), reroute)
