# 香港中文大学（深圳）本科招生自评知识库

CUHK-Shenzhen Undergraduate Self-Assessment Knowledge Base

本项目是一个本地运行的本科招生自评知识库。学生填写成绩、英语能力、专业兴趣、预算和适应能力后，系统会：

1. 从本地官方资料库检索相关招生信息；
2. 用本地 `bge-m3` 做向量检索，并用 BM25 做关键词检索；
3. 把检索到的官方资料片段发给 OpenAI 兼容云端大模型；
4. 输出"高度匹配 / 有条件匹配 / 风险较高 / 暂不建议 / 信息不足"的建议型报告。

> 重要：本系统不是港中深官方录取系统，也不会输出录取概率。所有知识库和历史记录保存在本机，不会上传到第三方。

## 资料覆盖（36 篇）

核心来源定义在 `app/sources.py`，扩展来源定义在 `scripts/extend_sources.py`。
双重检索：向量搜索（语义理解）+ BM25 关键词搜索 + RRF 融合排序。

| 类别 | 数量 | 内容 |
| --- | --- | --- |
| 高考招生 | 1 篇 | 2026 年夏季高考招生章程 |
| 综合评价 | 8 篇 | 各省简章 + 总览 + 入学测试安排 |
| 港澳台招生 | 6 篇 | 联招 / 台湾学测 / 香港 DSE / 澳门保送 / 四校联考 |
| 国际生 | 4 篇 | 入学要求 / 申请资格 / 重要日期 / 奖学金 |
| 奖学金 | 6 篇 | 学科特长 / 博文 / 音乐 / 体育 / 港澳台 / 总览 |
| 通用信息 | 6 篇 | 专业 / 学费住宿 / 国际化教学 / 大学概览 / 书院 / FAQ |
| 联系方式 | 1 篇 | 各招生组联系方式 |
| 音乐类 | 1 篇 | 音乐类招生简章 |
| 第三方参考 | 3 篇 | 高考分数线 / 985 对比 |
| **合计** | **36 篇** | |

## Features

- 本地网页表单：`http://127.0.0.1:8000`
- 官方资料采集到 `knowledge_base/official/`（36 篇，支持分步扩展）
- 双重检索：向量搜索（理解语义）+ BM25 关键词搜索 + RRF 融合排序
- 本地向量索引保存到 `data/index/`
- 自评历史默认保存到 `data/history/self_assessments.jsonl`
- 清空历史记录需要两次确认和确认短语
- 云端大模型只用于写最终报告；知识库和历史记录保存在本机

## Requirements

- Python 3.10+
- Ollama
- Ollama model: `bge-m3:latest`
- OpenAI-compatible chat API

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Confirm Ollama embedding model:

```bash
ollama pull bge-m3
ollama list
```

## Configuration

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Then fill:

```bash
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your_api_key
MODEL_NAME=your_chat_model
```

If you use a compatible proxy/provider, put its base URL in `OPENAI_BASE_URL`.

## Quick Start

1. Fetch official pages:

```bash
python3 scripts/fetch_official_sources.py
python3 scripts/extend_sources.py
```

2. Build local index:

```bash
python3 scripts/rebuild_index.py
```

3. Start web app:

```bash
python3 -m app.main
```

Open:

```text
http://127.0.0.1:8000
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web frontend |
| `GET` | `/api/status` | Knowledge base status |
| `POST` | `/api/ingest` | Fetch official sources |
| `POST` | `/api/rebuild` | Rebuild vector + BM25 index |
| `POST` | `/api/assess` | Generate self-assessment report |
| `GET` | `/api/history` | Read local history |
| `POST` | `/api/history/clear` | Clear local history with double confirmation |

## Project Structure

```text
app/
  main.py          FastAPI app and endpoints
  ingest.py        Official page fetch + HTML to Markdown
  documents.py     Markdown loading and chunking
  embeddings.py    Ollama embedding call
  retrieval.py     Vector search + BM25 + RRF fusion
  assessor.py      Profile validation + LLM report generation
  history.py       Local JSONL history
  sources.py       Official source URL registry
index.html         Local web UI
scripts/           Ingest and rebuild commands
tests/             Unit and integration-style tests
```

## Tests

```bash
python3 -m unittest discover -s tests
```

Tests do not call real Ollama or real cloud LLM.
