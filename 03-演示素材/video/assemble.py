# -*- coding: utf-8 -*-
"""合成：raw webm + 旁白 mp3 → 统一时长分段 → concat → 烧字幕 → 织识-演示视频.mp4"""
import json, pathlib, subprocess, sys
from scenes import SCENES

FF = '/opt/homebrew/bin/ffmpeg'
FP = '/opt/homebrew/bin/ffprobe'
MAXSPEED = {  # 每场景最大加速倍率（旁白短、画面长时压缩）
    's00': 1.5, 's02': 1.6, 's03': 2.0, 's04': 1.7, 's05': 1.5, 's06': 1.6,
    's07': 1.1, 's08': 1.2, 's09': 1.4, 's12': 2.0, 's13': 1.0, 's14': 1.0,
}

def dur(p):
    return float(subprocess.run([FP, '-v', 'quiet', '-show_entries', 'format=duration',
        '-of', 'csv=p=0', str(p)], capture_output=True, text=True).stdout.strip())

def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print('FFMPEG FAIL:', r.stderr[-800:]); sys.exit(1)

def main():
    segs, srt, t0 = [], [], 0.0
    pathlib.Path('segs').mkdir(exist_ok=True)
    for s in SCENES:
        sid = s['id']
        dv = dur(f'raw/{sid}.webm')
        da = dur(f'audio/{sid}.mp3')
        base = da + 0.8
        cap = MAXSPEED.get(sid, 1.6)
        speed = 1.0 if dv <= base else min(dv / base, cap)
        T = dv / speed if dv / speed > base else base
        seg = f'segs/{sid}.mp4'
        vchain = f'scale=1440:900:force_original_aspect_ratio=decrease,pad=1440:900:(ow-iw)/2:(oh-ih)/2:color=0x0b0e14,fps=30,setsar=1'
        if speed > 1.001:
            vchain = f'setpts={1/speed:.4f}*PTS,' + vchain
        else:
            vchain = vchain + f',tpad=stop_mode=clone:stop_duration={max(T - dv, 0):.2f}'
        run([FF, '-y', '-i', f'raw/{sid}.webm', '-i', f'audio/{sid}.mp3',
             '-filter_complex', f'[0:v]{vchain}[v];[1:a]aresample=44100,apad,atrim=0:{T:.2f}[a]',
             '-map', '[v]', '-map', '[a]', '-t', f'{T:.2f}',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-ac', '2', seg])
        segs.append(seg)
        for c in json.load(open(f'subs/{sid}.json')):
            srt.append((t0 + c[0], t0 + min(c[1], T - 0.05), c[2]))
        print(f'{sid}: video={dv:.1f}s audio={da:.1f}s speed={speed:.2f} T={T:.1f}s start={t0:.1f}s', flush=True)
        t0 += T
    with open('concat.txt', 'w') as f:
        f.writelines(f"file '{p}'\n" for p in segs)
    run([FF, '-y', '-f', 'concat', '-safe', '0', '-i', 'concat.txt', '-c', 'copy', 'nosubs.mp4'])
    with open('final.srt', 'w') as f:
        for i, (a, b, t) in enumerate(srt, 1):
            f.write(f"{i}\n{fmt(a)} --> {fmt(b)}\n{t}\n\n")
    print(f'total {t0:.1f}s, {len(srt)} subtitle cues', flush=True)

def fmt(t):
    ms = int(round(t * 1000))
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'

if __name__ == '__main__':
    main()
