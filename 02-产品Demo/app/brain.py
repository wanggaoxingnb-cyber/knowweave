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


def _chat(system: str, user: str, max_tokens: int = 1500) -> str:
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.4,
        max_tokens=max_tokens,
    )
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
    return _extract_json(_chat(system, user, max_tokens=1200))


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
