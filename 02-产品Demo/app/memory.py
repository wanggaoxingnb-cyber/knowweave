"""记忆层：concepts/ + profiles/ 纯 Markdown 读写。schema 见开工卡第3节。"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT / "memory"
CONCEPTS_DIR = MEMORY_DIR / "concepts"
PROFILES_DIR = MEMORY_DIR / "profiles"
HISTORY_DIR = ROOT / "data" / "history"

MASTERY_STAGES = ["initial", "理解了", "能讲给别人", "能用"]
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, text[end + 4:].strip()


def _render_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _concept_path(name: str) -> Path:
    safe = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return CONCEPTS_DIR / f"{safe}.md"


def list_concepts() -> list[dict]:
    result = []
    if not CONCEPTS_DIR.exists():
        return result
    for path in sorted(CONCEPTS_DIR.glob("*.md")):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        result.append({
            "名称": meta.get("名称", path.stem),
            "掌握度": meta.get("掌握度", "initial"),
            "相关概念": LINK_RE.findall(meta.get("相关概念", "")),
            "更新时间": meta.get("更新时间", ""),
            "body": body,
        })
    return result


def load_concept(name: str) -> dict | None:
    path = _concept_path(name)
    if not path.exists():
        return None
    meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    return {"meta": meta, "body": body, "名称": meta.get("名称", name)}


def save_concept(name: str, explanation: str = "", question: str = "", hook: str = "",
                 source: str = "对话问答", related: list[str] | None = None) -> dict:
    """新建或更新概念文件（自生长规则1&2）。"""
    today = date.today().isoformat()
    related = related or []
    path = _concept_path(name)
    created = not path.exists()
    mastery_up = False

    if created:
        meta = {
            "名称": name,
            "掌握度": "initial",
            "来源": source,
            "相关概念": " ".join(f"[[{r}]]" for r in related),
            "首次学习时间": today,
            "更新时间": today,
        }
        body = "\n\n".join([
            f"大白话解释: {explanation}" if explanation else "大白话解释: （待补充）",
            f"我当时的疑问: {question}" if question else "我当时的疑问: （待补充）",
            f"一句话记忆钩子: {hook}" if hook else "一句话记忆钩子: （待补充）",
        ])
    else:
        old = load_concept(name)
        meta, body = old["meta"], old["body"]
        stage_idx = MASTERY_STAGES.index(meta.get("掌握度", "initial"))
        if stage_idx < len(MASTERY_STAGES) - 1:
            meta["掌握度"] = MASTERY_STAGES[stage_idx + 1]
            mastery_up = True
        meta["更新时间"] = today
        existing = LINK_RE.findall(meta.get("相关概念", ""))
        merged = existing + [r for r in related if r not in existing and r != name]
        meta["相关概念"] = " ".join(f"[[{r}]]" for r in merged)
        if explanation and "（待补充）" in body:
            body = body.replace("大白话解释: （待补充）", f"大白话解释: {explanation}")
        if hook and "一句话记忆钩子: （待补充）" in body:
            body = body.replace("一句话记忆钩子: （待补充）", f"一句话记忆钩子: {hook}")

    path.write_text(_render_frontmatter(meta) + "\n" + body + "\n", encoding="utf-8")
    return {"created": created, "mastery_up": mastery_up, "meta": meta}


def adjust_mastery(name: str, direction: str) -> str | None:
    """判题联动：pass 升一级，fail 降一级（不低于 initial）。返回新掌握度。"""
    path = _concept_path(name)
    if not path.exists():
        return None
    old = load_concept(name)
    meta, body = old["meta"], old["body"]
    idx = MASTERY_STAGES.index(meta.get("掌握度", "initial"))
    idx = idx + 1 if direction == "up" else max(0, idx - 1)
    meta["掌握度"] = MASTERY_STAGES[idx]
    meta["更新时间"] = date.today().isoformat()
    path.write_text(_render_frontmatter(meta) + "\n" + body + "\n", encoding="utf-8")
    return MASTERY_STAGES[idx]


def load_profile() -> str:
    path = PROFILES_DIR / "user.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def append_history(question: str, concepts: list[str], answer_brief: str = "") -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"qa-{date.today().isoformat()}.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {question}\n")
        f.write(f"- 涉及概念: {'、'.join(concepts) if concepts else '（无）'}\n")
        if answer_brief:
            f.write(f"- 回答摘要: {answer_brief}\n")


def search_related(query: str, limit: int = 6) -> list[dict]:
    """朴素检索：名称命中 + 双链命中 + 正文关键词重叠。"""
    query_l = query.lower()
    scored = []
    for concept in list_concepts():
        score = 0
        name = concept["名称"]
        if name.lower() in query_l or query_l in name.lower():
            score += 10
        for token in re.findall(r"[一-鿿]{2,}|[a-zA-Z]+", query):
            if token in name:
                score += 3
            if token in concept["body"]:
                score += 1
        for link in concept["相关概念"]:
            if link.lower() in query_l:
                score += 5
        if score > 0:
            scored.append((score, concept))
    scored.sort(key=lambda item: -item[0])
    return [c for _, c in scored[:limit]]


def graph_data() -> dict:
    nodes, edges, seen = [], [], set()
    for concept in list_concepts():
        name = concept["名称"]
        nodes.append({"id": name, "label": name,
                      "掌握度": concept["掌握度"], "更新时间": concept["更新时间"]})
        for link in concept["相关概念"]:
            key = tuple(sorted([name, link]))
            if key not in seen:
                seen.add(key)
                edges.append({"from": name, "to": link})
    return {"nodes": nodes, "edges": edges}
