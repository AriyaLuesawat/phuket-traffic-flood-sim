"""Generates SYNTHETIC answers to the Phuket Native questionnaire for practising the analysis in jamovi.

    .venv/bin/python scripts/make_synthetic_survey.py

NOT REAL DATA. Never report it as a pilot test or use it in the paper.

Each simulated respondent has three correlated latent attitudes (usability, information quality, usefulness;
r = 0.5). An item answer = 3 + loading x attitude + noise, rounded and clipped to 1-5. Negative SUS items
(2, 4, 6, 8, 10) use the opposite sign, so they must be reverse scored before Cronbach's alpha.
Continuance intention follows usefulness and usability. Demographic shares are guesses for a student sample.

Output: data/synthetic/phuket-native-SYNTHETIC-n30.csv (and .xlsx)
"""
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
N, SEED = 30, 2569
rng = np.random.default_rng(SEED)

cov = np.full((3, 3), 0.5) + 0.5 * np.eye(3)
usab, info, useful = rng.multivariate_normal([0.3, 0.4, 0.5], cov, N).T
cont = 0.6 * useful + 0.3 * usab + rng.normal(0, 0.6, N)


def item(latent, loading=0.9, noise=0.6, sign=1):
    return np.clip(np.rint(3 + sign * loading * latent + rng.normal(0, noise, N)), 1, 5).astype(int)


def pick(options, p):
    return rng.choice(options, N, p=p)


cols = {
    'Id': np.arange(1, N + 1),
    'Role': pick(['นักศึกษา', 'อาศัยหรือทำงานในภูเก็ต', 'นักท่องเที่ยว / มาเยือนชั่วคราว', 'เจ้าหน้าที่หน่วยงานรัฐหรือท้องถิ่น'],
                 [0.6, 0.25, 0.1, 0.05]),
    'Age': pick(['18–24 ปี', '25–34 ปี', '35–44 ปี', '45–54 ปี', '55 ปีขึ้นไป'], [0.6, 0.2, 0.1, 0.07, 0.03]),
    'TravelMode': pick(['รถจักรยานยนต์', 'รถยนต์ส่วนตัว', 'รถโดยสารสาธารณะ / รถรับจ้าง', 'ไม่ได้เดินทางในภูเก็ตเป็นประจำ'],
                       [0.55, 0.3, 0.1, 0.05]),
    'FloodEncounter': pick(['ไม่เคย', '1–2 ครั้ง', '3–5 ครั้ง', 'มากกว่า 5 ครั้ง'], [0.15, 0.4, 0.3, 0.15]),
    'MapAppUse': pick(['ไม่เคย', 'น้อยกว่าเดือนละครั้ง', 'เดือนละ 1–4 ครั้ง', 'หลายครั้งต่อสัปดาห์'], [0.03, 0.1, 0.3, 0.57]),
}
for i in range(1, 11):
    cols[f'SUS{i}'] = item(usab, sign=1 if i % 2 else -1)
for code in ['C1', 'C3', 'C4', 'F1', 'F2']:
    cols[code] = item(info)
for code in ['PU1', 'PU2', 'PU5', 'PU6']:
    cols[code] = item(useful)
for code in ['CI1', 'CI2']:
    cols[code] = item(cont, loading=0.8)
cols['FloodMatch'] = pick(['ตรงเกือบทั้งหมด', 'ตรงบางส่วน', 'ไม่ค่อยตรง', 'ไม่ทราบ'], [0.2, 0.5, 0.15, 0.15])
cols['DataType'] = np.array(['SYNTHETIC'] * N)

out = ROOT / 'data' / 'synthetic' / 'phuket-native-SYNTHETIC-n30.csv'
header = list(cols)
with open(out, 'w', encoding='utf-8-sig') as f:
    f.write(','.join(header) + '\n')
    for r in range(N):
        f.write(','.join(str(cols[h][r]) for h in header) + '\n')

import openpyxl  # noqa: E402
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'SYNTHETIC'
ws.append(header)
for r in range(N):
    ws.append([cols[h][r].item() if hasattr(cols[h][r], 'item') else cols[h][r] for h in header])
wb.save(out.with_suffix('.xlsx'))
print(out)
