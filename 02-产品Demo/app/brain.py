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


def extract_concepts_from_material(title_hint: str, text: str, profile_text: str) -> dict:
    """资料入库：从长文抽取 1-3 个核心概念并生成讲解。"""
    schema = """{
  "concepts": [
    {
      "name": "概念名",
      "explanation": "大白话解释，150字内",
      "analogy": "用用户熟悉领域举例，100字内",
      "hook": "一句话记忆钩子，30字内",
      "related": ["相关概念名"]
    }
  ],
  "summary": "资料一句话总结"
}"""
    system = (
        "你是「织识 KnowWeave」的资料解析器。从用户给的资料里抽取最值得学的 1-3 个核心概念，"
        "用大白话解释并用用户熟悉领域举例。严格输出 JSON。\n"
        f"【用户画像】\n{profile_text}\n输出 JSON schema：\n{schema}"
    )
    user = f"【资料标题线索】{title_hint}\n\n【资料正文】\n{text[:6000]}"
    return _extract_json(_chat(system, user, max_tokens=2500))


def available() -> bool:
    return _client is not None
