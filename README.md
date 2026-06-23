# 香港中文大学（深圳）本科招生自评知识库

CUHK-Shenzhen Undergraduate Self-Assessment Knowledge Base

本项目是一个本地运行的本科招生自评知识库。学生填写成绩、英语能力、专业兴趣、预算和适应能力后，系统会：

1. 从本地官方资料库检索相关招生信息；
2. 用本地 `bge-m3` 做向量检索，并用 BM25 做关键词检索；
3. 自动从检索结果中提取分数上下文（省份分数线、全国统计数据、邻省参照）；
4. 把检索到的官方资料片段和分数上下文一起发给 OpenAI 兼容云端大模型；
5. 输出"高度匹配 / 有条件匹配 / 风险较高 / 暂不建议 / 信息不足"的建议型报告。

> 重要：本系统不是港中深官方录取系统，也不会输出录取概率。所有知识库和历史记录保存在本机，不会上传到第三方。

## 资料覆盖（66 篇）

核心来源定义在 `app/sources.py`，扩展来源定义在 `scripts/extend_sources.py`。
双重检索：向量搜索（语义理解）+ BM25 关键词搜索 + RRF 融合排序。

| 类别 | 数量 | 内容 |
| --- | --- | --- |
| 高考招生 | 1 篇 | 2026 年夏季高考招生章程 |
| 综合评价 | 8 篇 | 各省简章 + 总览 + 入学测试安排 |
| 港澳台招生 | 6 篇 | 联招 / 台湾学测 / 香港 DSE / 澳门保送 / 四校联考 |
| 国际生 | 4 篇 | 入学要求 / 申请资格 / 重要日期 / 奖学金 |
| 奖学金 | 6 篇 | 学科特长 / 博文 / 音乐 / 体育 / 港澳台 / 总览 |
| 专业介绍 | 32 篇 | 31 个专业详情页 + 专业总览 |
| 通用信息 | 6 篇 | 学费住宿 / 国际化教学 / 大学概览 / 书院制度 / FAQ / 招生办联系方式 |
| 音乐类 | 1 篇 | 音乐类招生简章 |
| 第三方参考 | 2 篇 | 高考分数线（2022-2025）/ 985 对比 |
| **合计** | **66 篇** | |

## Features

- 本地网页表单：`http://127.0.0.1:8000`（Lucide 图标 + 分场景提示 + 报告卡片布局）
- 官方资料采集到 `knowledge_base/official/`（66 篇，支持分步扩展 + Playwright SPA 抓取）
- **SPA 浏览器抓取**：Playwright 无头 Chromium 渲染 JS 页面，自动降级到 urllib
- **智能字段校验**：硬必填（地区/考试/成绩/专业）缺则拦截；软选填（英语/预算/适应力）缺则提示但不阻断
- **分数上下文预提取**：检索后自动提取省份分数线、全国统计数据、邻省参照，注入 LLM prompt
- **分数/位次同口径对比**：自动解析学生成绩（识别分数 / 位次 / 百分位 / 非高考体系 IB·A-Level·SAT·DSE），与该省录取线同口径对比（位次对位次、分数对分数）；某一口径缺失时用录取线自带的（分数, 位次）配对作锚点定性推断，绝不把位次和分数混比
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
- Playwright（用于 SPA 页面抓取）

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install Playwright browser:

```bash
playwright install chromium
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

2. （可选）重新采集 SPA 页面（综合评价/港澳台/专业/学费/教学特色等 JS 渲染页）：

```bash
python3 scripts/rescrape_spa.py
```

3. （可选）采集高考录取分数线：

```bash
python3 scripts/scrape_score_lines.py --seed-only
```

4. Build local index:

```bash
python3 scripts/rebuild_index.py
```

5. Start web app:

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
| `POST` | `/api/ingest` | Fetch official sources（容错：失败项单独报告） |
| `POST` | `/api/rebuild` | Rebuild vector + BM25 index |
| `POST` | `/api/assess` | Generate self-assessment report |
| `GET` | `/api/history` | Read local history |
| `POST` | `/api/history/clear` | Clear local history with double confirmation |

## Project Structure

```text
app/
  main.py          FastAPI app and endpoints
  ingest.py        Official page fetch（SPA + static）+ HTML to Markdown
  documents.py     Markdown loading and chunking
  embeddings.py    Ollama embedding call
  retrieval.py     Vector search + BM25 + RRF fusion（top_k=16）
  assessor.py      Profile validation（hard/soft split）+ 学生成绩解析（分数/位次）+ score context extraction + LLM report
  history.py       Local JSONL history
  sources.py       Official source URL registry（含 js_render 标记）
  config.py        Settings from .env
  models.py        Pydantic data models
index.html         Local web UI（Lucide icons）
scripts/
  fetch_official_sources.py   采集 21 个核心资料源
  extend_sources.py           采集 43 个扩展资料源（31 个专业详情页 + 奖学金 + 书院等）
  rescrape_spa.py             用 Playwright 重新采集所有 SPA 页面
  scrape_score_lines.py       高考录取分数线采集工具（种子数据 + Playwright + 解析）
  rebuild_index.py            重建本地搜索索引
tests/
  test_core.py     28 个单元与集成测试（不含真实 Ollama/LLM 调用）
```

## How It Works

1. **资料采集**：`fetch_official_sources.py`（21 个核心源）+ `extend_sources.py`（43 个扩展源）= 64 个源，另有 2 篇第三方参考，共 66 篇 Markdown
   - 静态页面用 urllib/curl 抓取
   - SPA 页面（JS 渲染）用 Playwright 无头 Chromium 抓取，失败自动降级
   - HTML → Markdown：自动去除导航/脚本/样式，保留表格和超链接
2. **建索引**：`rebuild_index.py` 把 Markdown 切成 900 字块 → 用 `bge-m3` 转向量 → 存为 `vectors.npy` + `chunks.json`
3. **评估流程**：学生填表 → 硬必填校验 → 解析学生成绩（分数/位次）→ 检索 16 篇相关片段 → 提取分数上下文（同口径标注）→ 发送给云端 LLM → 输出报告

## Tests

```bash
python3 -m unittest discover -s tests
```

Tests do not call real Ollama or real cloud LLM.
