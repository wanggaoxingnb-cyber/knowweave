# -*- coding: utf-8 -*-
"""无 libass 方案：PIL 渲染字幕 PNG + ffmpeg overlay 链烧录。系统 python3 跑。"""
import pathlib, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1440, 900
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
FFMPEG = '/opt/homebrew/bin/ffmpeg'

def parse_srt(path):
    cues = []
    for block in re.split(r'\n\s*\n', open(path).read().strip()):
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        m = re.match(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)', lines[1])
        a = int(m[1])*3600+int(m[2])*60+int(m[3])+int(m[4])/1000
        b = int(m[5])*3600+int(m[6])*int(0)+int(m[6])*60+int(m[7])+int(m[8])/1000
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

def main():
    cues = parse_srt('final.srt')
    pdir = pathlib.Path('subpng'); pdir.mkdir(exist_ok=True)
    for i, (_, _, t) in enumerate(cues):
        p = pdir / f'{i:03d}.png'
        if not p.exists():
            render(t, p)
    cmd = [FFMPEG, '-y', '-i', 'nosubs.mp4']
    for i in range(len(cues)):
        cmd += ['-loop', '1', '-i', str(pdir / f'{i:03d}.png')]
    chain, last = '', '[0:v]'
    for i, (a, b, _) in enumerate(cues):
        nxt = f'[v{i}]'
        chain += f"{last}[{i+1}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'{nxt};"
        last = nxt
    chain = chain.rstrip(';')
    out = '织识-演示视频.mp4'
    cmd += ['-filter_complex', chain, '-map', last, '-map', '0:a',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
            '-c:a', 'copy', '-movflags', '+faststart', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:]); sys.exit(1)
    d = subprocess.run(['/opt/homebrew/bin/ffprobe', '-v', 'quiet', '-show_entries',
                        'format=duration,size', '-of', 'csv=p=0', out], capture_output=True, text=True).stdout.strip()
    print(f'DONE {out} duration,size = {d}')

if __name__ == '__main__':
    main()
