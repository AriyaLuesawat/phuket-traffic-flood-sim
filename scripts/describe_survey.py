"""Descriptive statistics of the questionnaire, in the layout of the COM-101 jamovi lab.

    .venv/bin/python scripts/describe_survey.py data/synthetic/phuket-native-SYNTHETIC-n30.csv

Frequencies + chi-square goodness of fit (equal proportions) for categorical items; mean, SD and class-width
interpretation (width 0.80) for Likert items; construct mean, SD and Cronbach's alpha (negative SUS items
reverse scored); full descriptives, Shapiro-Wilk and 1.5 x IQR outlier fences for the SUS score.
Skewness/kurtosis and their SEs use the same bias-corrected formulas as jamovi and SPSS.
Output: a Markdown report next to the input file.
"""
import csv
import math
import statistics as st
import sys
from collections import Counter
from pathlib import Path

from scipy import stats

CATEGORICAL = {
    'Role': ('ฐานะที่เกี่ยวข้องกับภูเก็ต', ['นักศึกษา', 'อาศัยหรือทำงานในภูเก็ต', 'นักท่องเที่ยว / มาเยือนชั่วคราว', 'เจ้าหน้าที่หน่วยงานรัฐหรือท้องถิ่น']),
    'Age': ('อายุ', ['18–24 ปี', '25–34 ปี', '35–44 ปี', '45–54 ปี', '55 ปีขึ้นไป']),
    'TravelMode': ('วิธีเดินทางบ่อยที่สุด', ['รถจักรยานยนต์', 'รถยนต์ส่วนตัว', 'รถโดยสารสาธารณะ / รถรับจ้าง', 'ไม่ได้เดินทางในภูเก็ตเป็นประจำ']),
    'FloodEncounter': ('เจอน้ำท่วมถนนใน 1 ปี', ['ไม่เคย', '1–2 ครั้ง', '3–5 ครั้ง', 'มากกว่า 5 ครั้ง']),
    'MapAppUse': ('ใช้แอปแผนที่', ['ไม่เคย', 'น้อยกว่าเดือนละครั้ง', 'เดือนละ 1–4 ครั้ง', 'หลายครั้งต่อสัปดาห์']),
    'FloodMatch': ('จุดน้ำท่วมตรงกับที่เคยเห็น', ['ตรงเกือบทั้งหมด', 'ตรงบางส่วน', 'ไม่ค่อยตรง', 'ไม่ทราบ']),
}
NEG = {'SUS2', 'SUS4', 'SUS6', 'SUS8', 'SUS10'}
CONSTRUCTS = {
    'System Usability (SUS)': [
        ('SUS1', 'อยากใช้เป็นประจำ'), ('SUS2', 'ซับซ้อนเกินความจำเป็น (−)'), ('SUS3', 'ใช้งานง่าย'),
        ('SUS4', 'ต้องมีคนเก่งคอมช่วย (−)'), ('SUS5', 'ฟังก์ชันทำงานต่อเนื่องกันดี'), ('SUS6', 'หน้าจอไม่ไปทางเดียวกัน (−)'),
        ('SUS7', 'คนส่วนใหญ่เรียนรู้ได้เร็ว'), ('SUS8', 'ใช้งานยุ่งยาก (−)'), ('SUS9', 'มั่นใจตอนใช้'),
        ('SUS10', 'ต้องเรียนรู้หลายอย่างก่อนใช้ (−)')],
    'Information Quality (EUCS)': [
        ('C1', 'แสดงข้อมูลที่ต้องการรู้'), ('C3', 'แผนที่และกราฟตอบตรงประเด็น'), ('C4', 'ข้อมูลครบพอ'),
        ('F1', 'จัดวางดูง่าย ใช้สะดวก'), ('F2', 'สีและสัญลักษณ์เข้าใจง่าย')],
    'Perceived Usefulness (PU)': [
        ('PU1', 'วางแผนเดินทางช่วงฝนตกได้เร็วขึ้น'), ('PU2', 'วางแผนเดินทางช่วงฝนตกได้ดีขึ้น'),
        ('PU5', 'วางแผนเดินทางช่วงฝนหรือน้ำท่วมง่ายขึ้น'), ('PU6', 'โดยรวมมีประโยชน์')],
    'Continuance Intention (CI)': [('CI1', 'ถ้ามีให้ใช้จริงจะใช้ต่อ'), ('CI2', 'อยากใช้มากกว่าวิธีเดิม')],
}


def level(m):
    for hi, label in [(1.80, 'ไม่เห็นด้วยอย่างยิ่ง'), (2.60, 'ไม่เห็นด้วย'), (3.40, 'ปานกลาง'), (4.20, 'เห็นด้วย')]:
        if m <= hi:
            return label
    return 'เห็นด้วยอย่างยิ่ง'


def alpha(matrix):
    k = len(matrix[0])
    item_var = sum(st.variance([r[j] for r in matrix]) for j in range(k))
    return k / (k - 1) * (1 - item_var / st.variance([sum(r) for r in matrix]))


def shape(x):
    n = len(x)
    skew, kurt = stats.skew(x, bias=False), stats.kurtosis(x, bias=False)
    se_s = math.sqrt(6 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3)))
    se_k = 2 * se_s * math.sqrt((n * n - 1) / ((n - 3) * (n + 5)))
    return skew, se_s, kurt, se_k


def main(path):
    path = Path(path)
    data = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    n = len(data)
    synthetic = any(r.get('DataType') == 'SYNTHETIC' for r in data)
    out = [f'# สถิติเชิงพรรณนา: {path.name}', '']
    if synthetic:
        out += ['> **ข้อมูลจำลอง (SYNTHETIC) ใช้ฝึกวิเคราะห์เท่านั้น ห้ามรายงานเป็นผลการเก็บข้อมูลจริง**', '']
    out += [f'จำนวนผู้ตอบ N = {n}', '', '## ตารางที่ 1 ข้อมูลทั่วไปของผู้ตอบ', '',
            '| ตัวแปร | กลุ่ม | ความถี่ (f) | ร้อยละ (%) |', '|---|---|---|---|']
    tests = []
    for col, (name, cats) in CATEGORICAL.items():
        cnt = Counter(r[col] for r in data)
        for i, c in enumerate(cats):
            out.append(f"| {name if i == 0 else ''} | {c} | {cnt.get(c, 0)} | {100 * cnt.get(c, 0) / n:.1f} |")
        out.append(f'| | **รวม** | **{n}** | **100.0** |')
        chi = stats.chisquare([cnt.get(c, 0) for c in cats])
        tests.append((name, chi.statistic, len(cats) - 1, chi.pvalue))
    out += ['', 'ทดสอบความกลมกลืนด้วยไคสแควร์ (สมมติฐานหลัก: ทุกกลุ่มมีสัดส่วนเท่ากัน)', '',
            '| ตัวแปร | χ² | df | p | ผล |', '|---|---|---|---|---|']
    for name, chi, df, p in tests:
        out.append(f"| {name} | {chi:.2f} | {df} | {'< .001' if p < .001 else f'{p:.3f}'} | "
                   f"{'สัดส่วนไม่เท่ากันอย่างมีนัยสำคัญ' if p < .05 else 'ไม่แตกต่างจากสัดส่วนเท่ากัน'} |")

    out += ['', '## ตารางที่ 2 ค่าเฉลี่ยและส่วนเบี่ยงเบนมาตรฐานรายข้อและรายด้าน', '',
            'เกณฑ์แปลผล (ความกว้างชั้น 0.80): 1.00–1.80 ไม่เห็นด้วยอย่างยิ่ง · 1.81–2.60 ไม่เห็นด้วย · '
            '2.61–3.40 ปานกลาง · 3.41–4.20 เห็นด้วย · 4.21–5.00 เห็นด้วยอย่างยิ่ง', '',
            'ข้อที่มี (−) เป็นข้อความด้านลบ ค่าเฉลี่ยรายข้อแสดงตามที่ตอบ ส่วนค่าเฉลี่ยรายด้านและ α กลับคะแนนข้อเหล่านี้แล้ว (6 − คะแนน)', '',
            '| ด้านและข้อคำถาม | Mean | S.D. | แปลผล | Cronbach\'s α |', '|---|---|---|---|---|']
    summaries = []
    for cname, items in CONSTRUCTS.items():
        matrix = [[6 - int(r[c]) if c in NEG else int(r[c]) for c, _ in items] for r in data]
        scores = [st.mean(row) for row in matrix]
        a, m, sd = alpha(matrix), st.mean(scores), st.stdev(scores)
        summaries.append((cname, len(items), a, m, sd))
        out.append(f'| **{cname}** | **{m:.2f}** | **{sd:.2f}** | **{level(m)}** | **{a:.3f}** |')
        for code, label in items:
            x = [int(r[code]) for r in data]
            out.append(f'| {code}: {label} | {st.mean(x):.2f} | {st.stdev(x):.2f} | {level(st.mean(x))} | |')

    sus = [sum((int(r[f'SUS{i}']) - 1) if i % 2 else (5 - int(r[f'SUS{i}'])) for i in range(1, 11)) * 2.5 for r in data]
    q1, med, q3 = (float(v) for v in st.quantiles(sus, n=4, method='inclusive'))
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    skew, se_s, kurt, se_k = shape(sus)
    w = stats.shapiro(sus)
    outliers = [s for s in sus if s < lo or s > hi]
    out += ['', '## ตารางที่ 3 คะแนน SUS (0–100, Brooke 1996)', '', '| สถิติ | ค่า |', '|---|---|',
            f'| N | {n} |', f'| Mean | {st.mean(sus):.2f} |', f'| Median | {med:.2f} |', f'| S.D. | {st.stdev(sus):.2f} |',
            f'| Minimum | {min(sus):.1f} |', f'| Maximum | {max(sus):.1f} |', f'| Range | {max(sus) - min(sus):.1f} |',
            f'| Q1 / Q3 / IQR | {q1:.2f} / {q3:.2f} / {iqr:.2f} |',
            f'| ขอบเขต outlier (1.5 × IQR) | {lo:.2f} ถึง {hi:.2f} ({len(outliers)} ค่าอยู่นอกขอบเขต) |',
            f'| Skewness (SE) | {skew:.3f} ({se_s:.3f}) |', f'| Kurtosis (SE) | {kurt:.3f} ({se_k:.3f}) |',
            f"| Shapiro-Wilk | W = {w.statistic:.3f}, p = {w.pvalue:.3f} ({'แจกแจงปกติ' if w.pvalue > .05 else 'ไม่แจกแจงปกติ'}) |"]

    out += ['', '## สรุปรายด้าน', '']
    for cname, k, a, m, sd in summaries:
        ok = 'ผ่านเกณฑ์ 0.70' if a >= .70 else 'ต่ำกว่าเกณฑ์ 0.70 ต้องพิจารณาปรับข้อคำถามก่อนรวมเป็นคะแนนด้าน'
        out.append(f'- {cname} วัดด้วย {k} ข้อ (α = {a:.2f}, {ok}) ค่าเฉลี่ยรวม {m:.2f} (SD = {sd:.2f}) '
                   f'แปลผลอยู่ในระดับ "{level(m)}"')
    report = path.with_name(path.stem + '-descriptive.md')
    report.write_text('\n'.join(out) + '\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main(sys.argv[1])
