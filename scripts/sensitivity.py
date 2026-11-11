"""Step 10a: sensitivity of the results to the assumed values, morning peak, 5 seeds per case.

    .venv/bin/python scripts/sensitivity.py run          # every case not finished yet, in the order of CASES
    .venv/bin/python scripts/sensitivity.py summary      # docs/sensitivity.md from finished cases

Each case changes one assumption and is compared with the base runs it changes (same seeds):
  radius_50, radius_200   water at the reported places within 50 / 200 m instead of 100 m (reported_flood.py),
                          step 7 setting (29 Oct 2569 08:00, light rain); base: step 7 'reports 0.3 m'
  minspeed_<v>_<flood>    lowest speed limit on a wet road v km/h instead of 2.1 km/h (v(300 mm) of
                          Pregnolato et al. 2017, held for deeper water: an assumption, the function is fitted
                          only below 300 mm); step 7 setting, reported places or modelled flood; base: step 7
  capacity_low/high       heavy-rain capacity factor at the low / high end of the range in
                          config/rain_effects.csv instead of the central value, rain only, step 8 setting;
                          base: step 8 'heavy'
The values 5 and 10 km/h are test values chosen for this analysis, not from a source.
Outputs: output/sensitivity/<case>/seed<N>/, docs/sensitivity.md
"""
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from road_flood_depth import RUN  # noqa: E402
from run_baseline import REROUTE, simulate  # noqa: E402
from run_flood_traffic import folder, run_case  # noqa: E402
from run_rain import MESO_TAU, SEEDS, finished, metrics, rain_classes, write_vtypes  # noqa: E402

OUT = ROOT / 'output' / 'sensitivity'
DATE, PERIOD = '2026-10-29', 'morning_peak'
STEP7_RAIN = folder(PERIOD, DATE) / 'rain'
REPORTS = 'reports_d300'
# case -> (kind, settings, base folder, reference folder for the change, label)
CASES = {
    'radius_50': ('flood', {'flood': 'reports_d300_r050'}, folder(PERIOD, DATE, REPORTS) / 'flood', STEP7_RAIN,
                  'น้ำจุดข่าว รัศมี 50 ม. (ฐาน 100 ม.)'),
    'radius_200': ('flood', {'flood': 'reports_d300_r200'}, folder(PERIOD, DATE, REPORTS) / 'flood', STEP7_RAIN,
                   'น้ำจุดข่าว รัศมี 200 ม. (ฐาน 100 ม.)'),
    'minspeed_10_reports': ('flood', {'flood': REPORTS, 'min_kmh': 10}, folder(PERIOD, DATE, REPORTS) / 'flood',
                            STEP7_RAIN, 'น้ำจุดข่าว ความเร็วต่ำสุดในน้ำ 10 กม./ชม. (ฐาน 2.1)'),
    'minspeed_10_model': ('flood', {'flood': RUN.name, 'min_kmh': 10}, folder(PERIOD, DATE) / 'flood', STEP7_RAIN,
                          'น้ำแบบจำลอง ความเร็วต่ำสุดในน้ำ 10 กม./ชม. (ฐาน 2.1)'),
    'capacity_low': ('rain', {'capacity': 'capacity_factor_low'}, ROOT / 'output' / 'rain_reroute_p20' / PERIOD / 'heavy',
                     ROOT / 'output' / 'rain_reroute_p20' / PERIOD / 'dry', 'ฝนหนัก ค่าลดความจุต่ำสุดของช่วง'),
    'capacity_high': ('rain', {'capacity': 'capacity_factor_high'}, ROOT / 'output' / 'rain_reroute_p20' / PERIOD / 'heavy',
                      ROOT / 'output' / 'rain_reroute_p20' / PERIOD / 'dry', 'ฝนหนัก ค่าลดความจุสูงสุดของช่วง'),
    'minspeed_5_reports': ('flood', {'flood': REPORTS, 'min_kmh': 5}, folder(PERIOD, DATE, REPORTS) / 'flood',
                           STEP7_RAIN, 'น้ำจุดข่าว ความเร็วต่ำสุดในน้ำ 5 กม./ชม. (ฐาน 2.1)'),
    'minspeed_5_model': ('flood', {'flood': RUN.name, 'min_kmh': 5}, folder(PERIOD, DATE) / 'flood', STEP7_RAIN,
                         'น้ำแบบจำลอง ความเร็วต่ำสุดในน้ำ 5 กม./ชม. (ฐาน 2.1)'),
}


def done(case, out):
    return finished(out) and (CASES[case][0] != 'flood' or (out / 'standing_water.json').exists())


def run(case, seed):
    out = OUT / case / f'seed{seed}'
    if done(case, out):
        return
    kind, cfg = CASES[case][:2]
    if kind == 'flood':
        run_case(PERIOD, DATE, 'flood', seed, out=out, flood=cfg['flood'], min_kmh=cfg.get('min_kmh'))
    else:  # as run_rain.main with reroute 0.2, heavy rain, another capacity factor
        c = next(k for k in rain_classes() if k['class'] == 'heavy')
        caf = float(c[cfg['capacity']])
        extra = [arg for k, v in MESO_TAU.items() for arg in (f'--meso-{k}', f'{v / caf:.4f}')]
        extra += ['--device.rerouting.probability', '0.2', *REROUTE[2:-2], '--seed', seed]
        out.mkdir(parents=True, exist_ok=True)
        simulate(PERIOD, out, write_vtypes(out / 'vtypes.add.xml', float(c['speed_factor'])), extra)
    print(case, seed, 'done', flush=True)


def mean(folders, key):
    return statistics.mean(metrics(f)[key] for f in folders)


def summary():
    lines = ['# ความไวของผลต่อค่าสมมติฐาน (ขั้นที่ 10)', '',
             'ช่วงเร่งด่วนเช้า 08:00–09:00 แต่ละกรณีเปลี่ยนค่าเดียว 5 seed เทียบกับกรณีฐานที่ใช้ seed เดียวกัน '
             '"เปลี่ยน" คือเทียบกับกรณีอ้างอิง (ฝนอย่างเดียวของขั้นที่ 7 หรือไม่มีฝนของขั้นที่ 8) '
             'สร้างโดย `scripts/sensitivity.py` ค่าทดสอบ 5 และ 10 กม./ชม. เลือกเพื่อการวิเคราะห์นี้ ไม่มีแหล่งอ้างอิง', '',
             '| กรณี | ความเร็ว ฐาน → ทดสอบ (กม./ชม.) | เปลี่ยน ฐาน → ทดสอบ | เวลาเดินทาง ฐาน → ทดสอบ (นาที) | เปลี่ยน ฐาน → ทดสอบ |',
             '|---|---|---|---|---|']
    missing = []
    for case, (kind, cfg, base, ref, label) in CASES.items():
        test = [OUT / case / f'seed{s}' for s in SEEDS]
        if not all(done(case, t) for t in test):
            missing.append(case)
            continue
        b = [base / f'seed{s}' for s in SEEDS]
        r = [ref / f'seed{s}' for s in SEEDS]
        sp = [mean(x, 'speed_kmh') for x in (r, b, test)]
        du = [mean(x, 'duration_s') / 60 for x in (r, b, test)]
        lines.append(f'| {label} | {sp[1]:.1f} → {sp[2]:.1f} | {100 * (sp[1] / sp[0] - 1):+.1f}% → {100 * (sp[2] / sp[0] - 1):+.1f}% | '
                     f'{du[1]:.1f} → {du[2]:.1f} | {100 * (du[1] / du[0] - 1):+.1f}% → {100 * (du[2] / du[0] - 1):+.1f}% |')
    if missing:
        lines += ['', 'ยังไม่เสร็จ: ' + ', '.join(missing)]
    (ROOT / 'docs' / 'sensitivity.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


def main():
    if sys.argv[1:2] == ['run']:
        jobs = [(c, s) for c in CASES for s in SEEDS]
        with ProcessPoolExecutor(5) as pool:
            list(pool.map(run, *zip(*jobs)))
    summary()


if __name__ == '__main__':
    main()
