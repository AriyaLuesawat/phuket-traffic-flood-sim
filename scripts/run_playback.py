"""Step 9a: reruns seed 1 of every step 8 scenario with edge means every 5 minutes, for the playback web page.

    .venv/bin/python scripts/run_playback.py                 # every period x scenario (36 runs)
    .venv/bin/python scripts/run_playback.py morning_peak

The step 8 runs kept only study-hour means per edge. These runs use the same settings and seed 1 as step 8
(run_rain.py --reroute 0.2 for the rain-only scenarios, run_scenarios.py for the flood scenarios) and add an
edgeData output every PLAYBACK_S seconds from the start of the warm-up to the end of the study hour. The
study-hour results should equal those of seed 1 in step 8, which check() tests.
Finished runs are kept, not rerun (scripts/step8.sh stops and resumes the queue).
Outputs: output/playback/<period>/<scenario>/ (edgedata_playback.xml, plus the step 8 outputs)
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
PLAYBACK_S = 300
os.environ['PLAYBACK_S'] = str(PLAYBACK_S)  # read by run_baseline.sumo_cmd, inherited by the pool workers
from build_demand import PERIODS  # noqa: E402
from run_baseline import REROUTE, simulate  # noqa: E402
from run_flood_traffic import run_case  # noqa: E402
from run_rain import MESO_TAU, finished, metrics, rain_classes, write_vtypes  # noqa: E402
from run_scenarios import FLOOD_AT, FLOOD_DATE, FLOODS, RAIN_DIR, SCENARIOS, flood_dir  # noqa: E402

OUT = ROOT / 'output' / 'playback'
SEED = 1


def done(out, scenario):
    return finished(out) and (scenario not in FLOODS or (out / 'standing_water.json').exists())


def run(period, scenario):
    out = OUT / period / scenario
    if done(out, scenario):
        return
    if scenario in FLOODS:
        run_case(period, FLOOD_DATE, 'flood', SEED, rain='heavy', flood_at=FLOOD_AT, out=out, flood=FLOODS[scenario])
    else:  # as run_rain.main with reroute 0.2
        c = next(k for k in rain_classes() if k['class'] == scenario)
        caf = float(c['capacity_factor'])
        extra = [arg for k, v in MESO_TAU.items() for arg in (f'--meso-{k}', f'{v / caf:.4f}')]
        extra += ['--device.rerouting.probability', '0.2', *REROUTE[2:-2], '--seed', SEED]
        out.mkdir(parents=True, exist_ok=True)
        simulate(period, out, write_vtypes(out / 'vtypes.add.xml', float(c['speed_factor'])), extra)
    print(period, scenario, 'done', flush=True)


def check(periods):
    """Study-hour speed of each playback run against seed 1 of step 8."""
    for p in periods:
        for sc in SCENARIOS:
            out = OUT / p / sc
            if not done(out, sc):
                print(p, sc, 'not finished')
                continue
            ref = flood_dir(p, SEED, sc) if sc in FLOODS else RAIN_DIR / p / sc / f'seed{SEED}'
            a, b = metrics(out)['speed_kmh'], metrics(ref)['speed_kmh']
            print(f'{p} {sc}: {a:.2f} km/h, step 8 seed {SEED} {b:.2f} km/h')


def main():
    periods = sys.argv[1:] or list(PERIODS)
    jobs = [(p, sc) for p in periods for sc in SCENARIOS]
    with ProcessPoolExecutor(5) as pool:
        list(pool.map(run, *zip(*jobs)))
    check(periods)


if __name__ == '__main__':
    main()
