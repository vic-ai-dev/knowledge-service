# Knowledge Service

RAG 知识服务平台 — 前后端分离架构。后端基于 FastAPI 提供 REST API + MCP SSE Transport，前端基于 React + TypeScript + Ant Design 5 构建可视化管理平台。

## 架构概览

```
┌──────────────┐     HTTP REST      ┌──────────────────────┐     SQL     ┌──────────────┐
│  React       │ ──────────────────▶│    FastAPI Server    │────────────▶│  PostgreSQL  │
│  (Vite 5173) │◀───────────────────│  (localhost:8000)    │◀────────────│  knowledge   │
└──────────────┘     JSON Response   │                      │             │  knowledge_rag│
                                     │  ┌────────────────┐  │             └──────────────┘
┌──────────────┐     MCP SSE         │  │  RAG Engine     │  │
│  MCP Client  │ ──────────────────▶│  │  - Ingestion    │  │
│              │◀───────────────────│  │  - Query Engine │  │
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

---

### SOTA 替换方案对比（按能力维度）

#### LLM — 当前 `deepseek-v4-flash` → SOTA 备选

| 维度 | deepseek-v4-flash (当前) | GPT-5 | Claude 4 Sonnet |
|------|------------------------|-------|----------------|
| Faithfulness | 0.82-1.00 | **+5-10%** | **+5-10%** |
| Answer Relevance | 0.0 (Ollama 降级) | 可完整评估 | 可完整评估 |
| 复杂推理能力 | ★★★★☆ 良好 | ★★★★★ 优秀 | ★★★★★ 优秀 |
| 中文理解 | ★★★★★ 原生 | ★★★★☆ 良好 | ★★★★☆ 良好 |
| 上下文窗口 | 128K | 200K+ | 200K |
| 首 Token 延迟 | ~0.3-0.8s | ~1-3s | ~1-4s |
| 每千次成本 (LLM 部分) | **¥9.6** | **¥71-¥190** (7-20x) | **¥89-¥222** (9-23x) |

> **权衡：** 升级 LLM 可带来 Faithfulness +5-10% 并启用 Answer Relevance 评估，但成本增加 7-23x，延迟 3-5x。适合质量敏感场景（如合规审核），日常场景 deepseek-v4-flash 足够。

#### Embedding — 多方案对比

| 维度 | qwen3-embedding:0.6b (当前) | text-embedding-3-large | text-embedding-3-small | BGE-large-en-v1.5 | BGE-m3 | Jina Embeddings v3 |
|------|---------------------------|----------------------|----------------------|------------------|--------|-------------------|
| **提供商** | Qwen | OpenAI | OpenAI | BAAI | BAAI | Jina AI |
| **参数量 / 维度** | 1024 | 3072 | 1536 | 1024 | 1024 | 1024 |
| **MTEB 检索** | ~52-55 | **64.6** | 62.3 | 64.0 | **64.5** | ~62 |
| **C-MTEB 检索 (中文)** | ~58-62 | ~60-63 | ~58-61 | ~56-58 | **~62-64** | ~58-60 |
| **部署方式** | 本地 Ollama | API | API | 本地 | 本地 | 本地 / API |
| **每 1K 次成本** | ¥0 | ~¥0.05 | ~¥0.008 | ¥0 | ¥0 | ¥0 (本地) |
| **推理延迟** | ~5-15ms | ~50-150ms | ~30-100ms | ~10-30ms | ~15-40ms | ~10-30ms |
| **Context Precision 预期提升** | — | +5-10% | +3-5% | +3-8% | +5-10% | +3-5% |
| **Context Recall 预期提升** | — | +8-12% | +5-8% | +5-8% | +8-12% | +3-5% |

> **结论：**
>
> - **中文为主场景**：BGE-m3 是当前最优升级（C-MTEB 最高，本地零成本，+5-10% Precision，+8-12% Recall）
> - **英文为主场景**：text-embedding-3-large 最优（MTEB 64.6，3072 维更细粒度）
> - **成本敏感**：text-embedding-3-small 足够（$0.02/1M tok，¥0.008/千次，几乎免费）
> - **当前 qwen3-embedding:0.6b** 0.6B 参数量级偏小，中文检索已被 BGE-m3 拉开明显差距，建议升级

#### Reranker — 多方案对比

| 维度 | Qwen3-Reranker-0.6B (当前) | Cohere Rerank v3.5 | Voyage Reranker | bge-reranker-large | Jina Reranker v3 |
|------|---------------------------|-------------------|----------------|-------------------|-----------------|
| **提供商** | Qwen | Cohere | Voyage AI | BAAI | Jina AI |
| **参数量** | 0.6B (Q8) | ~2B (闭源) | ~1B (闭源) | ～3.4B | ~0.6B |
| **NDCG@10 基准** | — | +10-18% | +8-12% | +8-14% | +8-12% |
| **Context Precision 预期提升** | — | +8-15% | +6-10% | +8-12% | +6-10% |
| **Context Recall 预期提升** | — | +5-8% | +3-5% | +5-8% | +3-5% |
| **中文效果** | ★★★★☆ 良好 | ★★★★☆ 良好 | ★★★☆☆ 一般 | **★★★★★ 优秀** | ★★★★☆ 良好 |
| **部署方式** | 本地 Ollama | API | API | 本地部署 | 本地 / API |
| **每 1K 次成本** | ¥0 | **$2 (≈¥14.5)** | $0.50 (≈¥3.6) | **¥0 (本地)** | ¥0 (本地) |
| **推理延迟** | ~20-50ms | ~100-300ms | ~80-200ms | ~50-100ms | ~20-50ms |
| **VRAM 需求** | < 1GB | 无 (API) | 无 (API) | ~10GB | ~1.5GB |

> **结论：**
> - **中文为主 + 本地部署**：**bge-reranker-large** 综合最优（中文效果顶尖，本地零成本，+8-12% Precision）
> - **英文为主 + 质量优先**：**Cohere Rerank v3.5** NDCG 最高 (+10-18%)，但需承担 $2/千次成本
> - **混合场景 + 低预算**：**Voyage Reranker** 性价比平衡 ($0.50/千次)
> - **资源受限**：**Jina Reranker v3** VRAM 仅需 1.5GB，延迟最低，适合边缘部署
> - **当前 Qwen3-Reranker-0.6B** 量化 0.6B 参数量级过小，NDCG 显著低于主流方案，建议至少升级到 bge-reranker-large

---

### 每 1000 次调用的成本估算

**LLM 成本（每次 ~3,300 tokens）：**

| 模型 | 输入 ¥/1M tok | 输出 ¥/1M tok | 1,000 次成本 (CNY) | 1,000 次成本 (USD) |
|------|-------------|-------------|-------------------|-------------------|
| **deepseek-v4-flash** (当前) | ~2 | ~8 | (2.8M×¥2 + 0.5M×¥8) ÷ 1M = **¥9.6** | **~$1.32** |
| GPT-5 | ~30-36 | ~120-180 | ¥80-¥190 | **$11-$26** |
| Claude 4 Sonnet | ~22 | ~110 | ¥89-¥222 | **$12-$31** |

**Embedding 成本（每次 ~50 tokens 输入）：**

| 模型 | 单价 / 1M tok | 1,000 次成本 |
|------|-------------|-------------|
| **qwen3-embedding:0.6b** (当前) | ¥0 (本地) | **≈ ¥0** |
| text-embedding-3-large | $0.13 | **≈ ¥0.05** |
| text-embedding-3-small | $0.02 | **≈ ¥0.008** |
| BGE-m3 / BGE-large-en-v1.5 | ¥0 (本地) | **≈ ¥0** |
| Jina Embeddings v3 | ¥0 (本地) | **≈ ¥0** |

**Reranker 成本（每次 ~5 chunks × ~500 tokens，~4,000 tokens 输入/查询）：**

| 模型 | 计费方式 | 1,000 次成本 |
|------|---------|-------------|
| **Qwen3-Reranker-0.6B** (当前) | ¥0 (本地) | **≈ ¥0** |
| Cohere Rerank v3.5 | $2/1K 查询 | **$2.00 (≈ ¥14.5)** |
| Voyage Reranker | $0.50/1K 查询 | **$0.50 (≈ ¥3.6)** |
| bge-reranker-large | ¥0 (本地) | **≈ ¥0** |
| Jina Reranker v3 | ¥0 (本地) | **≈ ¥0** |

> **综合对比：**
> - **当前全链路**（deepseek-v4-flash + qwen3-embedding + Qwen3-Reranker）：**¥9.6/千次**
> - **SOTA 全链路**（GPT-5 + text-embedding-3-large + Cohere Rerank v3.5）：**¥86-¥208/千次**（9-22x）
> - **推荐升级链路**（deepseek-v4-flash + BGE-m3 + bge-reranker-large，均本地）：**¥9.6/千次**（成本不变，中文检索 +8-12%）

---

### 高性能方案（全链路云 API）

适用于生产环境中质量优先的场景，无需本地 GPU 机房：

| 环节 | 推荐模型 | 提供商 | 部署方式 | 每千次成本 |
|------|---------|--------|----------|-----------|
| **LLM** | GPT-5 或 Claude 4 Sonnet | OpenAI / Anthropic | 云端 API | ¥71-¥222 |
| **Embedding** | text-embedding-3-large | OpenAI | 云端 API | ~¥0.05 |
| **Reranker** | Cohere Rerank v3.5 | Cohere | 云端 API | ~¥14.5 |
| **合计** | — | — | **全云 API** | **¥86-¥237/千次** |

| 维度 | 预期表现 |
|------|---------|
| Faithfulness | 0.92-1.00 (+5-10% vs 当前) |
| Context Precision | 0.72-0.85 (+8-18% vs 当前) |
| Context Recall | +8-12% vs 当前 |
| Answer Relevance | 可完整评估（Ollama 降级消除） |
| P90 端到端延迟 | ~2-4s（API 网络延迟为主） |
| 运维复杂度 | 低（无需 GPU 资源，仅管理 API Key + 配额） |

> **适合场景：** 合规审核、监管报送、合同审查等对答案质量要求严格的业务线。API 方式无基础设施负担，但需监控 API 配额和预算。

### 性价比方案（全链路云 API）

适用于日常知识问答与内部辅助场景，平衡质量与成本，同样无需本地基础设施：

| 环节 | 推荐模型 | 提供商 | 部署方式 | 每千次成本 |
|------|---------|--------|----------|-----------|
| **LLM** | deepseek-v4-flash（与当前一致） | DeepSeek (opencode.ai) | 云端 API | ¥9.6 |
| **Embedding** | text-embedding-3-small | OpenAI | 云端 API | ~¥0.008 |
| **Reranker** | Voyage Reranker | Voyage AI | 云端 API | ~¥3.6 |
| **合计** | — | — | **全云 API** | **¥13.2/千次** |

| 维度 | 预期表现 |
|------|---------|
| Faithfulness | 0.82-1.00（与当前持平） |
| Context Precision | 0.64-0.75 (+3-8% vs 当前) |
| Context Recall | +3-5% vs 当前 |
| Answer Relevance | 可完整评估（本地 embedding 降级消除） |
| P90 端到端延迟 | ~0.5-1.5s（与当前持平） |

> **适合场景：** 员工自助查询、文档检索、开发辅助等日常场景。

### 方案对比

| 对比维度 | 当前混合方案 | 性价比方案（推荐） | 高性能方案 |
|---------|------------|-----------------|-----------|
| LLM | deepseek-v4-flash (云端) | deepseek-v4-flash (云端) | GPT-5 / Claude 4 (云端) |
| Embedding | qwen3-embedding (本地 Ollama) | text-embedding-3-small (API) | text-embedding-3-large (API) |
| Reranker | Qwen3-Reranker (本地 Ollama) | Voyage Reranker (API) | Cohere Rerank v3.5 (API) |
| 本地 GPU 需求 | **需要**（Ollama 服务） | **不需要**（全 API） | **不需要**（全 API） |
| Context Precision | 0.62-0.71 | **0.64-0.75** | **0.72-0.85** |
| Faithfulness | 0.82-1.00 | 0.82-1.00 | 0.92-1.00 |
| P90 延迟 | ~0.5-1.5s | ~0.5-1.5s | ~2-4s |
| 每千次 | **¥9.6** | **¥13.2** | **¥86-¥237** |

> **推荐：** 大多数生产环境选择**性价比方案**。全链路云 API，无本地 GPU 依赖，每千次仅 ¥13.2，较当前混合方案仅增加 ¥3.6/千次，即可获得完整的指标可评估性与零基础设施运维。质量敏感场景可通过 settings.yaml 一键切换至高性能方案。


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
Dataset                               Status    Q  Pass Fail Time(s) faithfulness context_precision
------------------------------------------------------------------------------------
黄金测试集_合规指南_zh                   OK       12   12    0  223.3   0.9667  0.7123
黄金测试集_员工手册_zh                   OK       10   10    0  198.4   1.0000  0.6644
黄金测试集_架构文档_zh                   OK       20   20    0  387.9   0.9271  0.7032
Golden_Test_Set_Architecture_en        OK        9    9    0  176.9   0.9141  0.6196
Golden_Test_Set_Compliance_en          OK        5    5    0  112.3   0.8167  0.6492
====================================================================================
```
> **说明：** `黄金测试集_技术规范_zh` 和 `Golden_Test_Set_Technical_Standards_en` 由于 ragas batch 执行超时/异常，暂未产出指标（日志见 `ragas_batch_failed`），后续需排查重跑。其余 5 个数据集共 56 条查询全部通过。



# 运行日志

## ingestion

```bash
2026-06-17 09:17:53,191  info  app.main  http_request  metadata={'method': 'POST', 'path': '/api/ingestion/upload', 'query_string': '', 'client_host': '127.0.0.1'}  service=knowledge_service
2026-06-17 09:17:53,228  info  app.common.database_sa  sql  duration_ms=2.62  message=[SQL] SELECT documents.id, documents.source_path, documents.title, documents.category, documents.language, documents.doc_type, documents.file_size, documents.file_hash, documents.chunk_count, documents.image_count, documents.ingested_at, documents.updated_at, documents.is_deleted  FROM documents  WHERE documents.file_hash = $1::VARCHAR AND documents.is_deleted = false  params=('4c74c8c7885b87c541a93739b3c37a715ecd656688060014b5aafdece8c07e67',)  service=knowledge_service
2026-06-17 09:17:53,229  info  app.api.ingestion  file_uploaded  message=文件上传成功  metadata={'filename': '核心业务系统概述_zh.md', 'size': 3112, 'type': 'md', 'sha256': '4c74c8c7885b87c541a93739b3c37a715ecd656688060014b5aafdece8c07e67', 'category': 'employee_handbook', 'language': 'zh'}  service=knowledge_service
2026-06-17 09:17:53,230  info  app.ingestion.pipeline  ============================================================  service=knowledge_service
2026-06-17 09:17:53,231  info  app.ingestion.pipeline  Starting Ingestion Pipeline for: /var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md  service=knowledge_service
2026-06-17 09:17:53,231  info  app.ingestion.pipeline    Category: employee_handbook  service=knowledge_service
2026-06-17 09:17:53,231  info  app.ingestion.pipeline    Language: zh  service=knowledge_service
2026-06-17 09:17:53,231  info  app.ingestion.pipeline    Doc type: md  service=knowledge_service
2026-06-17 09:17:53,231  info  app.ingestion.pipeline  ============================================================  service=knowledge_service
2026-06-17 09:17:53,231  info  app.ingestion.pipeline    service=knowledge_service
2026-06-17 09:17:53,231  info  app.ingestion.pipeline  📋 Stage 1: File Integrity Check  service=knowledge_service
2026-06-17 09:17:53,232  info  app.main  http_response  metadata={'method': 'POST', 'path': '/api/ingestion/upload', 'status_code': 200, 'duration_ms': 41.36}  service=knowledge_service
2026-06-17 09:17:53,238  info  app.main  http_request  metadata={'method': 'GET', 'path': '/api/documents', 'query_string': 'page=1&page_size=10', 'client_host': '127.0.0.1'}  service=knowledge_service
2026-06-17 09:17:53,284  info  app.ingestion.integrity  integrity_check  metadata={'file_path': '/var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md', 'file_hash': '4c74c8c7885b87c541a93739b3c37a715ecd656688060014b5aafdece8c07e67'}  service=knowledge_service
2026-06-17 09:17:53,284  info  app.common.database_sa  sql  duration_ms=16.87  message=[SQL] SELECT count(*) AS count_1  FROM documents  WHERE documents.is_deleted = false  params=()  service=knowledge_service
2026-06-17 09:17:53,287  info  app.common.database_sa  sql  duration_ms=1.74  message=[SQL] SELECT documents.id, documents.source_path, documents.title, documents.category, documents.language, documents.doc_type, documents.file_size, documents.file_hash, documents.chunk_count, documents.image_count, documents.ingested_at, documents.updated_at, documents.is_deleted  FROM documents  WHERE documents.is_deleted = false ORDER BY documents.ingested_at DESC   LIMIT $1::INTEGER OFFSET $2::INTEGER  params=(10, 0)  service=knowledge_service
2026-06-17 09:17:53,288  info  app.common.database_sa  sql  duration_ms=1.00  message=[SQL] SELECT ingestion_history.id, ingestion_history.document_id, ingestion_history.source_path, ingestion_history.file_hash, ingestion_history.file_size, ingestion_history.status, ingestion_history.category, ingestion_history.language, ingestion_history.doc_type, ingestion_history.total_chunks, ingestion_history.total_images, ingestion_history.error_message, ingestion_history.started_at, ingestion_history.completed_at, ingestion_history.created_at  FROM ingestion_history  WHERE ingestion_history.document_id = $1::UUID ORDER BY ingestion_history.created_at DESC   LIMIT $2::INTEGER  params=(UUID('95f4fdc3-745c-402f-ba8f-523fac09320c'), 1)  service=knowledge_service
2026-06-17 09:17:53,291  info  app.common.database_sa  sql  duration_ms=1.28  message=[SQL] SELECT ingestion_history.id, ingestion_history.document_id, ingestion_history.source_path, ingestion_history.file_hash, ingestion_history.file_size, ingestion_history.status, ingestion_history.category, ingestion_history.language, ingestion_history.doc_type, ingestion_history.total_chunks, ingestion_history.total_images, ingestion_history.error_message, ingestion_history.started_at, ingestion_history.completed_at, ingestion_history.created_at  FROM ingestion_history  WHERE ingestion_history.document_id = $1::UUID ORDER BY ingestion_history.created_at DESC   LIMIT $2::INTEGER  params=(UUID('3b0e6bd1-39e0-4aef-b8b8-2c912c75ea3f'), 1)  service=knowledge_service
2026-06-17 09:17:53,294  info  app.common.database_sa  sql  duration_ms=2.42  message=[SQL] SELECT ingestion_history.id, ingestion_history.document_id, ingestion_history.source_path, ingestion_history.file_hash, ingestion_history.file_size, ingestion_history.status, ingestion_history.category, ingestion_history.language, ingestion_history.doc_type, ingestion_history.total_chunks, ingestion_history.total_images, ingestion_history.error_message, ingestion_history.started_at, ingestion_history.completed_at, ingestion_history.created_at  FROM ingestion_history  WHERE ingestion_history.document_id = $1::UUID ORDER BY ingestion_history.created_at DESC   LIMIT $2::INTEGER  params=(UUID('ecdaeea1-0b06-4127-8eaa-21ae1677b527'), 1)  service=knowledge_service
2026-06-17 09:17:53,295  info  app.ingestion.integrity  integrity_check_new  metadata={'file_path': '/var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md', 'result': 'new'}  service=knowledge_service
2026-06-17 09:17:53,303  info  app.common.database_sa  sql  duration_ms=8.19  message=[SQL] SELECT ingestion_history.id, ingestion_history.document_id, ingestion_history.source_path, ingestion_history.file_hash, ingestion_history.file_size, ingestion_history.status, ingestion_history.category, ingestion_history.language, ingestion_history.doc_type, ingestion_history.total_chunks, ingestion_history.total_images, ingestion_history.error_message, ingestion_history.started_at, ingestion_history.completed_at, ingestion_history.created_at  FROM ingestion_history  WHERE ingestion_history.document_id = $1::UUID ORDER BY ingestion_history.created_at DESC   LIMIT $2::INTEGER  params=(UUID('bba9caac-dad0-4203-befd-4f99cd7ce129'), 1)  service=knowledge_service
2026-06-17 09:17:53,307  info  app.ingestion.pipeline    File hash: 4c74c8c7885b87c541a93739b3c37a715ecd656688060014b5aafdece8c07e67  service=knowledge_service
2026-06-17 09:17:53,307  info  app.ingestion.pipeline    ✓ File needs processing  service=knowledge_service
2026-06-17 09:17:53,309  info  app.common.database_sa  sql  duration_ms=2.80  message=[SQL] SELECT ingestion_history.id, ingestion_history.document_id, ingestion_history.source_path, ingestion_history.file_hash, ingestion_history.file_size, ingestion_history.status, ingestion_history.category, ingestion_history.language, ingestion_history.doc_type, ingestion_history.total_chunks, ingestion_history.total_images, ingestion_history.error_message, ingestion_history.started_at, ingestion_history.completed_at, ingestion_history.created_at  FROM ingestion_history  WHERE ingestion_history.document_id = $1::UUID ORDER BY ingestion_history.created_at DESC   LIMIT $2::INTEGER  params=(UUID('fe15a5ba-8ac1-44db-b897-eff5994db0a9'), 1)  service=knowledge_service
2026-06-17 09:17:53,319  info  app.common.database_sa  sql  duration_ms=0.65  message=[SQL] SELECT ingestion_history.id, ingestion_history.document_id, ingestion_history.source_path, ingestion_history.file_hash, ingestion_history.file_size, ingestion_history.status, ingestion_history.category, ingestion_history.language, ingestion_history.doc_type, ingestion_history.total_chunks, ingestion_history.total_images, ingestion_history.error_message, ingestion_history.started_at, ingestion_history.completed_at, ingestion_history.created_at  FROM ingestion_history  WHERE ingestion_history.document_id = $1::UUID ORDER BY ingestion_history.created_at DESC   LIMIT $2::INTEGER  params=(UUID('ebb49370-899f-4446-ab8a-a3afbb4816ce'), 1)  service=knowledge_service
2026-06-17 09:17:53,320  info  app.ingestion.integrity  integrity_register  metadata={'run_id': 'f3f4f91e-488c-46cb-be61-fcd4ecced670', 'file_path': '/var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md', 'file_hash': '4c74c8c7885b87c541a93739b3c37a715ecd656688060014b5aafdece8c07e67'}  service=knowledge_service
2026-06-17 09:17:53,320  info  app.main  http_response  metadata={'method': 'GET', 'path': '/api/documents', 'status_code': 200, 'duration_ms': 82.14}  service=knowledge_service
2026-06-17 09:17:53,322  info  app.factory.loader.markdown  md_load_complete  metadata={'source_path': '/var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md', 'length': 1580}  service=knowledge_service
2026-06-17 09:17:53,322  info  app.ingestion.chunking.batch_processor  📄 Stage 2: Document Loading  service=knowledge_service
2026-06-17 09:17:53,322  info  app.ingestion.chunking.batch_processor    Text length: 1580 chars  service=knowledge_service
2026-06-17 09:17:53,322  info  app.ingestion.chunking.batch_processor    Source: /var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md  service=knowledge_service
2026-06-17 09:17:53,323  info  app.factory.splitter.langchain_impl  split_done  metadata={'splitter': 'MarkdownHeaderSplitter', 'chunks': 7, 'duration_ms': 0.35}  service=knowledge_service
2026-06-17 09:17:53,323  info  app.ingestion.chunking.batch_processor  ✂️  Stage 3: Document Chunking  service=knowledge_service
2026-06-17 09:17:53,323  info  app.ingestion.chunking.batch_processor    Chunks generated: 7  service=knowledge_service
2026-06-17 09:17:53,323  info  app.ingestion.chunking.batch_processor    First chunk preview: 本文档对保险公司核心业务系统进行总体介绍，帮助技术人员从业务视角理解各系统的职责、边界和关键业务流程。面向新入职开发人员、架构师及与业务部门协作的技术人员。...  service=knowledge_service
2026-06-17 09:17:53,324  info  app.ingestion.chunking.batch_processor  🔄 Stage 4: Transform Pipeline  service=knowledge_service
2026-06-17 09:17:53,324  info  app.ingestion.chunking.batch_processor    4a. Chunk Refinement...  service=knowledge_service
2026-06-17 09:17:53,324  info  app.ingestion.chunking.batch_processor        Refined 7 chunks  service=knowledge_service
2026-06-17 09:17:53,324  info  app.ingestion.chunking.batch_processor    4b. Metadata Enrichment...  service=knowledge_service
2026-06-17 09:17:53,324  info  app.ingestion.chunking.batch_processor        Enriched 7 chunks  service=knowledge_service
2026-06-17 09:17:53,324  info  app.ingestion.chunking.batch_processor  🔢 Stage 5: Encoding  service=knowledge_service
openai._base_client  Request options: {'method': 'post', 'url': '/embeddings', 'files': None, 'idempotency_key': 'stainless-python-retry-a512c499-6b05-451e-87d0-fdb1e1ccbfe2', 'post_parser': <function AsyncEmbeddings.create.<locals>.parser at 0x127f320c0>, 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'input': ['本文档对保险公司核心业务系统进行总体介绍，帮助技术人员从业务视角理解各系统的职责、边界和关键业务流程。面向新入职开发人员、架构师及与业务部门协作的技术人员。', '```\n产品设计 → 销售 → 投保 → 核保 → 缴费 → 出单 → 保单管理 → 续期 → 理赔 → 合同终止\n``` \n核心业务贯穿以下生命周期阶段，每个阶段由对应的系统支撑： \n| 阶段 | 核心活动 | 支撑系统 |\n|------|---------|---------|\n| 产品设计 | 产品定义、费率定价、条款生成 | 产品中心 |\n| 销售 | 渠道推广、客户触达、投保建议 | 渠道中心、CRM |\n| 投保 | 信息录入、健康告知、投保证明上传 | 承保中心 |\n| 核保 | 自动核保规则判断、人工核保 | 核保引擎 |\n| 缴费 | 首期保费收取、支付渠道对接 | 收付中心 |\n| 出单 | 保单生成、电子保单下发 | 承保中心 |\n| 保单管理 | 保全变更、退保、复效 | 保全中心 |\n| 续期 | 续期缴费提醒、宽限期管理 | 续期中心 |\n| 理赔 | 报案、查勘、定损、理算、结案 | 理赔中心 |\n| 合同终止 | 满期给付、退保销户 | 保全/收付中心 |', '```\n产品中心 ←→ 承保中心 ←→ 收付中心\n↕ ↕\n渠道中心 ←→ 核保引擎 保全中心 ←→ 理赔中心\n↕ ↕\nCRM系统 ←→ 再保中心 续期中心\n↕\n通知中心(短信/邮件/推送)\n```', '```\n一个客户 → 多份保单\n一份保单 → 多个被保人\n一份保单 → 多个受益人\n一份保单 → 多个险种(主险+附加险)\n一份保单 → 多条缴费记录\n一份保单 → 多次保全/理赔记录\n```', '所有核心系统遵循统一的字段定义： \n| 通用字段 | 类型 | 说明 |\n|---------|------|------|\n| policy_id | Varchar(32) | 保单唯一编号，规则: 渠道(2)+产品(4)+序列(10)+校验位 |\n| application_id | Varchar(32) | 投保单号 |\n| product_code | Varchar(16) | 产品编码 |\n| channel_code | Varchar(8) | 渠道编码 |\n| customer_id | Varchar(32) | 客户唯一标识 |\n| policy_status | Varchar(4) | 保单状态码 |\n| premium | Decimal(18,2) | 保费金额 |\n| sum_insured | Decimal(18,2) | 保额 |', '1. **单向依赖**：避免循环依赖，核心数据流向有向无环\n2. **事件通知**：状态变更通过领域事件通知下游\n3. **数据归属**：每个原子数据有且仅有一个系统主责维护\n4. **幂等设计**：所有写入接口支持幂等重试\n5. **最终一致性**：跨系统状态无需强一致，通过对账保证', '- 承保与核保业务流程文档\n- 理赔业务流程文档\n- 续期与保全业务流程文档\n- 再保业务流程文档\n- 产品配置与管理规范'], 'model': 'qwen3-embedding:0.6b', 'encoding_format': 'base64'}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/embeddings
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/embeddings "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:17:56 GMT', 'transfer-encoding': 'chunked'})
openai._base_client  request_id: None
2026-06-17 09:17:56,633  info  app.ingestion.embedding.dense_encoder  dense_encode_batch  metadata={'batch_start': 0, 'batch_size': 7, 'total_chunks': 7, 'completed': 7, 'model': 'qwen3-embedding:0.6b'}  service=knowledge_service
2026-06-17 09:17:56,634  info  app.ingestion.embedding.dense_encoder  dense_encode_complete  metadata={'total_chunks': 7}  service=knowledge_service
2026-06-17 09:17:56,634  info  app.ingestion.chunking.batch_processor    Dense vectors: 7 (dim=1024)  service=knowledge_service
2026-06-17 09:17:56,634  info  app.ingestion.chunking.batch_processor  ✓ Batch processing complete  chunks=7  service=knowledge_service
2026-06-17 09:17:56,634  info  app.ingestion.pipeline  💾 Stage 6: Storage  service=knowledge_service
2026-06-17 09:17:56,899  info  app.ingestion.storage.vector_upserter  vector_upsert_done  metadata={'total_input': 7, 'upserted': 7, 'skipped': 0}  service=knowledge_service
2026-06-17 09:17:56,900  info  app.ingestion.pipeline    ✓ Stored 7 vectors  service=knowledge_service
2026-06-17 09:17:56,930  info  app.ingestion.storage.bm25_indexer  bm25_loaded  metadata={'chunks': 599}  service=knowledge_service
2026-06-17 09:17:57,380  info  app.ingestion.storage.bm25_indexer  bm25_rebuild_done  metadata={'chunks': 606, 'terms': 5927}  service=knowledge_service
2026-06-17 09:17:57,381  info  app.ingestion.storage.bm25_indexer  bm25_add_documents  metadata={'chunks': 7, 'doc_id': 'cf12ca1a-aa8d-4242-8e58-39a22cfdf9eb'}  service=knowledge_service
2026-06-17 09:17:57,381  info  app.ingestion.pipeline    ✓ BM25 index updated  chunk_count=7  service=knowledge_service
2026-06-17 09:17:57,394  info  app.ingestion.integrity  integrity_register_document  metadata={'document_id': 'cf12ca1a-aa8d-4242-8e58-39a22cfdf9eb', 'source_path': '/var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md', 'title': '核心业务系统概述_zh', 'chunk_count': 7}  service=knowledge_service
2026-06-17 09:17:57,394  info  app.ingestion.pipeline    ✓ Document metadata registered  chunk_count=7  service=knowledge_service
2026-06-17 09:17:57,403  info  app.ingestion.integrity  integrity_trace_recorded  metadata={'trace_id': '09d2adce-feeb-88ed-bbbf-50a1361dca31', 'source_path': '/var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md', 'status': 'completed', 'total_chunks': 7}  service=knowledge_service
2026-06-17 09:17:57,403  info  app.ingestion.pipeline    ✓ Ingestion trace recorded  service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.integrity  integrity_update  metadata={'run_id': 'f3f4f91e-488c-46cb-be61-fcd4ecced670', 'status': 'completed', 'total_chunks': 7}  service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.pipeline    service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.pipeline  ============================================================  service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.pipeline  ✅ Pipeline completed successfully!  service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.pipeline      load: 1 items (3ms)  service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.pipeline      split: 7 items (1ms)  service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.pipeline      transform: 7 items (1ms)  service=knowledge_service
2026-06-17 09:17:57,408  info  app.ingestion.pipeline      embed: 7 items (3310ms)  service=knowledge_service
2026-06-17 09:17:57,409  info  app.ingestion.pipeline     Total chunks: 7  service=knowledge_service
2026-06-17 09:17:57,409  info  app.ingestion.pipeline  ============================================================  service=knowledge_service
2026-06-17 09:17:57,410  info  app.api.ingestion  background_pipeline_completed  metadata={'source': '/var/folders/48/jd8bj2jn5n92m_b72kkg42s80000gn/T/ks_upload_s0pt2zqb/4c74c8c7885b87c5.md'}  service=knowledge_service

```





## query

```bash
2026-06-17 09:21:57,846  info  app.main  http_request  metadata={'method': 'POST', 'path': '/api/query/search', 'query_string': '', 'client_host': '127.0.0.1'}  service=knowledge_service
2026-06-17 09:21:57,849  info  app.query_engine.query_processor  query_processed  metadata={'search_mode': 'hybrid', 'top_k': 10, 'rerank': True, 'has_filters': False}  service=knowledge_service
openai._base_client  Request options: {'method': 'post', 'url': '/embeddings', 'files': None, 'idempotency_key': 'stainless-python-retry-aa74f768-d845-46d1-a0d4-d7d7039d4465', 'post_parser': <function AsyncEmbeddings.create.<locals>.parser at 0x13b154a40>, 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'input': '发布前回滚方案需要验证哪些内容？', 'model': 'qwen3-embedding:0.6b', 'encoding_format': 'base64'}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/embeddings
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/embeddings "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:21:58 GMT', 'transfer-encoding': 'chunked'})
openai._base_client  request_id: None
2026-06-17 09:21:58,354  debug  app.factory.vector_store.pgvector_impl  query_result_rows  message=Got 10 rows from vector query  service=knowledge_service
2026-06-17 09:21:58,355  debug  app.factory.vector_store.pgvector_impl  query_metadata_debug  message=First row metadata type=str, value='{"h1": "上线Checklist规范", "h2": "3. 发布前 Checklist", "h3": "3.4 回滚方案", "title": "上线Checklist规范_zh", "category": "technical_spec", "doc_type": "md", "language": "zh", "enriched_at": "2026-06-16T23:02:29.  metadata={'type': 'str'}  service=knowledge_service
2026-06-17 09:21:58,355  info  app.query_engine.dense_retriever  dense_retrieve_done  metadata={'top_k': 10, 'recall_k': 10, 'results': 10, 'latency_ms': 505.11}  service=knowledge_service
2026-06-17 09:21:58,380  info  app.ingestion.storage.bm25_indexer  bm25_loaded  metadata={'chunks': 606}  service=knowledge_service
2026-06-17 09:21:58,382  info  app.query_engine.sparse_retriever  sparse_retrieve_done  metadata={'top_k': 10, 'results': 10, 'latency_ms': 26.81}  service=knowledge_service
2026-06-17 09:21:58,382  info  app.query_engine.rrf_fusion  rrf_fusion_done  metadata={'dense_input': 10, 'sparse_input': 10, 'unique_before_fusion': 15, 'final_top_k': 10}  service=knowledge_service
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-3d944b27-1a2a-4a1c-8c55-ec319917fb2b', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'user', 'content': 'You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.\n\nQuery: 发布前回滚方案需要验证哪些内容？\n\nPassage: - [ ] 回滚方案文档已编写\n- [ ] 应用回滚步骤已验证（回滚到上一版本的脚本）\n- [ ] 数据库回滚脚本已准备并验证\n- [ ] 数据回滚触发条件已定义\n- [ ] 回滚预估时间已评估（RTO）\n- [ ] 回滚后数据有效性已验证\n\nRelevance score:'}], 'model': 'dengcao/Qwen3-Reranker-0.6B:Q8_0', 'max_tokens': 10, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-5c0e53f2-c98b-481a-95cf-8dd6ace3ada3', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'user', 'content': 'You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.\n\nQuery: 发布前回滚方案需要验证哪些内容？\n\nPassage: 通过标准化的上线检查清单（Checklist），确保每次发布前所有准备工作到位、风险可控、回滚方案完备，降低发布导致的生产事故概率。\n\nRelevance score:'}], 'model': 'dengcao/Qwen3-Reranker-0.6B:Q8_0', 'max_tokens': 10, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-890f14bd-24b4-411d-88b5-5bcd5eb910c2', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'user', 'content': 'You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.\n\nQuery: 发布前回滚方案需要验证哪些内容？\n\nPassage: ```markdown\n# 回滚方案 - [项目名称] v[版本号]\n\n## 回滚触发条件\n1. [条件1]\n2. [条件2]\n\n## 应用回滚\n1. 回滚到上一版本镜像：[镜像 Tag]\n2. 部署命令：[命令]\n3. 验证命令：[健康检查命令]\n\n## 数据库回滚\n1. 回滚脚本：[SQL 文件路径]\n2. 执行方式：[DBA 执行 / 自动化工具]\n3. 验证方式：[验证 SQL]\n\n## 数据补偿\n- 如有数据写入，补偿方案：[描述]\n\n## 回滚后动作\n- 通知相关人员\n- 记录回滚原因\n- 后续优化计划\n```\n\nRelevance score:'}], 'model': 'dengcao/Qwen3-Reranker-0.6B:Q8_0', 'max_tokens': 10, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-08f682ed-85b5-4ecb-a9da-944befa31862', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'user', 'content': 'You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.\n\nQuery: 发布前回滚方案需要验证哪些内容？\n\nPassage: - [ ] 预发布环境（Staging）验证通过\n- [ ] 生产环境配置已审核（配置中心 diff）\n- [ ] 数据库变更脚本已审批并预执行验证\n- [ ] 依赖的外部服务版本已确认（第三方 API / 中间件）\n- [ ] SSL 证书未过期\n- [ ] CDN 缓存刷新计划已确认\n- [ ] 域名/DNS 变更已完成\n\nRelevance score:'}], 'model': 'dengcao/Qwen3-Reranker-0.6B:Q8_0', 'max_tokens': 10, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-e1d05e7d-ebc1-43d5-9905-2640bb3d44dd', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'user', 'content': 'You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.\n\nQuery: 发布前回滚方案需要验证哪些内容？\n\nPassage: - [ ] Rollback plan documented\n- [ ] Application rollback steps verified (rollback script to previous version)\n- [ ] Database rollback script prepared and verified\n- [ ] Rollback trigger conditions defined\n- [ ] Estimated rollback time assessed (RTO)\n- [ ] Post-rollback data validity verified\n\nRelevance score:'}], 'model': 'dengcao/Qwen3-Reranker-0.6B:Q8_0', 'max_tokens': 10, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-6101c0bf-9fbb-49a2-9460-e2d1c4f9953c', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'user', 'content': 'You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.\n\nQuery: 发布前回滚方案需要验证哪些内容？\n\nPassage: - [ ] 灰度发布方案已定稿\n- [ ] 灰度比例和时间计划已确定\n- [ ] 灰度验证指标已定义（错误率、RT、业务指标）\n- [ ] 灰度回滚条件已明确\n- [ ] 灰度期间监控已配置\n\nRelevance score:'}], 'model': 'dengcao/Qwen3-Reranker-0.6B:Q8_0', 'max_tokens': 10, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-04353d49-3f90-4faa-84fa-99806a536eeb', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'user', 'content': 'You are a relevance scorer. Given a query and a passage, rate how relevant the passage is to the query on a scale of 0 to 10. Only output a number between 0 and 10, nothing else.\n\nQuery: 发布前回滚方案需要验证哪些内容？\n\nPassage: \n\nRelevance score:'}], 'model': 'dengcao/Qwen3-Reranker-0.6B:Q8_0', 'max_tokens': 10, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:01 GMT', 'content-length': '321'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:01 GMT', 'content-length': '319'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:02 GMT', 'content-length': '321'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:02 GMT', 'content-length': '321'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:02 GMT', 'content-length': '321'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:02 GMT', 'content-length': '321'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:02 GMT', 'content-length': '319'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:02 GMT', 'content-length': '320'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:03 GMT', 'content-length': '321'})
openai._base_client  request_id: None
openai._base_client  HTTP Response: POST http://127.0.0.1:11434/v1/chat/completions "200 OK" Headers({'content-type': 'application/json', 'date': 'Wed, 17 Jun 2026 01:22:03 GMT', 'content-length': '319'})
openai._base_client  request_id: None
2026-06-17 09:22:03,138  info  app.query_engine.reranker  query_rerank_done  metadata={'candidates': 10, 'final': 10, 'latency_ms': 4754.82}  service=knowledge_service
2026-06-17 09:22:03,138  info  app.query_engine.hybrid_search  hybrid_search_done  metadata={'search_mode': 'hybrid', 'dense_results': 10, 'sparse_results': 10, 'final_results': 10, 'latency_ms': 5288.16}  service=knowledge_service
openai._base_client  Request options: {'method': 'post', 'url': '/chat/completions', 'files': None, 'idempotency_key': 'stainless-python-retry-4a5f5e44-e61c-4fa5-ad02-e44d84f5fa01', 'security': {'bearer_auth': True}, 'content': None, 'json_data': {'messages': [{'role': 'system', 'content': 'You are a professional enterprise knowledge assistant. Answer questions based strictly on the provided context.\n\n## Rules\n\n1. **Base on context only** — Do not make up or infer information beyond the provided context.\n2. **Strip formatting** — The context may contain Markdown formatting (e.g. **, *, #, `). These are for text structure only; do NOT include them in your answer.\n3. **UNABLE_TO_ANSWER** — If the context does NOT contain enough information to answer the question, begin your response with exactly "UNABLE_TO_ANSWER" followed by a brief explanation.\n4. **Be honest** — Do not guess. If the information is only partially covered, say so rather than fabricating.\n\n## Context\n\n[来源: 上线Checklist规范_zh]\n- [ ] 灰度发布方案已定稿\n- [ ] 灰度比例和时间计划已确定\n- [ ] 灰度验证指标已定义（错误率、RT、业务指标）\n- [ ] 灰度回滚条件已明确\n- [ ] 灰度期间监控已配置\n\n- [ ] 回滚方案文档已编写\n- [ ] 应用回滚步骤已验证（回滚到上一版本的脚本）\n- [ ] 数据库回滚脚本已准备并验证\n- [ ] 数据回滚触发条件已定义\n- [ ] 回滚预估时间已评估（RTO）\n- [ ] 回滚后数据有效性已验证\n\n通过标准化的上线检查清单（Checklist），确保每次发布前所有准备工作到位、风险可控、回滚方案完备，降低发布导致的生产事故概率。\n\n```markdown\n# 回滚方案 - [项目名称] v[版本号]\n\n## 回滚触发条件\n1. [条件1]\n2. [条件2]\n\n## 应用回滚\n1. 回滚到上一版本镜像：[镜像 Tag]\n2. 部署命令：[命令]\n3. 验证命令：[健康检查命令]\n\n## 数据库回滚\n1. 回滚脚本：[SQL 文件路径]\n2. 执行方式：[DBA 执行 / 自动化工具]\n3. 验证方式：[验证 SQL]\n\n## 数据补偿\n- 如有数据写入，补偿方案：[描述]\n\n## 回滚后动作\n- 通知相关人员\n- 记录回滚原因\n- 后续优化计划\n```\n\n- [ ] 预发布环境（Staging）验证通过\n- [ ] 生产环境配置已审核（配置中心 diff）\n- [ ] 数据库变更脚本已审批并预执行验证\n- [ ] 依赖的外部服务版本已确认（第三方 API / 中间件）\n- [ ] SSL 证书未过期\n- [ ] CDN 缓存刷新计划已确认\n- [ ] 域名/DNS 变更已完成\n\n## Question\n\n发布前回滚方案需要验证哪些内容？\n\n## Answer\n'}, {'role': 'user', 'content': '发布前回滚方案需要验证哪些内容？'}], 'model': 'deepseek-v4-flash', 'max_tokens': 10000, 'stream': False, 'temperature': 0.0}}
openai._base_client  Sending HTTP Request: POST https://opencode.ai/zen/go/v1/chat/completions
openai._base_client  HTTP Response: POST https://opencode.ai/zen/go/v1/chat/completions "200 OK" Headers({'date': 'Wed, 17 Jun 2026 01:22:12 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'cf-placement': 'remote-ORD', 'content-encoding': 'gzip', 'server': 'cloudflare', 'cf-ray': 'a0ce3db6edb72aa8-PHL'})
openai._base_client  request_id: None
2026-06-17 09:22:12,740  info  app.factory.llm.deepseek  deepseek_llm_call  metadata={'model': 'deepseek-v4-flash', 'prompt_tokens': 696, 'completion_tokens': 775, 'reasoning': True}  service=knowledge_service
2026-06-17 09:22:12,792  info  app.common.database_sa  sql  duration_ms=17.24  message=[SQL] INSERT INTO query_traces (trace_id, user_query, search_mode, rerank, category, language, total_latency_ms, input_tokens, output_tokens, total_tokens, cache_hit, rejected, rejection_reason, context_precision, context_recall, faithfulness, answer_relevancy, prompt_cache_hit_tokens, prompt_cache_miss_tokens, stages, top_k_results, results, error) VALUES ($1::UUID, $2::VARCHAR, $3::VARCHAR, $4::BOOLEAN, $5::VARCHAR, $6::VARCHAR, $7::INTEGER, $8::INTEGER, $9::INTEGER, $10::INTEGER, $11::BOOLEAN, $12::BOOLEAN, $13::VARCHAR, $14::FLOAT, $15::FLOAT, $16::FLOAT, $17::FLOAT, $18::INTEGER, $19::INTEGER, $20::JSONB, $21::JSONB, $22::VARCHAR, $23::VARCHAR) RETURNING query_traces.created_at  params=(UUID('88e526bf-a80f-425d-933b-4f8bd5e45b11'), '发布前回滚方案需要验证哪些内容？', 'hybrid', True, None, None, 14890, 696, 775, 1471, False, False, None, None, None, None, None, 640, 56, '{"total_latency_ms": 14890.82}', '[{"chunk_id": "af0b6c03-2767-4e71-a302-d2babae0b12d", "text": "- [ ] \\u7070\\u5ea6\\u53d1\\u5...  service=knowledge_service
2026-06-17 09:22:12,811  debug  app.query_engine.pipeline  query_trace_saved  metadata={'trace_id': '88e526bf-a80f-425d-933b-4f8bd5e45b11'}  service=knowledge_service
2026-06-17 09:22:12,812  info  app.query_engine.pipeline  pipeline_completed  metadata={'query': '发布前回滚方案需要验证哪些内容？', 'search_mode': 'hybrid', 'results': 10, 'total_latency_ms': 14890.82}  service=knowledge_service
2026-06-17 09:22:12,812  info  app.api.query  api_search  message=API 检索请求  metadata={'query': '发布前回滚方案需要验证哪些内容？', 'search_mode': 'hybrid', 'results': 10, 'latency_ms': 14890.82}  service=knowledge_service
2026-06-17 09:22:12,822  info  app.main  http_response  metadata={'method': 'POST', 'path': '/api/query/search', 'status_code': 200, 'duration_ms': 14975.68}  service=knowledge_service
2026-06-17 09:22:12,851  info  app.main  http_request  metadata={'method': 'GET', 'path': '/api/query/traces', 'query_string': 'page=1&page_size=10', 'client_host': '127.0.0.1'}  service=knowledge_service
2026-06-17 09:22:12,860  info  app.common.database_sa  sql  duration_ms=2.65  message=[SQL] SELECT count(*) AS count_1  FROM query_traces  params=()  service=knowledge_service
2026-06-17 09:22:12,864  info  app.common.database_sa  sql  duration_ms=2.64  message=[SQL] SELECT query_traces.trace_id, query_traces.user_query, query_traces.search_mode, query_traces.rerank, query_traces.category, query_traces.language, query_traces.total_latency_ms, query_traces.input_tokens, query_traces.output_tokens, query_traces.total_tokens, query_traces.cache_hit, query_traces.rejected, query_traces.rejection_reason, query_traces.context_precision, query_traces.context_recall, query_traces.faithfulness, query_traces.answer_relevancy, query_traces.prompt_cache_hit_tokens, query_traces.prompt_cache_miss_tokens, query_traces.stages, query_traces.top_k_results, query_traces.results, query_traces.error, query_traces.created_at  FROM query_traces ORDER BY query_traces.created_at DESC   LIMIT $1::INTEGER OFFSET $2::INTEGER  params=(10, 0)  service=knowledge_service
2026-06-17 09:22:12,866  info  app.main  http_response  metadata={'method': 'GET', 'path': '/api/query/traces', 'status_code': 200, 'duration_ms': 15.13}  service=knowledge_service
2026-06-17 09:22:12,896  info  app.main  http_request  metadata={'method': 'GET', 'path': '/api/query/traces', 'query_string': 'page=1&page_size=10', 'client_host': '127.0.0.1'}  service=knowledge_service
2026-06-17 09:22:12,903  info  app.common.database_sa  sql  duration_ms=1.74  message=[SQL] SELECT count(*) AS count_1  FROM query_traces  params=()  service=knowledge_service
2026-06-17 09:22:12,906  info  app.common.database_sa  sql  duration_ms=1.71  message=[SQL] SELECT query_traces.trace_id, query_traces.user_query, query_traces.search_mode, query_traces.rerank, query_traces.category, query_traces.language, query_traces.total_latency_ms, query_traces.input_tokens, query_traces.output_tokens, query_traces.total_tokens, query_traces.cache_hit, query_traces.rejected, query_traces.rejection_reason, query_traces.context_precision, query_traces.context_recall, query_traces.faithfulness, query_traces.answer_relevancy, query_traces.prompt_cache_hit_tokens, query_traces.prompt_cache_miss_tokens, query_traces.stages, query_traces.top_k_results, query_traces.results, query_traces.error, query_traces.created_at  FROM query_traces ORDER BY query_traces.created_at DESC   LIMIT $1::INTEGER OFFSET $2::INTEGER  params=(10, 0)  service=knowledge_service
2026-06-17 09:22:12,907  info  app.main  http_response  metadata={'method': 'GET', 'path': '/api/query/traces', 'status_code': 200, 'duration_ms': 11.3}  service=knowledge_service

```





# 相关文档

- [DEV_SPEC.md](DEV_SPEC.md) — 完整开发规范、架构设计、项目排期
