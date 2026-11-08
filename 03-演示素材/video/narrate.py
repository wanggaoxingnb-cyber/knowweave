# -*- coding: utf-8 -*-
"""edge-tts 逐场景旁白 + 句级时间戳 → audio/{id}.mp3, subs/{id}.json。用项目 venv 跑。"""
import asyncio, json, pathlib, re, sys
import edge_tts
from edge_tts import SubMaker
from scenes import SCENES

VOICE = 'zh-CN-YunxiNeural'
MAXLEN = 18  # 单条字幕最长字符数

def split_sentence(text, st, en):
    """长句按标点切成 ≤MAXLEN 的短条，时间按字符数比例分配"""
    parts = [p for p in re.split(r'(?<=[，。？；：！、])', text) if p.strip()]
    chunks, buf = [], ''
    for p in parts:
        if buf and len(buf) + len(p) > MAXLEN:
            chunks.append(buf); buf = p
        else:
            buf += p
    if buf:
        chunks.append(buf)
    if len(chunks) <= 1:
        return [[round(st, 2), round(en, 2), text.strip()]]
    total = sum(len(c) for c in chunks)
    cues, cur = [], st
    for i, c in enumerate(chunks):
        nxt = en if i == len(chunks) - 1 else cur + (en - st) * len(c) / total
        cues.append([round(cur, 2), round(nxt, 2), c.strip()])
        cur = nxt
    return cues

async def gen(scene):
    mp3 = pathlib.Path('audio') / f"{scene['id']}.mp3"
    comm = edge_tts.Communicate(scene['narration'], VOICE, rate='+4%')
    sub = SubMaker()
    with open(mp3, 'wb') as f:
        async for chunk in comm.stream():
            if chunk['type'] == 'audio':
                f.write(chunk['data'])
            elif chunk['type'] == 'SentenceBoundary':
                sub.feed(chunk)
    cues = []
    for c in sub.cues:
        cues.extend(split_sentence(c.content, c.start.total_seconds(), c.end.total_seconds()))
    if not cues:  # 保底：整段一句
        cues = [[0.1, 5.0, scene['narration']]]
    pathlib.Path('subs').mkdir(exist_ok=True)
    json.dump(cues, open(pathlib.Path('subs') / f"{scene['id']}.json", 'w'), ensure_ascii=False, indent=1)
    print(f"{scene['id']}: {len(cues)} cues, end={cues[-1][1]}", flush=True)

async def main(ids):
    pathlib.Path('audio').mkdir(exist_ok=True)
    for s in SCENES:
        if ids and s['id'] not in ids:
            continue
        await gen(s)

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
