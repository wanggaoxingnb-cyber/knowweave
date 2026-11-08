# -*- coding: utf-8 -*-
"""分段并行烧字幕：4 段并行 + 字幕 PNG 仅在显示窗口解码。"""
import pathlib, re, subprocess, sys, concurrent.futures as cf
from PIL import Image, ImageDraw, ImageFont

W, H = 1440, 900
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
FFMPEG = '/opt/homebrew/bin/ffmpeg'
CHUNKS = [(0.0, 38.9), (38.9, 79.0), (79.0, 125.2), (125.2, 160.0)]

def parse_srt(path):
    cues = []
    for block in re.split(r'\n\s*\n', open(path).read().strip()):
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        m = re.match(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)', lines[1])
        a = int(m[1])*3600+int(m[2])*60+int(m[3])+int(m[4])/1000
        b = int(m[5])*3600+int(m[6])*60+int(m[7])+int(m[8])/1000
        cues.append((a, b, ' '.join(lines[2:])))
    return cues

def render(text, out):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 40)
    box = d.textbbox((0, 0), text, font=f, stroke_width=2)
    tw, th = box[2]-box[0], box[3]-box[1]
    d.text(((W-tw)/2, H-110-th), text, font=f, fill=(255, 255, 255, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 200))
    img.save(out)

def burn_chunk(idx, cs, ce, cues):
    mine = [(a, b, t) for a, b, t in cues if a >= cs - 0.01 and a < ce - 0.01]
    pdir = pathlib.Path('subpng')
    cmd = [FFMPEG, '-y', '-ss', f'{cs}', '-t', f'{ce-cs}', '-i', 'nosubs.mp4', '-threads', '3']
    parts, last = [], '[0:v]'
    for j, (a, b, t) in enumerate(mine):
        p = pdir / f'c{idx}_{j:02d}.png'
        if not p.exists():
            render(t, p)
        cmd += ['-loop', '1', '-t', f'{b-a+0.1}', '-i', str(p)]
        a0, b0 = a - cs, b - cs
        parts.append(f'[{j+1}:v]setpts=PTS+{a0:.2f}/TB[p{j}];{last}[p{j}]overlay=0:0:eof_action=pass:enable=between(t\\,{a0:.2f}\\,{b0:.2f})[v{j}]')
        last = f'[v{j}]'
    out = f'segs/chunk{idx}.mp4'
    if parts:
        cmd += ['-filter_complex', ';'.join(parts), '-map', last, '-map', '0:a']
    else:
        cmd += ['-map', '0:v', '-map', '0:a']
    cmd += ['-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-r', '30', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return f'chunk{idx} FAIL: ' + r.stderr[-500:]
    return f'chunk{idx} ok ({len(mine)} cues)'

def main():
    cues = parse_srt('final.srt')
    with cf.ThreadPoolExecutor(4) as ex:
        for msg in ex.map(lambda i: burn_chunk(i, *CHUNKS[i], cues), range(4)):
            print(msg, flush=True)
    with open('concat2.txt', 'w') as f:
        f.writelines(f"file 'segs/chunk{i}.mp4'\n" for i in range(4))
    r = subprocess.run([FFMPEG, '-y', '-f', 'concat', '-safe', '0', '-i', 'concat2.txt',
                        '-c', 'copy', '-movflags', '+faststart', '织识-演示视频.mp4'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:]); sys.exit(1)
    print('FINAL DONE')

if __name__ == '__main__':
    main()
