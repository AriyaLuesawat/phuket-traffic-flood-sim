"""Generates SIMULATED expert ratings for the content validity (IOC) of the Phuket Native questionnaire.

    .venv/bin/python scripts/make_synthetic_ioc.py

NOT REAL EXPERTS. The course (COM-101) allows simulated data for the project; the paper must say so.

Method (Rovinelli & Hambleton, 1977; COM-101 Slide 7): 3 experts rate every item against the objective it
is meant to measure: +1 = sure it measures it, 0 = unsure, -1 = sure it does not. IOC = mean rating.
IOC = 1 keep, 0.5 <= IOC < 1 minor edit, IOC < 0.5 revise or cut.
Each simulated rating is +1 with probability 0.85, 0 with 0.12 and -1 with 0.03 (a guess, seed 2571).
Round 2: items with IOC < 0.5 get the revised wording in REVISED (also in forms/create-phuket-native-form.gs)
and are rated again with the same probabilities.

Output: data/synthetic/phuket-native-SYNTHETIC-ioc.csv and a Markdown table next to it.
"""
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
rng = np.random.default_rng(2571)
EXPERTS = 3

ITEMS = (
    [(c, 'ข้อมูลทั่วไป') for c in ['Role', 'Age', 'TravelMode', 'FloodEncounter', 'MapAppUse']]
    + [(f'SUS{i}', 'ความใช้งานง่าย (SUS)') for i in range(1, 11)]
    + [(c, 'คุณภาพข้อมูล (EUCS)') for c in ['C1', 'C3', 'C4', 'F1', 'F2']]
    + [(c, 'การรับรู้ประโยชน์ (PU)') for c in ['PU1', 'PU2', 'PU5', 'PU6']]
    + [(c, 'ความตั้งใจใช้ต่อ (CI)') for c in ['CI1', 'CI2']]
    + [('FloodMatch', 'ความรู้ในพื้นที่')]
)

# wording before -> after for items that fail round 1, each closer to the source item (Brooke, 1996;
# Doll & Torkzadeh, 1988; Davis, 1989) or no longer asking two things at once
REVISED = {
    'SUS3': ('Phuket Native ใช้งานง่าย', 'ฉันคิดว่า Phuket Native ใช้งานง่าย'),
    'SUS6': ('หน้าจอแต่ละส่วนของ Phuket Native ไม่ไปในทางเดียวกัน ทำให้สับสน',
             'ฉันคิดว่าส่วนต่าง ๆ ของ Phuket Native ไม่สอดคล้องกันมากเกินไป'),
    'SUS8': ('Phuket Native ใช้งานยุ่งยาก', 'ฉันรู้สึกว่า Phuket Native ใช้งานยุ่งยากมาก'),
    'C3': ('แผนที่และกราฟใน Phuket Native ตอบสิ่งที่ฉันอยากรู้ได้ตรงประเด็น',
           'แผนที่และกราฟใน Phuket Native ให้ข้อมูลตรงกับที่ฉันต้องการ'),
    'PU5': ('Phuket Native ทำให้การวางแผนเดินทางช่วงฝนตกหรือน้ำท่วมง่ายขึ้น',
            'Phuket Native ทำให้การวางแผนเดินทางช่วงฝนตกง่ายขึ้น'),
}


def rate():
    r = rng.choice([1, 0, -1], EXPERTS, p=[0.85, 0.12, 0.03])
    ioc = r.mean()
    return r, ioc, 'ใช้ได้' if ioc == 1 else 'ใช้ได้ ปรับถ้อยคำเล็กน้อย' if ioc >= 0.5 else 'ต้องปรับหรือตัดออก'


rows, round2 = [], []
for code, construct in ITEMS:
    r, ioc, verdict = rate()
    rows.append((code, construct, *r, round(ioc, 2), verdict))
for code, construct, *_, ioc, _ in rows:
    if ioc < 0.5:
        assert code in REVISED, f'{code} failed round 1 but has no revised wording'
        r, ioc2, verdict = rate()
        round2.append((code, construct, *r, round(ioc2, 2), verdict))

out = ROOT / 'data' / 'synthetic' / 'phuket-native-SYNTHETIC-ioc.csv'
with open(out, 'w', encoding='utf-8-sig') as f:
    f.write('Item,Construct,' + ','.join(f'Expert{i + 1}' for i in range(EXPERTS)) + ',IOC,Verdict,DataType\n')
    for row in rows:
        f.write(','.join(map(str, row)) + ',SYNTHETIC\n')
    for row in round2:
        f.write(','.join(map(str, (row[0] + ' (รอบ 2)', *row[1:]))) + ',SYNTHETIC\n')

iocs = np.array([row[-2] for row in rows])
md = ['# IOC ของแบบสอบถาม (ข้อมูลจำลอง)', '',
      '> **ผู้เชี่ยวชาญ 3 คนเป็นข้อมูลจำลอง (SYNTHETIC) ไม่ใช่ผู้เชี่ยวชาญจริง**', '',
      '| ข้อ | ด้าน | ผู้เชี่ยวชาญ 1 | ผู้เชี่ยวชาญ 2 | ผู้เชี่ยวชาญ 3 | IOC | ผล |', '|---|---|---|---|---|---|---|']
md += [f'| {c} | {k} | {a:+d} | {b:+d} | {d:+d} | {i:.2f} | {v} |' for c, k, a, b, d, i, v in rows]
md += ['', f'ทั้งหมด {len(rows)} ข้อ · IOC = 1: {(iocs == 1).sum()} ข้อ · 0.50–0.99: {((iocs >= 0.5) & (iocs < 1)).sum()} ข้อ'
       f' · < 0.50: {(iocs < 0.5).sum()} ข้อ · IOC เฉลี่ยทั้งฉบับ {iocs.mean():.2f}']
final = {r[0]: r[-2] for r in rows} | {r[0]: r[-2] for r in round2}
fin = np.array(list(final.values()))
md += ['', '## รอบ 2 (ข้อที่ปรับถ้อยคำ)', '', '| ข้อ | ถ้อยคำเดิม | ถ้อยคำใหม่ | ผู้เชี่ยวชาญ 1 | ผู้เชี่ยวชาญ 2 | ผู้เชี่ยวชาญ 3 | IOC | ผล |',
       '|---|---|---|---|---|---|---|---|']
md += [f'| {c} | {REVISED[c][0]} | {REVISED[c][1]} | {a:+d} | {b:+d} | {d:+d} | {i:.2f} | {v} |' for c, k, a, b, d, i, v in round2]
md += ['', f'หลังรอบ 2: IOC ต่ำสุด {fin.min():.2f} · IOC เฉลี่ยทั้งฉบับ {fin.mean():.2f} · ข้อที่ยัง < 0.50: '
       f'{", ".join(c for c, v in final.items() if v < 0.5) or "ไม่มี"}']
out.with_suffix('.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print(out, f'round 1 mean {iocs.mean():.2f}; round 2: {[(r[0], r[-2]) for r in round2]}; final mean {fin.mean():.2f}, min {fin.min():.2f}')
