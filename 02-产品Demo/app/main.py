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


@app.get("/api/audio/{name}")
def audio(name: str):
    path = AUDIO_DIR / Path(name).name
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="audio/mpeg")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
