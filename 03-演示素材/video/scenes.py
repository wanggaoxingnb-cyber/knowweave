# -*- coding: utf-8 -*-
"""织识演示视频：场景定义（旁白 + 录屏动作）"""
BASE = 'http://127.0.0.1:8000'
MEMORY_DIR = '/Users/w.g.x/Desktop/织识/02-产品Demo/memory/concepts/'

async def wait_idle(page, timeout=180000):
    try:
        await page.wait_for_selector('#status', state='visible', timeout=4000)
    except Exception:
        pass
    try:
        await page.wait_for_selector('#status', state='hidden', timeout=timeout)
    except Exception:
        pass
    await page.wait_for_timeout(800)

async def say(page, text):
    await page.click('#chatInput')
    await page.type('#chatInput', text, delay=45)
    await page.wait_for_timeout(300)
    await page.keyboard.press('Enter')

async def stage_scroll(page, times=3, pause=900):
    for _ in range(times):
        await page.evaluate("() => { const s = document.getElementById('stage'); if (s) s.scrollTop += 220; }")
        await page.wait_for_timeout(pause)

async def s0(page):
    await page.wait_for_timeout(1200)
    await page.click('header button:has-text("知识图谱")')
    await page.wait_for_timeout(4500)
    await page.click('#graphOverlay .x-btn')
    await page.hover('#chatInput')
    await page.wait_for_timeout(1200)

async def s1(page):
    await page.click('#chatInput')
    await page.fill('#chatInput', 'https://sspai.com/post/101529')
    await page.wait_for_timeout(500)
    await page.type('#chatInput', ' 先存着', delay=60)
    await page.keyboard.press('Enter')
    await wait_idle(page, 60000)
    await page.hover('header button:has-text("待学习")')
    await page.wait_for_timeout(1500)

async def s2(page):
    await page.click('header button:has-text("待学习")')
    await page.wait_for_selector('.inbox-item', timeout=10000)
    await page.wait_for_timeout(800)
    await page.click('.inbox-item button:has-text("听个大概")')
    await wait_idle(page, 120000)
    await page.wait_for_timeout(2500)

async def s3(page):
    await page.click('header button:has-text("待学习")')
    await page.wait_for_selector('.inbox-item', timeout=10000)
    await page.wait_for_timeout(800)
    await page.click('.inbox-item button:has-text("开始学")')
    await wait_idle(page, 240000)
    await stage_scroll(page, 4, 800)

async def s4(page):
    await say(page, '灰度测试是啥')
    await wait_idle(page, 90000)
    try:
        await page.hover('#stage .card .section >> nth=1')
    except Exception:
        pass
    await page.wait_for_timeout(2500)

async def s5(page):
    await say(page, '考考我 Attention')
    await wait_idle(page, 90000)
    await page.wait_for_selector('.quiz-item', timeout=30000)
    items = await page.query_selector_all('.quiz-item')
    await page.wait_for_timeout(800)
    await page.click('#qa-1')
    await page.type('#qa-1', '就是让模型更专注一点？', delay=55)
    await page.click('.quiz-item >> nth=0 >> button:has-text("提交")')
    await page.wait_for_selector('#qf-1:not(:empty)', timeout=60000)
    await page.wait_for_timeout(2000)
    if len(items) > 1:
        ref = await page.input_value('#qr-2')
        await page.click('#qa-2')
        await page.type('#qa-2', ref[:80], delay=14)
        await page.click('.quiz-item >> nth=1 >> button:has-text("提交")')
        await page.wait_for_selector('#qf-2:not(:empty)', timeout=60000)
        await page.wait_for_timeout(2200)
    else:
        ref = await page.input_value('#qr-1')
        await page.fill('#qa-1', '')
        await page.type('#qa-1', ref[:80], delay=14)
        await page.click('.quiz-item >> nth=0 >> button:has-text("提交")')
        await page.wait_for_timeout(4000)

async def s6(page):
    await say(page, '我想系统学 LLM 原理')
    await wait_idle(page, 120000)
    await stage_scroll(page, 3, 900)
    await page.wait_for_timeout(1000)

async def s7(page):
    await say(page, 'Attention 太难懂了，画给我看')
    await wait_idle(page, 200000)
    await page.wait_for_timeout(1500)
    await page.mouse.move(1050, 450, steps=15)
    await page.wait_for_timeout(2000)

async def s8(page):
    await say(page, 'RAG 跟幻觉什么关系')
    await wait_idle(page, 90000)
    await page.click('header button:has-text("知识图谱")')
    await page.wait_for_timeout(4200)
    await page.click('#graphOverlay .x-btn')
    await page.wait_for_timeout(600)

async def s9(page):
    await page.click('header button:has-text("知识图谱")')
    await page.wait_for_timeout(3800)
    pos = await page.evaluate("""() => {
      const ps = network.getPositions();
      const keys = Object.keys(ps);
      const id = keys.find(k => k.includes('Attention')) || keys[0];
      const dom = network.canvasToDOM(ps[id]);
      return {x: dom.x, y: dom.y};
    }""")
    await page.mouse.move(pos['x'], pos['y'], steps=15)
    await page.wait_for_timeout(300)
    await page.mouse.click(pos['x'], pos['y'])
    try:
        await page.wait_for_selector('#graphDetail', state='visible', timeout=8000)
    except Exception:
        pass
    await page.wait_for_timeout(2800)
    await page.click('#graphOverlay .x-btn')

async def s10(page):
    await page.click('header button:has-text("它眼中的你")')
    await page.wait_for_timeout(1500)
    await page.evaluate("() => { const b = document.getElementById('profileBody'); if (b) b.scrollTop += 160; }")
    await page.wait_for_timeout(1200)
    await page.click('#profileEditBtn')
    await page.wait_for_timeout(1500)
    await page.click('#profileModal .x-btn')
    await page.wait_for_timeout(500)

async def s11(page):
    await page.goto('file://' + MEMORY_DIR)
    await page.wait_for_timeout(1800)
    try:
        await page.click('text=Attention.md', timeout=5000)
        await page.wait_for_timeout(2500)
        await page.mouse.wheel(0, 300)
        await page.wait_for_timeout(1200)
    except Exception:
        await page.wait_for_timeout(2000)

async def s12(page):
    await say(page, '把最近学的写成文章')
    await wait_idle(page, 120000)
    await stage_scroll(page, 4, 800)

async def s13(page):
    await page.click('header button:has-text("待学习")')
    await page.wait_for_timeout(1800)
    await page.click('#inboxDrawer .x-btn')
    await page.wait_for_timeout(600)
    await page.click('header button:has-text("知识图谱")')
    await page.wait_for_timeout(3500)
    await page.click('#graphOverlay .x-btn')
    await page.wait_for_timeout(500)

SCENES = [
    dict(id='s00', narration='这是我用了一周的织识。别急，先看它到底记住了我什么。', action=s0),
    dict(id='s01', narration='通勤路上刷到一篇好文章，没空读？丢个链接，说声先存着，它抓正文、留一句种草点，十秒进待学习区，不打断通勤。', action=s1),
    dict(id='s02', narration='午休只有五分钟？点听个大概，它只做一段六十秒的播客，耳朵先学起来。', action=s2),
    dict(id='s03', narration='晚上有了整块时间，点开始学，导读、概念卡、检验题、播客，一个学习页全给齐。', action=s3),
    dict(id='s04', narration='看这张概念卡，它知道我喜欢打游戏，就用英雄联盟新英雄先上测试服，给我讲灰度测试。', action=s4),
    dict(id='s05', narration='学没学会，它来验。答错不要紧，它当场讲评；答对一题，掌握度就往上涨一档。', action=s5),
    dict(id='s06', narration='想系统学一个东西？直接说我要系统学 LLM 原理，它读我的图谱和画像，把先学哪几个、为什么，排成一条路。', action=s6),
    dict(id='s07', narration='Transformer 看三遍没懂？说一句画给我看，它现场生成一份能点的图解；画过的第二次直接秒开。', action=s7),
    dict(id='s08', narration='学的东西最怕各看各的。我就问 RAG 跟幻觉什么关系，它不光讲清楚，还在记忆里织了一条边，图谱黄点一闪，连起来了。', action=s8),
    dict(id='s09', narration='周末看看这周学了啥。图谱一开，十几个节点，颜色就是掌握度，灰的是刚认识，绿的是能讲给别人。点开节点，还能一键再考自己。', action=s9),
    dict(id='s10', narration='它记得我是谁。它眼中的你里，身份、行业、熟悉领域，还有最近聊出来的信号，全透明，随时能改能删。', action=s10),
    dict(id='s11', narration='更关键的是，这份记忆不是黑盒，就是本地一堆 Markdown 文件，能看、能改、能拷走，不上传云端。', action=s11),
    dict(id='s12', narration='学懂了的东西还能变成资产：把我最近学的写成文章，素材全来自我的概念卡和当时的疑问。越学，弹药越多。', action=s12),
    dict(id='s13', narration='用了一周最明显的变化：收藏不再吃灰，待学习区一条一条变少；图谱从几个节点长成一张网；掌握度一点一点变绿。它真的记得我学过什么，也知道我是谁。', action=s13),
    dict(id='s14', narration='织识 KnowWeave，记得你学过什么、也知道你是谁。我是王宁，一个用 Codex 做出这个产品的产品经理。', action=None),
]
