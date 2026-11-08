import asyncio, pathlib, shutil, tempfile
from playwright.async_api import async_playwright

async def main():
    tmp = tempfile.mkdtemp(prefix='rec_')
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome', headless=True)
        ctx = await b.new_context(viewport={'width':1440,'height':900},
                                  record_video_dir=tmp, record_video_size={'width':1440,'height':900})
        pg = await ctx.new_page()
        await pg.goto('file://' + str(pathlib.Path('endboard.html').resolve()))
        await pg.wait_for_timeout(9500)
        await ctx.close()
        await b.close()
    shutil.move(str(list(pathlib.Path(tmp).glob('*.webm'))[0]), 'raw/s14.webm')
    shutil.rmtree(tmp, ignore_errors=True)
    print('s14 saved')

asyncio.run(main())
