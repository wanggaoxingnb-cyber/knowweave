"""织识 KnowWeave — FastAPI 单页应用。运行：.venv/bin/python -m app.main"""
from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import brain, memory

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-YunxiNeural")

app = FastAPI(title="织识 KnowWeave")


# ---------- 工具 ----------

async def _tts(text: str) -> str | None:
    """edge-tts 生成播客音频，返回 /api/audio/xxx.mp3 路径；失败返回 None。"""
    if not text:
        return None
    name = hashlib.md5((text + TTS_VOICE).encode()).hexdigest()[:16] + ".mp3"
    path = AUDIO_DIR / name
    if not path.exists():
        try:
            import edge_tts
            await edge_tts.Communicate(text, TTS_VOICE).save(str(path))
        except Exception as e:
            print(f"[tts] failed: {e}")
            return None
    return f"/api/audio/{name}"


def _ocr_image(data: bytes) -> str:
    """macOS Vision OCR（截图取字），失败返回空串。"""
    swift = ROOT / "app" / "ocr.swift"
    if not swift.exists():
        return ""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        out = subprocess.run(["swift", str(swift), tmp_path],
                             capture_output=True, text=True, timeout=120)
        return out.stdout.strip()
    except Exception as e:
        print(f"[ocr] failed: {e}")
        return ""
    finally:
        os.unlink(tmp_path)


def _pdf_text(data: bytes) -> str:
    import pymupdf
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


# ---------- 核心链路 ----------

def _ask_pipeline(question: str) -> dict:
    profile = memory.load_profile()
    related = memory.search_related(question)
    events = []

    if brain.available():
        result = brain.answer_question(question, profile, related)
    else:
        result = _mock_answer(question, related)

    concept_name = result.get("concept", question[:20])
    save_result = memory.save_concept(
        concept_name,
        explanation=result.get("explanation", ""),
        question=question,
        hook=result.get("hook", ""),
        related=result.get("related", []),
    )
    events.append(("新建概念" if save_result["created"] else "更新概念") + f"「{concept_name}」")
    if save_result["mastery_up"]:
        events.append(f"「{concept_name}」掌握度提升到 {save_result['meta']['掌握度']}")

    # 防混提示命中的旧概念也高亮
    highlight = [concept_name]
    for c in related:
        if c["名称"] in (result.get("warning", "") + result.get("explanation", "")):
            highlight.append(c["名称"])

    memory.append_history(question, highlight, result.get("hook", ""))
    return {
        "card": result,
        "learned_before": [c["名称"] for c in related],
        "memory_events": events,
        "highlight": list(dict.fromkeys(highlight)),
        "mock": not brain.available(),
    }


MOCK_ANSWERS = {
    "回归测试": {
        "concept": "回归测试",
        "explanation": "回归测试就是：代码改了之后，把以前的测试再跑一遍，确认老功能没被改坏。就像装修完新房，要检查原来的水电还能不能用。",
        "analogy": "像英雄联盟版本更新：新英雄上线了，策划要确认老英雄技能没被改坏，亚索的E还能不能正常位移，这就是回归测试。",
        "hook": "改完代码，回头再测一遍老的。",
        "warning": "别和自回归模型混：自回归是 AI 按顺序一个词一个词生成文本，跟软件测试没关系。",
        "podcast_script": "今天聊聊回归测试。简单说，就是代码改了以后，把以前的测试重新跑一遍，看老功能有没有被改坏。打个你熟悉的比方：英雄联盟每次版本更新上了新英雄，团队都得确认老英雄的技能没被影响，亚索的E还能不能正常用。这个回头检查的动作，就是回归测试。记住一句话：改完代码，回头再测一遍老的。",
        "related": ["自回归模型", "冒烟测试", "测试用例"],
    },
    "灰度测试": {
        "concept": "灰度测试",
        "explanation": "灰度测试是上线前的小范围试水：先放给一小部分用户用新版本，没问题再逐步放大到全部用户，降低翻车风险。",
        "analogy": "英雄联盟出新英雄，不会一上来全服开放，而是先在测试服或部分大区灰度上线，收集反馈、修完 bug 再全量推送。",
        "hook": "先小范围试水，没问题再全量。",
        "warning": "",
        "podcast_script": "今天聊灰度测试。它指的是新版本上线前，先放给一小部分用户试用，确认没问题再推到全部用户。你打英雄联盟肯定熟：新英雄不会直接全服上线，先测试服、再部分大区，收集反馈修 bug，最后才全量。这就是灰度。一句话记住：先小范围试水，没问题再全量。",
        "related": ["回归测试", "验收测试"],
    },
}


def _mock_answer(question: str, related: list[dict]) -> dict:
    for key, value in MOCK_ANSWERS.items():
        if key in question:
            return value
    return {
        "concept": question[:10],
        "explanation": "（mock 模式：未配置 LLM key，这是占位回答）",
        "analogy": "", "hook": "", "warning": "",
        "podcast_script": "", "related": [],
    }


# ---------- 路由 ----------

@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/api/ask")
async def ask(payload: dict):
    question = payload.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)
    result = _ask_pipeline(question)
    result["audio_url"] = await _tts(result["card"].get("podcast_script", ""))
    return result


@app.post("/api/ingest")
async def ingest(text: str = Form(""), file: UploadFile | None = File(None)):
    raw = text.strip()
    title_hint = "粘贴文本"
    if file is not None:
        data = await file.read()
        title_hint = file.filename or "上传文件"
        suffix = Path(title_hint).suffix.lower()
        if suffix == ".pdf":
            raw = _pdf_text(data)
        elif suffix in (".png", ".jpg", ".jpeg", ".webp"):
            raw = _ocr_image(data)
        else:
            raw = data.decode("utf-8", errors="ignore")
    if not raw:
        return JSONResponse({"error": "没有读到内容（截图识别失败请改粘贴文本）"}, status_code=400)

    events = []
    if brain.available():
        result = brain.build_learning_page(title_hint, raw, memory.load_profile())
        cards = []
        for item in result.get("concepts", [])[:3]:
            save_result = memory.save_concept(
                item.get("name", "未命名概念"),
                explanation=item.get("explanation", ""),
                hook=item.get("hook", ""),
                source=title_hint,
                related=item.get("related", []),
            )
            events.append(("新建概念" if save_result["created"] else "更新概念") + f"「{item.get('name')}」")
            cards.append(item)
        memory.append_history(f"[资料入库] {title_hint}", [c.get("name", "") for c in cards], result.get("summary", ""))
        return {"summary": result.get("summary", ""),
                "walkthrough": result.get("walkthrough", []),
                "cards": cards,
                "quiz": result.get("quiz", []),
                "memory_events": events,
                "highlight": [c.get("name", "") for c in cards],
                "audio_url": await _tts(result.get("podcast_script", "")),
                "mock": False}
    memory.append_history(f"[资料入库-mock] {title_hint}", [], raw[:100])
    return {"summary": "（mock 模式：未配置 LLM key，仅留痕）", "walkthrough": [], "cards": [],
            "quiz": [], "memory_events": events, "highlight": [], "mock": True}


@app.post("/api/quiz")
async def quiz(payload: dict):
    """考考我：针对已学概念出题。"""
    concept_name = payload.get("concept", "").strip()
    concept = memory.load_concept(concept_name)
    if not concept:
        return JSONResponse({"error": f"概念「{concept_name}」不存在"}, status_code=404)
    if not brain.available():
        return {"questions": [{"q": f"（mock）用自己的话讲讲什么是{concept_name}？", "a": "mock 模式不判题"}]}
    return brain.make_quiz(concept_name, concept["body"], memory.load_profile())


@app.post("/api/quiz/judge")
async def quiz_judge(payload: dict):
    """判题：pass 升掌握度，fail 降一级并换例子重讲。"""
    concept_name = payload.get("concept", "")
    question = payload.get("question", "")
    reference = payload.get("reference", "")
    user_answer = payload.get("answer", "").strip()
    if not user_answer:
        return JSONResponse({"error": "回答不能为空"}, status_code=400)
    if not brain.available():
        return {"pass": True, "feedback": "mock 模式默认通过", "mastery": None}
    result = brain.judge_answer(concept_name, question, reference, user_answer, memory.load_profile())
    passed = bool(result.get("pass"))
    new_mastery = memory.adjust_mastery(concept_name, "up" if passed else "down")
    memory.append_history(f"[考考我] {concept_name}: {question}",
                          [concept_name], ("答对" if passed else "答错"))
    return {"pass": passed, "feedback": result.get("feedback", ""), "mastery": new_mastery}


@app.get("/api/graph")
def graph():
    return memory.graph_data()


@app.get("/api/concepts")
def concepts():
    return {"concepts": [{k: v for k, v in c.items() if k != "body"} for c in memory.list_concepts()]}


@app.get("/api/profile")
def get_profile():
    """它眼中的你：返回用户画像原文（含信号沉淀区）。"""
    return {"profile": memory.load_profile()}


@app.get("/api/audio/{name}")
def audio(name: str):
    path = AUDIO_DIR / Path(name).name
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="audio/mpeg")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


# ==================== v2：统一入口 + 意图路由 ====================

URL_PATTERN = __import__("re").compile(r"https?://[^\s)\]>\"']+")


def _fetch_url_text(url: str) -> str:
    import re as _re
    try:
        import httpx
        resp = httpx.get(url, timeout=20, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        html = resp.text
        html = _re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=_re.S | _re.I)
        html = _re.sub(r"</(p|div|h\d|li|br)>", "\n", html, flags=_re.I)
        text = _re.sub(r"<[^>]+>", "", html)
        text = _re.sub(r"[ \t]+", " ", text)
        return _re.sub(r"\n\s*\n+", "\n", text).strip()
    except Exception as e:
        print(f"[fetch] failed: {e}")
        return ""


async def _learn_pipeline_v2(title_hint: str, raw: str) -> dict:
    events, cards = [], []
    result = brain.build_learning_page(title_hint, raw, memory.load_profile())
    for item in result.get("concepts", [])[:3]:
        sr = memory.save_concept(item.get("name", "未命名概念"),
                                 explanation=item.get("explanation", ""),
                                 hook=item.get("hook", ""),
                                 source=title_hint, related=item.get("related", []))
        events.append(("新建概念" if sr["created"] else "更新概念") + f"「{item.get('name')}」")
        cards.append(item)
    memory.append_history(f"[资料入库] {title_hint}", [c.get("name", "") for c in cards], result.get("summary", ""))
    return {"summary": result.get("summary", ""), "walkthrough": result.get("walkthrough", []),
            "cards": cards, "quiz": result.get("quiz", []), "memory_events": events,
            "highlight": [c.get("name", "") for c in cards],
            "audio_url": await _tts(result.get("podcast_script", ""))}


def _graph_brief() -> str:
    return "、".join(f"{c['名称']}({c['掌握度']})" for c in memory.list_concepts()) or "（空）"


def _concepts_brief() -> str:
    parts = []
    for c in memory.list_concepts():
        parts.append(f"【{c['名称']}｜掌握度:{c['掌握度']}】\n{c['body'][:300]}")
    return "\n\n".join(parts)[:5000]


@app.post("/api/chat")
async def chat_v2(text: str = Form(""), files: list[UploadFile] = File(default=[])):
    """统一入口：一个输入框通吃一切，LLM 判断意图。"""
    text = text.strip()
    valid_files = [f for f in files if f.filename]
    url_match = URL_PATTERN.search(text)

    # 只丢图不说话 = 进收件箱（低摩擦收集，不打断）
    if valid_files and not text and all(
            Path(f.filename or "").suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
            for f in valid_files):
        saved = []
        for f in valid_files[:3]:
            data = await f.read()
            stem = memory.add_image_to_inbox(f.filename or "截图", data, _ocr_image(data))
            saved.append(stem)
        n = len(saved)
        return {"type": "save", "reply": f"{n} 张图收进待学习区了 📥 有空点「开始学」或「听个大概」",
                "inbox": memory.list_inbox()}

    # 文件优先：直接走学习
    if valid_files:
        pages, highlight = [], []
        for f in valid_files[:3]:
            data = await f.read()
            suffix = Path(f.filename or "").suffix.lower()
            if suffix == ".pdf":
                raw = _pdf_text(data)
            elif suffix in (".png", ".jpg", ".jpeg", ".webp"):
                raw = _ocr_image(data)
            else:
                raw = data.decode("utf-8", errors="ignore")
            if not raw.strip():
                pages.append({"error": f"「{f.filename}」没读到内容"})
                continue
            page = await _learn_pipeline_v2(f.filename or "上传文件", raw)
            pages.append(page)
            highlight += page.get("highlight", [])
        ok = len([p for p in pages if not p.get("error")])
        return {"type": "learn", "reply": f"学完 {ok} 份资料，学习页放中间了 👉 底部有检验题，敢不敢答",
                "pages": pages, "highlight": highlight}

    if not text:
        return JSONResponse({"error": "说点什么，或者拖个文件/贴个链接"}, status_code=400)

    # LLM 意图路由
    bare_url = url_match and not text.replace(url_match.group(0), "").strip(" ，,。：:")
    if bare_url:
        # 只丢链接不说话 = 先收进待学习区，不用路由猜
        route = {"intent": "save", "signals": [], "concepts": []}
    else:
        route = brain.route_intent(text, has_files=False, has_url=bool(url_match)) if brain.available() \
            else {"intent": "explain", "signals": [], "concepts": []}
    intent = route.get("intent", "explain")
    written = memory.append_profile_signals(route.get("signals", []))
    signal_note = f"（记住了：{written[0]}）" if written else ""
    profile = memory.load_profile()

    # ---- save：待学习缓存区 ----
    if intent == "save":
        if not url_match:
            return {"type": "chat", "reply": "想存东西的话，把链接一起贴给我就行 📥"}
        raw = _fetch_url_text(url_match.group(0))
        if len(raw) < 100:
            return {"type": "chat", "reply": "这个链接抓不到正文（可能要登录/有反爬）。复制正文贴给我也行。"}
        hook = raw[:0]
        if brain.available():
            try:
                hook = brain._extract_json(brain._chat(
                    "用一句话说出这篇资料最值得读的点（30字内），JSON: {\"hook\": \"...\"}", raw[:1500], 200))["hook"]
            except Exception:
                hook = raw[:50]
        title = text.replace(url_match.group(0), "").strip(" ，,。：:")
        if title in ("", "先存着", "存着", "存一下", "收藏", "回头再看", "稍后读", "马住", "mark"):
            title = hook[:20] or url_match.group(0)[:40]
        memory.add_to_inbox(title, url_match.group(0), hook)
        return {"type": "save", "reply": f"已存入待学习区 📥 种草点：{hook}{signal_note}",
                "inbox": memory.list_inbox()}

    # ---- learn：链接学习 ----
    if intent == "learn" and url_match:
        raw = _fetch_url_text(url_match.group(0))
        if len(raw) < 100:
            return {"type": "chat", "reply": "链接抓不到正文，把正文复制贴给我吧。"}
        page = await _learn_pipeline_v2(url_match.group(0), raw)
        return {"type": "learn", "reply": f"学完了，学习页放中间 👉{signal_note}",
                "pages": [page], "highlight": page["highlight"]}

    # ---- weave：编织 ----
    if intent == "weave":
        names = route.get("concepts", [])
        for n in memory.match_concepts_in_text(text):
            if n not in names:
                names.append(n)
        bodies = {"（用户原话）": text}
        for n in names:
            c = memory.load_concept(n)
            bodies[n] = c["body"] if c else "（概念库中还没有，按通用知识讲）"
        if brain.available() and names:
            result = brain.weave_explain(names, profile, bodies)
            new_links = 0
            for pair in result.get("links", []):
                if len(pair) == 2 and memory.add_link(pair[0], pair[1]):
                    new_links += 1
            memory.append_history(f"[编织] {text}", names, result.get("relationship", "")[:60])
            return {"type": "weave", "reply": result.get("relationship", "") + signal_note,
                    "highlight": names,
                    "memory_events": [f"图谱新增 {new_links} 条连线" if new_links else "连线已存在"]}
        return {"type": "chat", "reply": "你想连哪两个概念？再说具体点。"}

    # ---- quiz：检验 ----
    if intent == "quiz":
        concepts = route.get("concepts", []) or memory.match_concepts_in_text(text)
        target = None
        for n in concepts:
            if memory.load_concept(n):
                target = n
                break
        if not target:
            recent = memory.list_concepts()
            if not recent:
                return {"type": "chat", "reply": "概念库还是空的，先学点东西再来考你 😄"}
            target = recent[-1]["名称"]
        concept = memory.load_concept(target)
        quiz_data = brain.make_quiz(target, concept["body"], profile) if brain.available() \
            else {"questions": [{"q": f"用自己的话讲讲{target}？", "a": "mock"}]}
        return {"type": "quiz", "reply": f"来，考考你「{target}」💪 题放中间了，答完我判",
                "quiz": quiz_data.get("questions", []), "concept": target, "highlight": [target]}

    # ---- mentor：导师 ----
    if intent == "mentor":
        topic = route.get("topic") or text
        if brain.available():
            result = brain.mentor_path(topic, profile, _graph_brief())
            memory.append_history(f"[导师] {topic}", [], result.get("goal", ""))
            return {"type": "mentor", "reply": f"路径给你排好了，放中间 🧭 从第一步开始就行{signal_note}",
                    "mentor": result, "topic": topic}
        return {"type": "chat", "reply": "mock 模式不支持导师模式"}

    # ---- create：输出倒逼输出 ----
    if intent == "create":
        if brain.available():
            result = brain.create_article(text, profile, _concepts_brief(), memory.read_history_brief())
            memory.append_history("[输出] 生成文章", [], result.get("title", ""))
            return {"type": "create", "reply": f"原稿写好了，放中间 ✍️{signal_note}",
                    "article": result}
        return {"type": "chat", "reply": "mock 模式不支持输出模块"}

    # ---- visualize：演绎 ----
    if intent == "visualize":
        names = route.get("concepts", []) or memory.match_concepts_in_text(text)
        target = names[0] if names else text[:10]
        concept = memory.load_concept(target)
        cached = memory.load_viz(target)
        if cached:
            return {"type": "visualize", "reply": f"「{target}」的图解之前做过，秒开 🎬",
                    "viz": cached, "highlight": [target]}
        if brain.available():
            result = brain.visualize_concept(target, concept["body"] if concept else "", profile)
            if result.get("html"):
                memory.save_viz(target, result.get("title", target), result["html"])
            return {"type": "visualize", "reply": f"给「{target}」现做了一个图解，中间看 🎬",
                    "viz": result, "highlight": [target]}
        return {"type": "chat", "reply": "mock 模式不支持演绎"}

    # ---- chat：闲聊 ----
    if intent == "chat":
        reply = ""
        if brain.available():
            reply = brain._chat(
                "你是织识 KnowWeave，记得用户学过什么的 AI 学习助手。简短自然地回复（80字内），"
                "可顺势引导学习。用户画像：\n" + profile + "\n已学概念：" + _graph_brief(), text, 200)
        return {"type": "chat", "reply": reply or "我在，说吧。" + signal_note}

    # ---- explain：讲解（默认） ----
    result = _ask_pipeline(text)
    result["audio_url"] = await _tts(result["card"].get("podcast_script", ""))
    result["type"] = "explain"
    result["reply"] = (result["card"].get("explanation", "")[:100] + "… 详细卡片在中间 👉") if result.get("card") else "嗯？"
    if signal_note:
        result["reply"] += signal_note
    return result


@app.get("/api/inbox")
def inbox_list():
    return {"items": memory.list_inbox()}


@app.post("/api/inbox/learn")
async def inbox_learn(payload: dict):
    """待学习区 → 现在学（重新抓取正文走学习页）。"""
    file_stem = payload.get("file", "")
    loaded = memory.load_inbox_item(file_stem)
    if not loaded:
        return JSONResponse({"error": "条目不存在"}, status_code=404)
    item, cached_body = loaded
    url = item.get("链接", "")
    raw = cached_body.strip() if cached_body.strip() else (_fetch_url_text(url) if url.startswith("http") else "")
    if len(raw) < 100:
        return {"type": "chat", "reply": "这篇抓不到正文了，把正文贴给我吧。"}
    page = await _learn_pipeline_v2(item.get("标题", "待学习资料"), raw)
    memory.remove_from_inbox(file_stem)
    return {"type": "learn", "reply": f"「{item.get('标题')}」学完了，已归档 ✅",
            "pages": [page], "highlight": page["highlight"], "inbox": memory.list_inbox()}


@app.post("/api/inbox/podcast")
async def inbox_podcast(payload: dict):
    """听个大概：只出 60 秒播客摘要，不建档不消耗整块时间（S2 碎片消化）。"""
    file_stem = payload.get("file", "")
    loaded = memory.load_inbox_item(file_stem)
    if not loaded:
        return JSONResponse({"error": "条目不存在"}, status_code=404)
    item, cached_body = loaded
    url = str(item.get("链接", ""))
    raw = cached_body.strip() if cached_body.strip() else (_fetch_url_text(url) if url.startswith("http") else "")
    src = raw[:2500] if len(raw) > 200 else f"标题：{item.get('标题')}\n种草点：{item.get('种草点')}"
    script = ""
    if brain.available():
        script = brain._chat(
            "你是织识的播客主播。把资料浓缩成 60 秒口播摘要（150-180字）：先一句话说这是什么，"
            "再讲最值得知道的 2 个点，最后一句说值不值得找整块时间深读。像朋友转述，口语化。"
            "直接出口播稿，不要任何格式和标题。",
            src, 300, thinking=False)
    audio_url = await _tts(script)
    return {"type": "podcast", "reply": f"「{item.get('标题')}」的 60 秒版放中间了 🎧",
            "title": item.get("标题"), "script": script, "audio_url": audio_url}


@app.get("/api/concept/{name}")
def concept_detail_v2(name: str):
    concept = memory.load_concept(name)
    if not concept:
        return JSONResponse({"error": f"概念「{name}」不存在"}, status_code=404)
    meta = concept["meta"]
    return {"name": meta.get("名称", name), "mastery": meta.get("掌握度", ""),
            "source": meta.get("来源", ""), "related": memory.LINK_RE.findall(meta.get("相关概念", "")),
            "first_learned": meta.get("首次学习时间", ""), "updated": meta.get("更新时间", ""),
            "body": concept["body"]}
