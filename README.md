# CUHK-Shenzhen Undergraduate Self-Assessment Knowledge Base

本项目是一个本地运行的本科招生自评知识库。学生填写自己的成绩、英语能力、专业兴趣、预算和适应能力后，系统会：

1. 从本地官方资料库检索相关招生信息；
2. 用本地 `bge-m3` 做向量检索，并用 BM25 做关键词检索；
3. 把检索到的官方资料片段发给 OpenAI 兼容云端大模型；
4. 输出“高度匹配 / 有条件匹配 / 风险较高 / 暂不建议 / 信息不足”的建议型报告。

> 重要：它不是港中深官方录取系统，也不会输出录取概率。

## Features

- 本地网页表单：`http://127.0.0.1:8000`
- 官方资料一次性采集到 `knowledge_base/official/`
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
index.html         Local web UI
scripts/           Ingest and rebuild commands
tests/             Unit and integration-style tests
```

## Tests

```bash
python3 -m unittest discover -s tests
```

Tests do not call real Ollama or real cloud LLM.
