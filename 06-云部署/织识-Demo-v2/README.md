# 织识 KnowWeave — Demo

本地单页应用：输入（提问/粘贴/上传 md·pdf·截图）→ 大模型解析串联 → 概念卡 + 播客音频 → Markdown 记忆库自生长 + 知识图谱。

## 快速开始

```bash
cd 织识-Demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 LLM_BASE_URL / LLM_API_KEY
python -m app.main     # 打开 http://127.0.0.1:8000
```

## 演示前

- `bash scripts/reset-demo.sh` 重置记忆库到种子状态
- `.env` 换成个人 key（.env 已 gitignore，绝不提交）
- 没有 key 也能跑：自动进入 mock 兜底模式（回归测试/灰度测试有内置演示答案）

## 目录

| 路径 | 说明 |
| --- | --- |
| app/main.py | FastAPI 路由：/api/ask /api/ingest /api/graph /api/audio |
| app/brain.py | 大模型调用（OpenAI 兼容网关），JSON 结构化输出 |
| app/memory.py | Markdown 记忆层：概念/画像读写、检索、图谱数据 |
| app/ocr.swift | 截图取字（macOS Vision，免装依赖） |
| memory/concepts/ | 概念库（frontmatter + 大白话/疑问/记忆钩子） |
| memory/profiles/user.md | 用户画像（身份/熟悉领域/举例偏好） |
| data/history/ | 问答留痕（成长轨迹） |
| static/index.html | 单页前端（输入/概念卡/vis-network 图谱） |

## 技术栈

Python FastAPI + OpenAI 兼容网关（默认 deepseek-v4-flash）+ edge-tts（中文音色）+ vis-network（本地内置，离线可演示）+ macOS Vision OCR。无数据库、无向量库，记忆就是 Markdown 文件夹。
