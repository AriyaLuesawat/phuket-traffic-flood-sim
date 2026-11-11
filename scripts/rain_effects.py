"""Step 5a: rain classes and their effect on road speed and capacity, plus how often each class occurs in Phuket.

    .venv/bin/python scripts/rain_effects.py

Hourly classes follow the rain-intensity bands of HCM 2010 Exhibit 10-15 (0.10 and 0.25 in/h = 2.54 and
6.35 mm/h). Capacity factors = 1 - the HCM average reduction; speed factors are SHRP 2-L08 values for a
65 mi/h free-flow speed, both as tabulated in FHWA-HOP-13-042 Appendix A (Tables 33, 34 and 36).
Daily classes are the TMD 24-hour (07:00-07:00) categories.

Inputs : data/raw/rain/era5_phuket_town_2000_2026.json
Outputs: config/rain_effects.csv, docs/rain-climatology.md
"""
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAIN = ROOT / 'data' / 'raw' / 'rain' / 'era5_phuket_town_2000_2026.json'
WET = 0.1  # mm/h; smallest amount the TMD records as rain

# class -> (lower mm/h, upper mm/h, capacity factor, capacity factor range, speed factor, note on the speed factor)
CLASSES = {
    'dry':    (0.0, WET, 1.00, (1.00, 1.00), 1.00, ''),
    'light':  (WET, 2.54, 0.98, (0.9657, 0.9883), 0.98, 'FHWA interpolation (Table 36); SHRP 2-L08 has no light-rain class'),
    'medium': (2.54, 6.35, 0.93, (0.8990, 0.9433), 0.94, 'SHRP 2-L08, 65 mi/h (Table 34)'),
    'heavy':  (6.35, None, 0.86, (0.8233, 0.8928), 0.93, 'SHRP 2-L08, 65 mi/h (Table 34)'),
}
TMD_DAILY = [('ไม่มีฝน', 0, 0.1), ('เล็กน้อย', 0.1, 10.05), ('ปานกลาง', 10.05, 35.05),
             ('หนัก', 35.05, 90.05), ('หนักมาก', 90.05, None)]  # 0.1-10.0, 10.1-35.0, 35.1-90.0, >90.0 mm


def hourly_class(mm):
    for name, (lo, hi, *_) in CLASSES.items():
        if mm >= lo and (hi is None or mm < hi):
            return name
    return 'dry'


def write_config():
    path = ROOT / 'config' / 'rain_effects.csv'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['class', 'min_mm_h', 'max_mm_h', 'capacity_factor', 'capacity_factor_low', 'capacity_factor_high',
                    'speed_factor', 'speed_source'])
        for name, (lo, hi, caf, (caf_lo, caf_hi), saf, note) in CLASSES.items():
            w.writerow([name, lo, '' if hi is None else hi, caf, caf_lo, caf_hi, saf, note])
    return path


def climatology():
    data = json.loads(RAIN.read_text())['hourly']
    hours = [(datetime.fromisoformat(t), p or 0.0) for t, p in zip(data['time'], data['precipitation'])]
    years = (hours[-1][0] - hours[0][0]).days / 365.25

    per_class = defaultdict(int)
    for _, mm in hours:
        per_class[hourly_class(mm)] += 1

    days = defaultdict(list)  # TMD rain day 07:00-07:00, labelled by its start date
    for t, mm in hours:
        days[(t - timedelta(hours=7)).date()].append(mm)
    daily = [(d, sum(v), max(v), sum(mm >= WET for mm in v)) for d, v in days.items() if len(v) == 24]

    lines = ['# ฝนในภูเก็ตจาก ERA5 (ขั้นที่ 5)', '',
             f'ข้อมูลฝนรายชั่วโมง ERA5 ช่องกริดใกล้ตัวเมืองภูเก็ต {hours[0][0]:%Y-%m-%d} ถึง {hours[-1][0]:%Y-%m-%d} '
             f'({len(hours):,} ชั่วโมง, {years:.1f} ปี) สร้างโดย `scripts/rain_effects.py`', '',
             '**ข้อจำกัด:** ERA5 เป็นค่าเฉลี่ยบนกริด ~25 กม. ความเข้มฝนรายชั่วโมงสูงสุดต่ำกว่าที่สถานีวัดได้ '
             'และมีฝนปรอยเล็กน้อยบ่อยกว่าจริง ตารางนี้ใช้ดูแนวโน้มและเลือกสถานการณ์จำลองเท่านั้น', '',
             '## ชั่วโมงฝนตามระดับความเข้ม (เกณฑ์ HCM 2010)', '',
             '| ระดับ | มม./ชม. | ชั่วโมงต่อปี | สัดส่วน | ตัวคูณความจุ | ตัวคูณความเร็ว |',
             '|---|---|---|---|---|---|']
    for name, (lo, hi, caf, _, saf, _) in CLASSES.items():
        rng = f'≥ {lo:g}' if hi is None else f'{lo:g}–{hi:g}'
        lines.append(f'| {name} | {rng} | {per_class[name] / years:,.0f} | {100 * per_class[name] / len(hours):.1f}% '
                     f'| {caf} | {saf} |')

    lines += ['', '## วันฝนตามเกณฑ์กรมอุตุนิยมวิทยา (ฝนรวม 07.00–07.00 น.)', '',
              '| ระดับ | วันต่อปี | ชั่วโมงที่มีฝนต่อวัน (มัธยฐาน) | ฝนสูงสุดรายชั่วโมง มัธยฐาน (มม./ชม.) | ฝนสูงสุดรายชั่วโมง เปอร์เซ็นไทล์ 90 |',
              '|---|---|---|---|---|']
    for name, lo, hi in TMD_DAILY:
        sel = [d for d in daily if d[1] >= lo and (hi is None or d[1] < hi)]
        if not sel:
            continue
        peaks = sorted(d[2] for d in sel)
        p90 = peaks[min(len(peaks) - 1, int(0.9 * len(peaks)))]
        lines.append(f'| {name} | {len(sel) / years:.1f} | {statistics.median(d[3] for d in sel):g} '
                     f'| {statistics.median(peaks):.1f} | {p90:.1f} |')

    lines += ['', '## วันที่ฝนมากที่สุด 10 อันดับ', '', '| วันฝน (เริ่ม 07.00 น.) | ฝนรวม (มม.) | สูงสุดรายชั่วโมง (มม./ชม.) | ชั่วโมงที่มีฝน |',
              '|---|---|---|---|']
    for d, total, peak, wet in sorted(daily, key=lambda x: -x[1])[:10]:
        lines.append(f'| {d} | {total:.1f} | {peak:.1f} | {wet} |')
    path = ROOT / 'docs' / 'rain-climatology.md'
    path.write_text('\n'.join(lines) + '\n')
    return path


if __name__ == '__main__':
    print(write_config())
    print(climatology())
