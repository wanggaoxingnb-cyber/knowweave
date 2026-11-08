# -*- coding: utf-8 -*-
"""逐场景无头录屏：raw/{scene_id}.webm。用法: record.py [s00 s03 ...]"""
import asyncio, pathlib, shutil, sys, tempfile
from playwright.async_api import async_playwright
from scenes import SCENES, BASE

CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;width:16px;height:16px;border:2.5px solid #ff5252;border-radius:50%;background:rgba(255,82,82,.25);z-index:999999;pointer-events:none;transform:translate(-50%,-50%);left:-100px;top:-100px';
  document.body.appendChild(c);
  addEventListener('mousemove', e => { c.style.left = e.clientX+'px'; c.style.top = e.clientY+'px'; }, true);
  addEventListener('mousedown', () => { c.style.boxShadow='0 0 0 8px rgba(255,82,82,.25)'; c.style.background='rgba(255,82,82,.55)'; }, true);
  addEventListener('mouseup', () => { c.style.boxShadow='none'; c.style.background='rgba(255,82,82,.25)'; }, true);
});
"""

async def main(ids):
    out = pathlib.Path('raw'); out.mkdir(exist_ok=True)
    todo = [s for s in SCENES if s['action'] and (not ids or s['id'] in ids)]
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True)
        for s in todo:
            tmp = tempfile.mkdtemp(prefix='rec_')
            try:
                ctx = await browser.new_context(
                    viewport={'width': 1440, 'height': 900},
                    record_video_dir=tmp, record_video_size={'width': 1440, 'height': 900})
                await ctx.add_init_script(CURSOR_JS)
                page = await ctx.new_page()
                print(f"[{s['id']}] recording...", flush=True)
                if s['id'] != 's11':
                    await page.goto(BASE, wait_until='load')
                    await page.wait_for_timeout(800)
                try:
                    await s['action'](page)
                except Exception as e:
                    print(f"[{s['id']}] ACTION ERROR: {e}", flush=True)
                await page.wait_for_timeout(600)
                await ctx.close()
                vids = list(pathlib.Path(tmp).glob('*.webm'))
                if vids:
                    shutil.move(str(vids[0]), out / f"{s['id']}.webm")
                    print(f"[{s['id']}] saved raw/{s['id']}.webm", flush=True)
                else:
                    print(f"[{s['id']}] NO VIDEO PRODUCED", flush=True)
            except Exception as e:
                print(f"[{s['id']}] SCENE FAILED: {e}", flush=True)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
