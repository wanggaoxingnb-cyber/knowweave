# -*- coding: utf-8 -*-
"""极简 md→html→PDF（headless Chrome 打印）。只支持本计划书用到的语法。"""
import html, re, subprocess, sys

def inline(t):
    t = html.escape(t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)
    return t

def convert(md):
    lines, out, i = md.split('\n'), [], 0
    buf_list = None
    def flush_list():
        nonlocal buf_list
        if buf_list:
            lines_out = ''.join(f'<li>{inline(x)}</li>' for x in buf_list[1])
            lines.append  # noop
            out.append(f'<{buf_list[0]}>{lines_out}</{buf_list[0]}>')
            buf_list = None
    out = []
    rows = []
    def flush_table():
        nonlocal rows
        if rows:
            body = ''
            for j, r in enumerate(rows):
                cells = ''.join(f'<{"th" if j==0 else "td"}>{inline(c.strip())}</{"th" if j==0 else "td"}>' for c in r)
                body += f'<tr>{cells}</tr>'
            out.append(f'<table>{body}</table>')
            rows = []
    while i < len(lines):
        l = lines[i]
        if l.strip().startswith('|'):
            flush_list()
            cells = [c for c in l.strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-{2,}:?', c.strip()) for c in cells):
                rows.append(cells)
            i += 1
            continue
        flush_table()
        if re.match(r'^[-*] ', l.strip()):
            if not buf_list or buf_list[0] != 'ul':
                flush_list(); buf_list = ('ul', [])
            buf_list[1].append(l.strip()[2:])
        elif re.match(r'^\d+\. ', l.strip()):
            if not buf_list or buf_list[0] != 'ol':
                flush_list(); buf_list = ('ol', [])
            buf_list[1].append(re.sub(r'^\d+\. ', '', l.strip()))
        else:
            flush_list()
            if l.startswith('# '):
                out.append(f'<h1>{inline(l[2:])}</h1>')
            elif l.startswith('## '):
                out.append(f'<h2>{inline(l[3:])}</h2>')
            elif l.startswith('### '):
                out.append(f'<h3>{inline(l[4:])}</h3>')
            elif l.startswith('> '):
                out.append(f'<blockquote>{inline(l[2:])}</blockquote>')
            elif l.strip() == '---':
                out.append('<hr>')
            elif l.strip():
                out.append(f'<p>{inline(l)}</p>')
        i += 1
    flush_list(); flush_table()
    return '\n'.join(out)

CSS = '''
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "PingFang SC", "Hiragino Sans GB", sans-serif; color:#1a1a2e; font-size:10.5pt; line-height:1.75; }
h1 { font-size:20pt; color:#0f2a4a; border-bottom:3px solid #3b82f6; padding-bottom:8px; }
h2 { font-size:14pt; color:#0f2a4a; border-left:4px solid #3b82f6; padding-left:10px; margin-top:1.4em; page-break-after: avoid; }
h3 { font-size:12pt; }
blockquote { color:#666; border-left:3px solid #ccc; margin:0; padding:2px 12px; font-size:9.5pt; }
table { border-collapse:collapse; width:100%; font-size:9pt; margin:10px 0; }
th,td { border:1px solid #bbb; padding:5px 8px; text-align:left; vertical-align:top; }
th { background:#eef4ff; }
code { background:#f2f4f8; padding:1px 4px; border-radius:3px; font-size:9pt; }
hr { border:none; border-top:1px dashed #ccc; margin:18px 0; }
b { color:#0f2a4a; }
'''

src = open(sys.argv[1]).read()
body = convert(src)
open('计划书.html', 'w').write(
    f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{convert(src)}</body></html>')
subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--headless',
                '--disable-gpu', '--no-pdf-header-footer',
                '--print-to-pdf=织识-商业计划书.pdf', '计划书.html'], check=True, capture_output=True)
print('PDF done')
