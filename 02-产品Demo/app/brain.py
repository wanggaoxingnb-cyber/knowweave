"""AI 大脑：OpenAI 兼容网关（默认 deepseek-v4-flash）。key 读 .env，缺失时走 mock 兜底。"""
from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.getenv("LLM_BASE_URL", "")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash-0731")

_client = None
if API_KEY:
    from openai import OpenAI
    _client = OpenAI(base_url=BASE_URL or None, api_key=API_KEY, timeout=60)

ANSWER_SCHEMA = """{
  "concept": "本次讲解的主概念名（简短名词）",
  "explanation": "大白话解释，150字内，产品经理能看懂",
  "analogy": "用用户熟悉领域（优先英雄联盟/游戏，其次直销/门店）举一个具体例子，100字内",
  "hook": "一句话记忆钩子，30字内",
  "warning": "如果用户问的概念和已学概念容易混淆，给出防混提示，格式「别和XX混：...」，没有就留空字符串",
  "podcast_script": "播客口播稿，口语化，200字内，把解释+例子讲一遍",
  "related": ["与主概念相关的概念名列表，优先从已学概念中选，可补充1-2个新概念"]
}"""


def _chat(system: str, user: str, max_tokens: int = 1500, json_mode: bool = False,
          timeout: int = 60, thinking: bool | None = None) -> str:
    kwargs = dict(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.4,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    if thinking is False:
        # 生成类长输出（演绎 HTML）禁用思考：思考会烧光 max_tokens 导致空响应，且耗时 10 倍
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = _client.chat.completions.create(**kwargs)
    except Exception:
        if not json_mode:
            raise
        kwargs.pop("response_format", None)
        resp = _client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content.strip()


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"no json in: {text[:200]}")
    return json.loads(match.group(0))


def answer_question(question: str, profile_text: str, related_concepts: list[dict]) -> dict:
    """核心：串联回答。读画像 + 已学概念，生成图文卡内容。"""
    known = "\n".join(
        f"- {c['名称']}（掌握度:{c['掌握度']}）" for c in related_concepts
    ) or "（还没有学过任何概念）"
    system = (
        "你是「织识 KnowWeave」，一个记得用户学过什么、也知道用户是谁的 AI 学习助手。\n"
        "规则：\n"
        "1. 用大白话讲概念，用户是产品经理不是工程师。\n"
        "2. 必须从用户熟悉领域举例（见用户画像）。\n"
        "3. 如果问题与「已学概念」相关，回答要带上「你学过XX」的串联；如果易混淆，warning 字段给出防混提示。\n"
        "4. 严格输出 JSON，不要输出其他内容。\n"
        f"输出 JSON schema：\n{ANSWER_SCHEMA}"
    )
    user = (
        f"【用户画像】\n{profile_text}\n\n"
        f"【已学概念】\n{known}\n\n"
        f"【用户问题】\n{question}"
    )
    return _extract_json(_chat(system, user))


LEARNING_PAGE_SCHEMA = """{
  "summary": "资料一句话总结，50字内",
  "walkthrough": [
    {"heading": "这部分讲了什么（小标题，15字内）", "note": "导读：这部分的重点和怎么看，80字内"}
  ],
  "concepts": [
    {
      "name": "概念名",
      "explanation": "大白话解释，150字内",
      "analogy": "用用户熟悉领域举例，100字内",
      "hook": "一句话记忆钩子，30字内",
      "related": ["相关概念名"]
    }
  ],
  "quiz": [
    {"q": "检验是否真懂的问题（不是原文照抄，是理解题）", "a": "参考答案，80字内"}
  ],
  "podcast_script": "播客口播稿：把这篇资料的核心讲给用户听，口语化，300字内"
}"""


def build_learning_page(title_hint: str, text: str, profile_text: str) -> dict:
    """资料入库 → 学习页：总结 + 导读 + 概念卡 + 检验题 + 播客稿。"""
    system = (
        "你是「织识 KnowWeave」的学习教练。用户丢给你一份资料，你要帮他真正学会，不是只摘要点。\n"
        "规则：\n"
        "1. walkthrough 按资料结构给 2-4 段导读，告诉他每段重点看什么。\n"
        "2. concepts 抽取最值得学的 1-3 个核心概念，用大白话+用户熟悉领域举例。\n"
        "3. quiz 出 2-3 道理解检验题（开放式，考察『真懂』而非记忆）。\n"
        "4. 严格输出 JSON，不要输出其他内容。\n"
        f"【用户画像】\n{profile_text}\n输出 JSON schema：\n{LEARNING_PAGE_SCHEMA}"
    )
    user = f"【资料标题线索】{title_hint}\n\n【资料正文】\n{text[:6000]}"
    return _extract_json(_chat(system, user, max_tokens=3000))


def make_quiz(concept_name: str, concept_body: str, profile_text: str) -> dict:
    """考考我：针对一个已学概念出理解检验题。"""
    schema = '{"questions": [{"q": "问题", "a": "参考答案，80字内"}]}'
    system = (
        "你是「织识 KnowWeave」的出题官。针对用户学过的一个概念出 3 道开放式理解题，"
        "由浅到深：第1题考定义，第2题考对比/辨析，第3题考应用（结合用户熟悉领域出题）。"
        "严格输出 JSON。\n"
        f"【用户画像】\n{profile_text}\n输出 JSON schema：\n{schema}"
    )
    user = f"【概念】{concept_name}\n【当时学的讲解】\n{concept_body[:1200]}"
    return _extract_json(_chat(system, user, max_tokens=2500, thinking=False))


def judge_answer(concept_name: str, question: str, reference: str,
                 user_answer: str, profile_text: str) -> dict:
    """判题：判断用户回答是否真懂，给反馈；不懂就换种方式再讲。"""
    schema = '{"pass": true或false, "feedback": "点评+针对性反馈，100字内，没答对就用用户熟悉领域换个例子再讲一遍"}'
    system = (
        "你是「织识 KnowWeave」的判题官。判断用户对概念的回答是否说明他真懂了（不要求用词精确，"
        "核心意思对就 pass）。反馈要具体：说清他对在哪、缺在哪；没答对就换个用户熟悉领域的例子再讲一次。"
        "严格输出 JSON。\n"
        f"【用户画像】\n{profile_text}\n输出 JSON schema：\n{schema}"
    )
    user = (f"【概念】{concept_name}\n【题目】{question}\n【参考答案】{reference}\n"
            f"【用户回答】{user_answer}")
    return _extract_json(_chat(system, user, max_tokens=800))


def available() -> bool:
    return _client is not None


# ---------- v2 新增：意图路由 / 编织 / 导师 / 输出 ----------

INTENTS = ["explain", "learn", "save", "weave", "quiz", "visualize", "mentor", "create", "chat"]


def route_intent(text: str, has_files: bool, has_url: bool) -> dict:
    """LLM 意图路由 + 顺带提取用户信号。返回 {"intent":..., "signals":[...], ...}"""
    if has_files:
        return {"intent": "learn", "signals": []}
    schema = (
        '{"intent": "以下之一: ' + "/".join(INTENTS) + '",'
        '"topic": "用户想学的主题（导师意图时填）",'
        '"concepts": ["文本中提到的概念名"],'
        '"signals": ["用户这段话里关于他本人的新信息（身份/爱好/熟悉度/学习目标），没有就空数组"],'
        '"reason": "判断理由，15字内"}'
    )
    system = (
        "你是意图路由器。做两件事：①判断用户这句话的意图；②从话里挖用户本人的新信息。\n"
        "意图只能是以下之一：\n"
        "- explain: 问某个概念/知识点是什么\n"
        "- learn: 给了资料/文章/链接，想学习它（含'帮我学''总结下这篇'）\n"
        "- save: 想先存着以后看（'先存着''回头再看''码住'）\n"
        "- weave: 问两个或多个概念之间的关系/想建立关联\n"
        "- quiz: 想被测试/检验（'考考我''出个题'）\n"
        "- visualize: 觉得难，想要图解/动画/演绎（'画给我看''演绎一下'）\n"
        "- mentor: 想系统学某个领域/主题（'我要系统学''怎么入门'）\n"
        "- create: 想把学过的东西写成文章/输出内容\n"
        "- chat: 闲聊或以上都不是\n"
        "concepts 提取规则：从文本里挑出提到的知识概念名词（技术名词/方法论名词），"
        "没有就空数组。concepts 字段必须出现，不能省略。\n"
        "signals 提取规则：只记用户本人的信息（身份/职业/爱好/熟悉领域/学习目标/偏好），"
        "每条是一句可沉淀的事实；纯问题没有新信息就给空数组。signals 字段必须出现，不能省略。\n"
        "示例1：用户说「我在保险公司做运营，用卖保险给我讲讲灰度测试」→ "
        "intent=explain, concepts=[\"灰度测试\"], signals=[\"在保险公司做运营\", \"偏好保险业务例子\"]\n"
        "示例2：用户说「什么是Transformer」→ intent=explain, concepts=[\"Transformer\"], signals=[]\n"
        "示例3：用户说「考考我Attention」→ intent=quiz, concepts=[\"Attention\"], signals=[]\n"
        "只输出 JSON，intent/topic/concepts/signals/reason 五个字段一个都不能少，不要输出其他字段。" + ("注意：文本里有链接，若语气是先存着则 save，想学习则 learn。" if has_url else "")
    )
    try:
        result = _extract_json(_chat(system, text, max_tokens=400, json_mode=True))
        if result.get("intent") not in INTENTS:
            result["intent"] = "explain"
    except Exception:
        result = {"intent": "save" if has_url else "explain"}
    result.setdefault("topic", "")
    result.setdefault("concepts", [])
    result.setdefault("signals", [])
    result.setdefault("reason", "")
    if not isinstance(result["signals"], list):
        result["signals"] = [str(result["signals"])]
    if not isinstance(result["concepts"], list):
        result["concepts"] = [str(result["concepts"])]
    return result


def weave_explain(concepts: list[str], profile_text: str, concept_bodies: dict) -> dict:
    """编织：讲清多个概念之间的关系。返回 {"relationship": ..., "links": [[a,b],...]}"""
    bodies = "\n\n".join(f"【{k}】\n{v[:400]}" for k, v in concept_bodies.items())
    schema = '{"relationship": "用大白话讲清这几个概念的关系，150字内，可用用户熟悉领域类比", "links": [["概念A","概念B"]]}'
    system = (
        "你是「织识」的知识编织者。讲清用户提到的概念之间的关系（从属/对比/因果/易混），"
        "并给出应该建立的双链 pairs。严格输出 JSON。\n"
        f"【用户画像】\n{profile_text}\n输出 JSON schema：\n{schema}"
    )
    user = f"【概念库相关内容】\n{bodies}\n\n【提到的概念】{concepts}"
    return _extract_json(_chat(system, user, max_tokens=800))


def mentor_path(topic: str, profile_text: str, graph_brief: str) -> dict:
    """导师模式：出学习路径。返回 {"goal":..., "steps":[{"concept","why","connect"}]}"""
    schema = '{"goal": "学习目标一句话", "steps": [{"concept": "概念名", "why": "为什么先学它，50字内", "connect": "和用户已会的东西怎么串联，50字内"}]}'
    system = (
        "你是「织识」的导师。用户想系统学一个主题，你要出一条 4-6 步的学习路径："
        "先学什么后学什么，每步说明理由，并尽量和用户已经掌握的概念/熟悉领域串联。"
        "严格输出 JSON。\n"
        f"【用户画像】\n{profile_text}\n【用户已学概念及掌握度】\n{graph_brief}\n输出 JSON schema：\n{schema}"
    )
    return _extract_json(_chat(system, f"我想系统学：{topic}", max_tokens=1200))


def create_article(instruction: str, profile_text: str, concepts_brief: str, history_brief: str) -> dict:
    """输出倒逼输出：从知识库生成自媒体原稿。"""
    schema = '{"title": "文章标题", "article": "Markdown 原稿，800-1500字，第一人称，口语化但有干货"}'
    system = (
        "你是「织识」的输出引擎。用户要把学过的东西写成自媒体文章（费曼学习法：输出倒逼输入）。\n"
        "素材来自他自己的概念库和学习留痕，文章要用第一人称讲'我是怎么学明白的'，"
        "包含他踩过的坑、悟到的最佳实践，用他的熟悉领域举例。\n"
        "严格输出 JSON。\n"
        f"【用户画像】\n{profile_text}\n输出 JSON schema：\n{schema}"
    )
    user = (f"【写作要求】{instruction}\n\n【我的概念库】\n{concepts_brief}\n\n"
            f"【我的学习留痕（坑与心得）】\n{history_brief}")
    return _extract_json(_chat(system, user, max_tokens=3000))


def visualize_concept(concept: str, concept_body: str, profile_text: str) -> dict:
    """演绎：生成自包含 HTML 图解/小动画。"""
    schema = '{"title": "标题", "html": "完整自包含 HTML（内联CSS/JS，无外部依赖，深色背景#0f1420，中文）"}'
    system = (
        "你是「织识」的演绎引擎。把一个难概念做成自包含 HTML 图解或交互动画"
        "（SVG 示意图/步骤动画/可点击的步骤切换均可），帮用户直觉理解。"
        "要求：单个完整 HTML 文档、无外部依赖、深色主题、中文标注、能在 iframe 里直接跑。"
        "重要：克制！HTML 控制在 120 行以内，只做最核心的一个画面/一个交互，宁小勿大。"
        "严格输出 JSON，html 字段是完整 HTML 字符串。\n"
        f"【用户画像】\n{profile_text}\n输出 JSON schema：\n{schema}"
    )
    user = f"【概念】{concept}\n【已有讲解】\n{concept_body[:1000]}"
    return _extract_json(_chat(system, user, max_tokens=6000, timeout=120, thinking=False))
