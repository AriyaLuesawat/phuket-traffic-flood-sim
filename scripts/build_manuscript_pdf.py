"""Builds manuscript/manuscript-th.pdf from manuscript/manuscript-th.md with headless Chrome.

    .venv/bin/python scripts/build_manuscript_pdf.py        (needs the `markdown` package and Google Chrome)

Layout rules: nothing is split across pages if it fits on one. A table stays with its caption, a figure
with its caption, a heading with the block after it, and a lead-in line ending in ":" with its list.
When such a group does not fit in the space left, it moves to the next page. URLs are made clickable and
ligatures are off so copied links stay correct.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'manuscript' / 'manuscript-th.md'
OUT = ROOT / 'manuscript' / 'manuscript-th.pdf'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FONTS = ROOT / 'fonts'

CSS = f'''
@font-face {{ font-family: 'IBM Plex Sans Thai'; font-weight: 400; src: url('file://{FONTS}/IBMPlexSansThai-Regular.ttf'); }}
@font-face {{ font-family: 'IBM Plex Sans Thai'; font-weight: 600; src: url('file://{FONTS}/IBMPlexSansThai-SemiBold.ttf'); }}
@font-face {{ font-family: 'IBM Plex Sans Thai'; font-weight: 700; src: url('file://{FONTS}/IBMPlexSansThai-Bold.ttf'); }}
@page {{ size: A4; margin: 2.2cm 2cm; }}
body {{ font-family: 'IBM Plex Sans Thai', sans-serif; font-size: 10.5pt; line-height: 1.65; color: #111;
        font-variant-ligatures: none; font-feature-settings: 'liga' 0, 'clig' 0; }}
h1 {{ font-size: 17pt; line-height: 1.35; margin: 0 0 .6em; }}
h2 {{ font-size: 13.5pt; margin: 1.4em 0 .5em; border-bottom: 1px solid #bbb; }}
h3 {{ font-size: 11.5pt; margin: 1.1em 0 .4em; }}
h1, h2, h3 {{ break-after: avoid; page-break-after: avoid; }}
p, li {{ text-align: left; orphans: 3; widows: 3; }}
li, blockquote, pre, tr, img {{ break-inside: avoid; page-break-inside: avoid; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: .4em 0 .8em; break-inside: avoid; page-break-inside: avoid; }}
th, td {{ border: 1px solid #999; padding: 3px 5px; vertical-align: top; }}
th {{ background: #eee; }}
code {{ font-size: 8.5pt; background: #f3f3f3; padding: 0 2px; }}
blockquote {{ color: #444; border-left: 3px solid #ccc; margin: .6em 0; padding-left: .8em; }}
a {{ color: #111; word-break: break-all; }}
img {{ display: block; max-width: 100%; max-height: 19cm; margin: .8em auto .2em; }}
.keep {{ break-inside: avoid; page-break-inside: avoid; }}
.keep > :last-child {{ margin-bottom: .8em; }}
.refs p {{ break-inside: avoid; page-break-inside: avoid; padding-left: 2em; text-indent: -2em; margin: .35em 0; }}
'''

BLOCK = r'(?:<div class="keep">.*?</div>|<p>.*?</p>|<ul>.*?</ul>|<ol>.*?</ol>|<blockquote>.*?</blockquote>|<table>.*?</table>)'


def keep(html: str, pattern: str) -> str:
    return re.sub(pattern, lambda m: f'<div class="keep">{m.group(0)}</div>', html, flags=re.S)


def layout(html: str) -> str:
    # caption + table (+ a source note that starts with "ที่มา")
    html = keep(html, r'<p><strong>ตารางที่ \d+</strong>.*?</p>\s*<table>.*?</table>(?:\s*<p>ที่มา.*?</p>)?')
    # figure + caption
    html = keep(html, r'<p><img [^>]*></p>\s*<p><strong>รูปที่ \d+</strong>.*?</p>')
    # lead-in paragraph ending with ":" + the list it introduces
    html = keep(html, r'<p>(?:(?!</p>).)*:(?:</strong>)?</p>\s*(?:<ul>.*?</ul>|<ol>.*?</ol>)')
    # heading + first block after it
    html = keep(html, rf'<h[23]>.*?</h[23]>\s*{BLOCK}')
    # hanging-indent reference list
    head, sep, refs = html.partition('<h2>เอกสารอ้างอิง</h2>')
    return head + sep + (f'<div class="refs">{refs}</div>' if sep else '')


def main() -> None:
    src = SRC.read_text(encoding='utf-8').replace('](../docs/img/', f'](file://{ROOT}/docs/img/')
    src = re.sub(r'(?<![(<\]])(https?://[^\s<>()]+[^\s<>().,])', r'<\1>', src)
    body = layout(markdown.markdown(src, extensions=['tables']))
    page = (f'<!doctype html><html lang="th"><head><meta charset="utf-8"><title>Manuscript</title>'
            f'<style>{CSS}</style></head><body>{body}</body></html>')
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / 'manuscript.html'
        html.write_text(page, encoding='utf-8')
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
                        '--no-pdf-header-footer', f'--print-to-pdf={OUT}', html.as_uri()],
                       check=True, capture_output=True)
        if len(sys.argv) > 1:  # keep the HTML for inspection
            Path(sys.argv[1]).write_text(page, encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    main()
