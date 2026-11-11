"""Step 5b: runs each period under steady rain of each class and compares it with the dry run.

    .venv/bin/python scripts/run_rain.py                    # all periods
    .venv/bin/python scripts/run_rain.py evening_peak
    .venv/bin/python scripts/run_rain.py --reroute 0.2 --classes dry,light morning_peak evening_peak

Rain is applied to the whole island for the full run (one ERA5 grid cell covers the island anyway):
  - speed:    every vehicle's speed factor x the class speed factor (lower desired speed)
  - capacity: SUMO meso headway parameters (tauff, taufj, taujf, taujj) / the class capacity factor, since a
              segment's discharge rate is proportional to 1 / headway
Demand and routes stay as in the dry run: nobody cancels or reschedules a trip because of rain (a stated
assumption; Takano et al. 2023 found Bangkok peak traffic slowed more in rain partly because of mode shift).

--reroute P gives a share P of the vehicles SUMO's rerouting device (as run_baseline.py --reroute) and writes
to output/rain_reroute_pNN/ and docs/rain-results-reroute-pNN.md; --classes limits the rain classes. Seeds that finished earlier (see finished()) are read, not rerun, so a stopped run can be started
again with the same command (scripts/step8.sh).
Outputs: output/rain/<period>/<class>/..., docs/rain-results.md
"""
import csv
import statistics
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_demand import PERIODS, WARMUP  # noqa: E402
from run_baseline import DEMAND, REROUTE, simulate, suffix  # noqa: E402

MESO_TAU = {'tauff': 1.13, 'taufj': 1.13, 'taujf': 1.73, 'taujj': 1.4}  # SUMO 1.28 defaults
SPEED_DEV = 0.1  # SUMO default speed deviation for every vehicle class used here
# Near capacity, whether a corridor breaks down depends on random driver speeds, so each case is run with
# several random seeds and reported as mean and range.
SEEDS = [1, 2, 3, 4, 5]


def rain_classes():
    return list(csv.DictReader(open(ROOT / 'config' / 'rain_effects.csv', encoding='utf-8')))


def write_vtypes(path, speed_factor):
    root = ET.parse(DEMAND / 'vtypes.add.xml').getroot()
    for vtype in root.iter('vType'):
        vtype.set('speedFactor', f'normc({speed_factor},{SPEED_DEV},0.2,2)')
    ET.ElementTree(root).write(path, encoding='utf-8')
    return path


def finished(out):
    """True if sumo simulated the whole run (warm-up + study hour). A stopped sumo still writes stats.xml and
    closes its outputs, so the simulated duration in stats.xml is checked, not just the file. A killed sumo
    leaves stats.xml with no performance element."""
    try:
        perf = ET.parse(out / 'stats.xml').getroot().find('performance')
    except (OSError, ET.ParseError):
        return False
    return perf is not None and float(perf.get('duration')) >= WARMUP + 3600


def metrics(out):
    """Network mean speed in the study hour, plus trip statistics of vehicles that finished."""
    ss = sp = 0.0
    for e in ET.parse(out / 'edgedata.xml').getroot().iter('edge'):
        ss += float(e.get('sampledSeconds', 0))
        sp += float(e.get('sampledSeconds', 0)) * float(e.get('speed', 0))
    trips = [t for t in ET.parse(out / 'tripinfo.xml').getroot().iter('tripinfo')]
    stats = ET.parse(out / 'stats.xml').getroot()
    return {
        'speed_kmh': sp / ss * 3.6,
        'trips_done': len(trips),
        'duration_s': statistics.mean(float(t.get('duration')) for t in trips),
        'timeloss_s': statistics.mean(float(t.get('timeLoss')) for t in trips),
        'running_end': int(stats.find('vehicles').get('running')),
        'teleports': int(stats.find('teleports').get('total')),
    }


def main(periods, reroute=0.0, classes=None):
    rows = []
    folder = f'rain{suffix(reroute).replace("-", "_")}'
    for period in periods:
        base = None
        for c in [c for c in rain_classes() if not classes or c['class'] in classes]:
            caf = float(c['capacity_factor'])
            extra = [arg for k, v in MESO_TAU.items() for arg in (f'--meso-{k}', f'{v / caf:.4f}')]
            if reroute:
                extra += ['--device.rerouting.probability', str(reroute), *REROUTE[2:-2]]

            def run(seed):
                out = ROOT / 'output' / folder / period / c['class'] / f'seed{seed}'
                if finished(out):
                    return metrics(out)
                out.mkdir(parents=True, exist_ok=True)
                simulate(period, out, write_vtypes(out / 'vtypes.add.xml', float(c['speed_factor'])),
                         extra + ['--seed', seed])
                return metrics(out)
            with ThreadPoolExecutor(len(SEEDS)) as pool:  # seeds run as parallel sumo processes
                runs = list(pool.map(run, SEEDS))
            m = {k: statistics.mean(r[k] for r in runs) for k in runs[0]}
            m['speed_min'] = min(r['speed_kmh'] for r in runs)
            m['speed_max'] = max(r['speed_kmh'] for r in runs)
            base = base or m
            rows.append({'period': period, 'class': c['class'], **m,
                         'speed_change': 100 * (m['speed_kmh'] / base['speed_kmh'] - 1),
                         'duration_change': 100 * (m['duration_s'] / base['duration_s'] - 1)})
            print({k: round(v, 1) if isinstance(v, float) else v for k, v in rows[-1].items()}, flush=True)

    note = f' · รถ {reroute:.0%} หาเส้นทางใหม่ทุก 300 วินาที' if reroute else ''
    lines = ['# ผลของฝนต่อการจราจร (ขั้นที่ 5)' + note, '',
             'ฝนตกสม่ำเสมอทั้งเกาะตลอดการจำลอง ความต้องการเดินทางเท่ากับวันไม่มีฝน '
             f'แต่ละกรณีรัน {len(SEEDS)} seed แสดงค่าเฉลี่ย (ช่วงต่ำสุด–สูงสุดของความเร็ว) '
             'ค่าเปลี่ยนแปลงเทียบกับกรณีไม่มีฝนของช่วงเวลาเดียวกัน สร้างโดย `scripts/run_rain.py`', '',
             '| ช่วงเวลา | ระดับฝน | ความเร็วเฉลี่ย (กม./ชม.) | ช่วง | เปลี่ยน | เวลาเดินทางเฉลี่ย (นาที) | เปลี่ยน | ยังวิ่งอยู่ตอนจบ | teleport |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['period']} | {r['class']} | {r['speed_kmh']:.1f} | {r['speed_min']:.1f}–{r['speed_max']:.1f} | "
                     f"{r['speed_change']:+.1f}% | {r['duration_s'] / 60:.1f} | {r['duration_change']:+.1f}% | "
                     f"{r['running_end']:,.0f} | {r['teleports']:.0f} |")
    (ROOT / 'docs' / f'rain-results{suffix(reroute)}.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    args = sys.argv[1:]
    opts = {}
    for flag in ('--reroute', '--classes'):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    main(args or list(PERIODS), float(opts.get('--reroute', 0)),
         opts['--classes'].split(',') if '--classes' in opts else None)
