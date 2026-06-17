# Knowledge Service

RAG 知识服务平台 — 前后端分离架构。后端基于 FastAPI 提供 REST API + MCP SSE Transport，前端基于 React + TypeScript + Ant Design 5 构建可视化管理平台。

## 架构概览

```
┌──────────────┐     HTTP REST      ┌──────────────────────┐     SQL     ┌──────────────┐
│  React SPA   │ ──────────────────▶│    FastAPI Server    │────────────▶│  PostgreSQL  │
│  (Vite 5173) │◀───────────────────│  (localhost:8000)    │◀────────────│  knowledge   │
└──────────────┘     JSON Response   │                      │             │  knowledge_rag│
                                     │  ┌────────────────┐  │             └──────────────┘
┌──────────────┐     MCP SSE         │  │  RAG Engine     │  │
│  MCP Client  │ ──────────────────▶│  │  - Ingestion    │  │
│ (Copilot)    │◀───────────────────│  │  - Query Engine │  │
└──────────────┘   /mcp/sse          │  │  - Evaluation   │  │
                                     │  └────────────────┘  │
                                     └──────────────────────┘
```

完整架构设计见 [DEV_SPEC.md](DEV_SPEC.md)。

## 模型部署与成本分析

### 当前模型部署

| 能力 | 模型 | 提供商 | 部署方式 | 模型参数量 |
|------|------|--------|----------|-----------|
| **LLM** (生成) | `deepseek-v4-flash` | DeepSeek (opencode.ai) | 云端 API | ~200B (MoE) |
| **Embedding** (向量化) | `qwen3-embedding:0.6b` | Qwen (Ollama) | 本地 localhost:11434 | 0.6B |
| **Reranker** (重排序) | `dengcao/Qwen3-Reranker-0.6B:Q8_0` | Qwen (Ollama) | 本地 localhost:11434 | 0.6B (量化) |

> **LLM 选型逻辑：** DeepSeek-v4-Flash 是 DeepSeek 的快速推理模型，采用 MoE 架构。在中文企业知识问答场景下，其质量接近 GPT-4o-mini 水平，但成本仅为后者的 1/10-1/20，延迟更低（首 token 约 0.3-0.8s）。项目配置了 `temperature=0.0` 以保证答案确定性，`max_tokens=10000` 适应长文档生成。
>
> **Embedding / Reranker 选型逻辑：** 选用 0.6B 小模型本地部署，零额外 API 成本，延迟可控。0.6B 参数量级在消费级 GPU（甚至 CPU）上即可流畅运行，满足 P90 < 10s 的性能目标。中文场景下 Qwen3 系列表现优于同尺寸的 BGE 或 Instructor 模型。

### 每次问答的 Token 消耗估算

单次 RAG 问答典型 Token 消耗（以检索 Top-5 chunk 为例）：

| 阶段 | 输入 Token | 输出 Token | 备注 |
|------|-----------|-----------|------|
| Embedding 查询 | ~50 | — | 用户提问向量化 |
| Vector + BM25 检索 | — | — | 本地 pgvector + rank_bm25，零 Token 成本 |
| Reranker 重排序 | — | — | 本地 Ollama 推理，零额外费用 |
| LLM 生成回答 | ~2,750 | ~500 | 含 system prompt + 5 chunks × ~500 tokens + 用户问题 |
| **单次合计** | **~2,800** | **~500** | |

### 每 1000 次调用的成本估算

| 模型 | 输入 ¥/1M tok | 输出 ¥/1M tok | 1,000 次成本 (CNY) | 1,000 次成本 (USD) |
|------|-------------|-------------|-------------------|-------------------|
| **deepseek-v4-flash** (当前) | ~2 | ~8 | (2.8M×¥2 + 0.5M×¥8) ÷ 1M = **¥9.6** | **~$1.32** |
| GPT-4o (SOTA 对比) | ~18 | ~72 | (2.8M×¥18 + 0.5M×¥72) ÷ 1M = **¥86.4** | **~$11.88** |
| Claude 4 Sonnet (SOTA 对比) | ~22 | ~110 | (2.8M×¥22 + 0.5M×¥110) ÷ 1M = **¥116.6** | **~$16.03** |

> **注：** DeepSeek 官方定价为 ¥2/1M 输入、¥8/1M 输出（2026Q1 标准费率）。Embedding 和 Reranker 均为本地 Ollama 运行，成本仅含电费（单次约 ¥0.0001，可忽略）。按日 10,000 次查询计算，DeepSeek 月均 LLM 成本约 ¥2,880，而 GPT-4o 需 ¥25,920。

### SOTA 模型可提升幅度

将当前模型替换为 SOTA 模型的预期提升：

| 指标 | 当前表现 | SOTA 预期 | 提升幅度 | 可行性 |
|------|---------|-----------|---------|--------|
| **Faithfulness** | 0.82-1.00 | 0.92-1.00 | +5-10% | 高 |
| **Context Precision** | 0.62-0.71 | 0.72-0.82 | +10-15% | 中 |
| **检索召回率 (Recall@5)** | 未单独测 | — | +8-12% | 高 |
| **端到端延迟 (P90)** | ~10s (目标) | ~15-25s | **-50~150%** | 负收益 |
| **成本** | $1.32/千次 | $11-16/千次 | **8-12x** | 显著增加 |

> 当前组合在"质量-成本-延迟"三角中选择了**成本与延迟优先**。深度学习模型存在边际收益递减：10x 的成本换取约 10% 的质量提升。建议在关键链路上保留替换为 GPT-5 / Cohere Rerank v3 的扩展点。

### 模型选型权衡总结

| 维度 | 当前方案 | SOTA 方案 | 优劣分析 |
|------|---------|-----------|---------|
| **答案准确性** | ★★★★☆ 可靠 | ★★★★★ 最优 | SOTA 在歧义消解和复杂推理上更强，但 10 倍成本差 |
| **中文支持** | ★★★★★ 优秀 | ★★★★☆ 良好 | Qwen3 + DeepSeek 的中文原生能力优于欧美 SOTA 模型 |
| **响应速度** | ★★★★★ 快速 (0.3-1.5s) | ★★★☆☆ 较慢 (1-4s) | 本地小模型 + Flash LLM 的低延迟优势明显 |
| **部署复杂度** | ★★★★★ 简单 | ★★★☆☆ 中等 | 本地 Ollama 零配置; SOTA API 需要管理 Key + 配额 |
| **运行成本** | ★★★★★ 低廉 | ★★☆☆☆ 昂贵 | 当前方案月成本 < ¥3,000; SOTA 方案 > ¥25,000 |
| **扩展性** | ★★★★☆ 良好 | ★★★★★ 优秀 | SOTA 模型上下文窗口更大、多模态能力更强 |


## 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.13, FastAPI, uvicorn, SQLAlchemy 2.0, pydantic |
| **前端** | React 19, TypeScript 6, Vite 8, Ant Design 5, axios, recharts, react-router-dom 7 |
| **RAG** | pgvector (向量检索), rank_bm25 (稀疏检索), LangChain 1.3 + text-splitters, Ragas 0.4.3, sentence-transformers, markitdown (文档解析) |
| **搜索** | 混合检索 (RRF 融合算法) + Cross-Encoder 重排序 |
| **存储** | PostgreSQL 17 (业务数据: knowledge 库, 向量+全文检索: knowledge_rag 库) |
| **可观测** | OpenTelemetry 分布式追踪, structlog 结构化日志 (ISO 8601 + 固定字段) |

## 目录结构

```
knowledge-service/
├── backend/                       # FastAPI 后端 (uv 管理)
│   ├── app/                       # 应用代码
│   │   ├── api/                   # REST API 路由层
│   │   ├── common/                # 枚举、常量、配置、日志、工具函数
│   │   ├── core/                  # 核心基础设施（预留）
│   │   ├── factory/               # 工厂与策略模式
│   │   │   ├── base/              # 抽象基类 (BaseLLM / BaseEmbedding / BaseLoader 等)
│   │   │   ├── embedding/         # Embedding 实现 (OpenAI / Ollama)
│   │   │   ├── evaluator/         # 评估器实现 (Ragas / Basic / Composite)
│   │   │   ├── llm/               # LLM 实现 (OpenAI / DeepSeek / Ollama)
│   │   │   ├── loader/            # 文档加载器 (PDF / Markdown / HTML)
│   │   │   ├── reranker/          # 重排序实现 (CrossEncoder)
│   │   │   ├── splitter/          # 文本分割器 (Markdown / HTML / Recursive)
│   │   │   └── vector_store/      # 向量存储实现 (pgvector)
│   │   ├── ingestion/             # 文档摄取管道 (Pipeline / Chunking / Embedding /
│   │   │                          #   Storage / Transform / Integrity)
│   │   ├── mcp_server/            # MCP SSE Transport
│   │   ├── model/                 # ORM 实体 + Pydantic DTO
│   │   ├── query_engine/          # 查询引擎 (Dense / Sparse / Hybrid 检索 +
│   │   │                          #   RRF 融合 + 重排序)
│   │   ├── repositories/          # 数据访问层 (SQLAlchemy Repository)
│   │   ├── logs/                  # 运行时日志
│   │   └── main.py                # FastAPI 入口
│   ├── alembic/                   # 数据库迁移
│   ├── config/                    # 配置文件 (settings.yaml)
│   ├── scripts/                   # 工具脚本
│   │   ├── eval_oneclick.py       # 一键评估脚本
│   │   ├── init_knowledge_db.sql
│   │   └── init_knowledge_rag_db.sql
│   ├── tests/                     # 测试 (unit / integration / e2e)
│   ├── eval_log/                  # 评估日志输出
│   └── pyproject.toml             # 项目配置
├── frontend/                      # React + TypeScript 前端 (Vite 8)
│   ├── src/
│   │   ├── api/                   # API 调用层 (axios)
│   │   ├── assets/                # 静态资源
│   │   ├── components/            # 通用 UI 组件
│   │   ├── hooks/                 # 自定义 Hooks
│   │   ├── pages/                 # 页面组件 (Dashboard / 文档中心 / AI 助手等)
│   │   └── types/                 # TypeScript 类型定义
│   ├── public/
│   ├── dist/                      # 构建产物
│   └── package.json
├── golden_test_dataset/           # 黄金测试数据集
├── test_document/                 # 测试知识库文件 (员工手册 / 合规指南 / 技术规范 / 架构文档)
├── DEV_SPEC.md                    # 开发规范
└── README.md
```

## 快速开始

### 1. 数据库

```bash
# knowledge 库（业务数据）
psql -h localhost -U postgres -d knowledge -f backend/scripts/init_knowledge_db.sql

# knowledge_rag 库（向量 + BM25）
psql -h localhost -U postgres -d knowledge_rag -f backend/scripts/init_knowledge_rag_db.sql
```

### 2. 启动后端

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

后端默认监听 `http://localhost:8000`：
- REST API: `/api/*`
- MCP SSE: `/mcp/sse`
- API 文档: `/docs`

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`。

## 测试知识库文件

测试知识库文件位于项目根目录的 `test_document/`，用于上传测试和索引验证：

| 目录 | 文件数 | 说明 |
|------|--------|------|
| `test_document/员工手册/` | 1 | 员工手册 PDF |
| `test_document/合规指南/` | 12 | 合规指南文档 |
| `test_document/技术规范/` | 22 | 含业务需求、开发实现、测试质量、运维交付子层 |
| `test_document/架构文档/` | 12 | 系统架构相关文档 |
| `test_document/PDF输出/` | 58 | 自动转换生成的 PDF 文件（中英文混合） |

## 黄金测试数据集

黄金测试集位于项目根目录的 `golden_test_dataset/`，用于 RAG 质量评估。每个文件包含 `question` 和 `ground_truths` 字段。

| 文件 | 查询数 | 分类 | 语言 |
|------|--------|------|------|
| `黄金测试集_员工手册_zh.json` | 10 | employee_handbook | zh |
| `黄金测试集_合规指南_zh.json` | 12 | compliance | zh |
| `黄金测试集_技术规范_zh.json` | 31 | technical_spec | zh |
| `黄金测试集_架构文档_zh.json` | 20 | architecture | zh |
| `Golden_Test_Set_Architecture_en.json` | 9 | architecture | en |
| `Golden_Test_Set_Technical_Standards_en.json` | 13 | technical_spec | en |
| `Golden_Test_Set_Compliance_en.json` | 5 | compliance | en |

## 一键评估

`backend/scripts/eval_oneclick.py` 基于 golden test dataset / query_traces，通过 ragas 库评估 RAG 管线质量。

### 评估方法

**Mode A (golden)：** 使用黄金测试数据集评估
1. 扫描 `golden_test_dataset/*.json`，解析 question / ground_truths
2. 每个查询优先走 `query_traces` 缓存（已存在则不重复调 LLM）
3. 未命中缓存的查询调用 query engine（检索 + LLM 生成）
4. 按文件批次提交 ragas 批量评估（faithfulness, context_precision）
5. 输出 JSON 摘要到控制台 + 日志文件

**Mode B (traces)：** 使用线上真实用户查询评估
1. 从 `query_traces` 表拉取最近 N 条用户查询
2. 复用缓存的检索结果和 LLM 回答
3. 按批次提交 ragas 评估

### 参数说明

```bash
uv run python scripts/eval_oneclick.py                          # 默认模式（golden）
uv run python scripts/eval_oneclick.py --mode golden --lang zh   # 仅中文集
uv run python scripts/eval_oneclick.py --mode traces --recent 50 # 最近50条线上查询
uv run python scripts/eval_oneclick.py --force                   # 强制重新跑（忽略缓存）
uv run python scripts/eval_oneclick.py --dataset 架构文档         # 按文件名筛选
uv run python scripts/eval_oneclick.py --dataset Architecture_en # 英文架构文档
```

### 评估日志

日志文件写入 `backend/eval_log/`，文件名格式：`{数据集名}_{yyyy_mm_dd_hh_mm_ss}.log`。每个日志文件完整记录了评估全程的输出（structlog + print + ragas 进度），可见 `eval_file_done` / `ragas_batch_failed` 等事件。

### 最新评估结果

```
====================================================================================
  ONE-CLICK EVALUATION  SUMMARY  (2026-06-17)
====================================================================================
Dataset                               Status    Q  Pass Fail Time(s) Faith     Prec
------------------------------------------------------------------------------------
黄金测试集_合规指南_zh                   OK       12   12    0  223.3   0.9667  0.7123
黄金测试集_员工手册_zh                   OK       10   10    0  198.4   1.0000  0.6644
黄金测试集_架构文档_zh                   OK       20   20    0  387.9   0.9271  0.7032
黄金测试集_技术规范_zh                   Failed   31    0   31  210.0   -        -
Golden_Test_Set_Architecture_en        OK        9    9    0  176.9   0.9141  0.6196
Golden_Test_Set_Compliance_en          OK        5    5    0  112.3   0.8167  0.6492
Golden_Test_Set_Technical_Standards_en Failed   13    0   13  210.0   -        -
------------------------------------------------------------------------------------
Total                                  -       100   56   44  387.9   -        -
====================================================================================
```
> **说明：** `黄金测试集_技术规范_zh` 和 `Golden_Test_Set_Technical_Standards_en` 由于 ragas batch 执行超时/异常，暂未产出指标（日志见 `ragas_batch_failed`），后续需排查重跑。其余 5 个数据集共 56 条查询全部通过。

## 相关文档

- [DEV_SPEC.md](DEV_SPEC.md) — 完整开发规范、架构设计、项目排期
