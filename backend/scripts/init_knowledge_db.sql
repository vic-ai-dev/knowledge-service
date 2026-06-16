-- ============================================================================
-- Knowledge Service — knowledge 库初始化（业务数据）
-- ============================================================================
-- 运行方式：
--   createdb knowledge
--   psql -d knowledge -f scripts/init_knowledge_db.sql
-- ============================================================================

-- 当所有字段定义用到的全部内容都没有中文时默认启用

-- 1. 文档注册表（新增：集中式文档元数据）
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_path     TEXT NOT NULL,
    title           TEXT,
    collection      TEXT NOT NULL DEFAULT 'default',
    category        TEXT NOT NULL CHECK (category IN ('employee_handbook', 'compliance', 'technical_spec', 'architecture')),
    language        TEXT NOT NULL CHECK (language IN ('zh', 'en')),
    doc_type        TEXT NOT NULL CHECK (doc_type IN ('pdf', 'md', 'html')),
    file_size       BIGINT,
    file_hash       TEXT UNIQUE,
    chunk_count     INTEGER DEFAULT 0,
    image_count     INTEGER DEFAULT 0,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    is_deleted      BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_language ON documents(language);
CREATE INDEX idx_documents_doc_type ON documents(doc_type);
CREATE INDEX idx_documents_collection ON documents(collection);

COMMENT ON TABLE documents IS '文档注册表：所有已摄入文档的元数据';
COMMENT ON COLUMN documents.category IS '知识分类：employee_handbook / compliance / technical_spec / architecture';
COMMENT ON COLUMN documents.language IS '语言：zh (中文) / en (英文)';
COMMENT ON COLUMN documents.doc_type IS '文件格式：pdf / md / html';


-- 2. 文件摄入历史表（SHA256 去重 + 增量更新）
--
-- 注意：id 使用 UUID 以兼容 FileIntegrityChecker 的跨服务追踪语义。
DROP TABLE IF EXISTS ingestion_history CASCADE;
CREATE TABLE IF NOT EXISTS ingestion_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID,
    source_path     TEXT NOT NULL,
    file_hash       TEXT NOT NULL,
    file_size       BIGINT,
    status          TEXT NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    category        TEXT,
    language        TEXT,
    doc_type        TEXT,
    total_chunks    INTEGER DEFAULT 0,
    total_images    INTEGER DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ingestion_hash ON ingestion_history(file_hash);
CREATE INDEX idx_ingestion_status ON ingestion_history(status);
CREATE INDEX idx_ingestion_created_at ON ingestion_history(created_at);

COMMENT ON TABLE ingestion_history IS '文件摄入历史：SHA256 去重 + 增量更新状态追踪';
COMMENT ON COLUMN ingestion_history.document_id IS '关联的文档 ID（documents.id）';
COMMENT ON COLUMN ingestion_history.source_path IS '源文件路径';
COMMENT ON COLUMN ingestion_history.status IS '状态：processing / completed / failed';
COMMENT ON COLUMN ingestion_history.total_chunks IS '摄入的 Chunk 总数';
COMMENT ON COLUMN ingestion_history.total_images IS '摄入的图片总数（含跨模态）';
COMMENT ON COLUMN ingestion_history.error_message IS '失败时的错误信息';
COMMENT ON COLUMN ingestion_history.started_at IS '处理开始时间';
COMMENT ON COLUMN ingestion_history.completed_at IS '处理完成时间';
COMMENT ON COLUMN ingestion_history.created_at IS '记录创建时间';

COMMENT ON TABLE ingestion_history IS '文件摄入历史：SHA256 去重，避免重复处理未变更文件';


-- 3. 图片索引表
CREATE TABLE IF NOT EXISTS image_index (
    id              BIGSERIAL PRIMARY KEY,
    image_id        TEXT NOT NULL UNIQUE,
    file_path       TEXT NOT NULL,
    collection      TEXT NOT NULL DEFAULT 'default',
    doc_hash        TEXT,
    page_num        INTEGER,
    category        TEXT,
    language        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_image_id ON image_index(image_id);
CREATE INDEX idx_image_doc_hash ON image_index(doc_hash);

COMMENT ON TABLE image_index IS '图片索引：image_id 到本地文件路径的映射';


-- 4. Ingestion 追踪表
CREATE TABLE IF NOT EXISTS ingestion_traces (
    trace_id        UUID PRIMARY KEY,
    source_path     TEXT NOT NULL,
    collection      TEXT DEFAULT 'default',
    document_id     UUID,
    total_latency_ms INTEGER,
    status          TEXT CHECK (status IN ('completed', 'failed')),
    total_chunks    INTEGER,
    total_images    INTEGER,
    stages          JSONB,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ingestion_traces_created ON ingestion_traces(created_at DESC);
CREATE INDEX idx_ingestion_traces_status ON ingestion_traces(status);

COMMENT ON TABLE ingestion_traces IS 'Ingestion 追踪记录，stage 为 JSONB 存储各阶段详情';


-- 5. Query 追踪表
CREATE TABLE IF NOT EXISTS query_traces (
    trace_id        UUID PRIMARY KEY,
    user_query      TEXT NOT NULL,
    search_mode     TEXT,
    rerank          BOOLEAN,

    collection      TEXT DEFAULT 'default',
    category        TEXT,
    language        TEXT,
    total_latency_ms INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    total_tokens    INTEGER,
    cache_hit       BOOLEAN DEFAULT FALSE,
    rejected        BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,
    compliance_score FLOAT,
    stages          JSONB,
    top_k_results   JSONB,
    results         TEXT,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_query_traces_created ON query_traces(created_at DESC);
CREATE INDEX idx_query_traces_query ON query_traces USING gin(to_tsvector('simple', user_query));

COMMENT ON TABLE query_traces IS 'Query 追踪记录：含 p50/p95 延迟来源 (total_latency_ms)、令牌用量、缓存命中、拒绝率、答案符合率';
COMMENT ON COLUMN query_traces.input_tokens IS '输入令牌数（LLM + Embedding 调用）';
COMMENT ON COLUMN query_traces.output_tokens IS '输出令牌数（LLM 响应）';
COMMENT ON COLUMN query_traces.total_tokens IS '总令牌数 = input + output';
COMMENT ON COLUMN query_traces.cache_hit IS '查询是否命中缓存（Embedding / 结果缓存）';
COMMENT ON COLUMN query_traces.rejected IS '查询是否被拒绝（限流 / 内容过滤）';
COMMENT ON COLUMN query_traces.rejection_reason IS '拒绝原因';
COMMENT ON COLUMN query_traces.compliance_score IS '答案符合率 0-1，基于 LLM-as-Judge 或规则判定';

-- 6. 评估结果表
CREATE TABLE IF NOT EXISTS evaluation_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metrics         JSONB NOT NULL,
    test_set        TEXT,
    backends_used   JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_eval_created ON evaluation_results(created_at DESC);

COMMENT ON TABLE evaluation_results IS '评估结果，metrics 为 JSONB 存储 hit_rate / mrr / faithfulness 等';


-- 7. 黄金测试集
CREATE TABLE IF NOT EXISTS golden_test_set (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    queries         JSONB NOT NULL,
    category        TEXT,
    language        TEXT,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_golden_category ON golden_test_set(category);
CREATE INDEX idx_golden_language ON golden_test_set(language);

COMMENT ON TABLE golden_test_set IS '黄金测试集，用于 RAG 评估回归测试';
COMMENT ON COLUMN golden_test_set.queries IS 'JSONB 数组：[{"query":"...","ground_truth_chunks":[...],"expected_metrics":{...}}]';


-- 8. 对话记录表（AI 知识助手）
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    model           TEXT DEFAULT 'default',
    collection      TEXT DEFAULT 'default',
    category        TEXT,
    language        TEXT,
    message_count   INTEGER DEFAULT 0,
    messages        JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_created ON conversations(created_at DESC);
CREATE INDEX idx_conversations_category ON conversations(category);
CREATE INDEX idx_conversations_collection ON conversations(collection);

COMMENT ON TABLE conversations IS 'AI 知识助手对话记录';

COMMENT ON COLUMN conversations.messages IS 'JSONB 数组：[{"role":"user"/"assistant", "content":"...", "citations":[...], "token_count":N, "timestamp":"..."}]';
COMMENT ON COLUMN conversations.model IS '使用的 LLM 模型（如 gpt-4o-mini），从 settings.yaml 读取默认值';
COMMENT ON COLUMN conversations.collection IS '对话上下文所属集合';
COMMENT ON COLUMN conversations.category IS '对话上下文所属分类（过滤条件）';

-- 9. 查询结果缓存表（性能优化：P90 < 10s）
CREATE TABLE IF NOT EXISTS query_cache (
    cache_key   TEXT PRIMARY KEY,
    query_text  TEXT NOT NULL,
    search_mode TEXT,
    rerank      BOOLEAN,
    results     JSONB NOT NULL,
    hit_count   INTEGER DEFAULT 1,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '1 hour'
);

CREATE INDEX idx_query_cache_expires ON query_cache(expires_at);


-- ── Migration: Add search_mode / rerank to query_traces (for existing DBs) ──
ALTER TABLE query_traces
    ADD COLUMN IF NOT EXISTS search_mode TEXT,
    ADD COLUMN IF NOT EXISTS rerank BOOLEAN;

COMMENT ON COLUMN query_traces.search_mode IS '检索模式：vector_only / hybrid';
COMMENT ON COLUMN query_traces.rerank IS '是否启用重排序器';
