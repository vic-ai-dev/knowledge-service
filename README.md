# Knowledge Service

RAG 知识服务平台 — 前后端分离架构。

## 目录结构

```
knowledge-service/
├── backend/          # FastAPI 后端（REST API + MCP SSE + WebSocket）
├── frontend/         # React + TypeScript 前端管理平台
├── config/           # 配置文件
├── scripts/          # 数据脚本
├── tests/            # 测试
└── DEV_SPEC.md       # 开发规范
```

## 快速开始

### 1. 数据库初始化

```bash
# knowledge 库（业务数据）
psql -d knowledge -f scripts/init_knowledge_db.sql

# knowledge_rag 库（向量 + BM25）
psql -d knowledge_rag -f scripts/init_knowledge_rag_db.sql
```

### 2. 启动后端

```bash
pip install -e .
uvicorn backend.main:app --reload --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 运行测试

```bash
pytest
```

## 文档

完整开发规范见 [DEV_SPEC.md](DEV_SPEC.md)。
