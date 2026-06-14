-- ============================================================================
-- Knowledge Service — knowledge_rag 库初始化（向量 + 全文检索）
--
-- 向量检索使用 pgvector 扩展。
-- 全文检索使用 PostgreSQL 内置的 tsvector/GIN（BM25 评分在应用层实现）。
-- ============================================================================
-- 运行方式：
--   psql -d knowledge_rag -f scripts/init_knowledge_rag_db.sql
-- ============================================================================

-- ============================================================================
-- 扩展安装
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 注意事项（pg_bm25/pg_search）
-- ============================================================================
-- ParadeDB pg_search/pg_bm25 扩展暂未安装（Alpine 环境暂不支持编译）。
-- BM25 稀疏检索评分在 Python 应用层实现，使用 PostgreSQL 内置
-- tsvector/GIN 索引作为倒排索引层。
--
-- 后续如需迁移到 ParadeDB/pg_search，请参考：
--   https://github.com/paradedb/paradedb
--
-- 当前方案优势：
--   1. 无需额外扩展，零依赖
--   2. BM25 参数（k1, b）可在应用层灵活调优
--   3. 与 pgvector 完全兼容，混合同一查询
--
-- 参见 TODOLIST: T11 — pg_bm25 索引重建窗口
-- ============================================================================


-- ============================================================================
-- 1. 集合表
-- ============================================================================
CREATE TABLE IF NOT EXISTS collections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    document_count  INTEGER DEFAULT 0,
    chunk_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE collections IS '文档集合：逻辑命名空间，支持多知识库隔离';


-- ============================================================================
-- 2. 文档 Chunk 表（核心表，支持多种检索模式）
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text              TEXT NOT NULL,
    text_search       tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED,
    metadata          JSONB DEFAULT '{}'::jsonb,
    collection        TEXT NOT NULL DEFAULT 'default',
    category          TEXT,
    language          TEXT,
    doc_type          TEXT,
    doc_id            UUID,
    chunk_index       INTEGER,
    source_path       TEXT,
    token_count       INTEGER DEFAULT 0,
    embedding         vector(1536),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE document_chunks IS '文档 Chunk 表：文本 + tsvector 全文检索 + 向量 + 元数据，支持 Dense / Sparse / Hybrid 三种检索模式';

-- pgvector HNSW 索引（高并发场景推荐）
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- B-tree 过滤索引
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_category ON document_chunks(category);
CREATE INDEX IF NOT EXISTS idx_chunks_language ON document_chunks(language);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_type ON document_chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_chunks_collection ON document_chunks(collection);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON document_chunks(doc_id, chunk_index);

-- 全文检索索引（tsvector/GIN，应用层实现 BM25 评分）
CREATE INDEX IF NOT EXISTS idx_chunks_text_search ON document_chunks USING GIN (text_search);

COMMENT ON INDEX idx_chunks_text_search IS '全文检索索引（tsvector/GIN），满足关键词精确匹配场景';


-- ============================================================================
-- 3. 检索日志表
-- ============================================================================
CREATE TABLE IF NOT EXISTS retrieval_log (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        UUID NOT NULL,
    query_text      TEXT NOT NULL,
    search_mode     TEXT CHECK (search_mode IN ('dense', 'sparse', 'hybrid')),
    category_filter TEXT,
    language_filter TEXT,
    top_k           INTEGER,
    rerank_backend  TEXT,
    total_latency_ms INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cache_hit       BOOLEAN DEFAULT FALSE,
    result_chunk_ids TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_log_trace ON retrieval_log(trace_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_log_created ON retrieval_log(created_at DESC);

COMMENT ON TABLE retrieval_log IS '检索日志：记录每次查询的模式、参数和结果，用于分析调优';


-- ============================================================================
-- 4. 向量索引维护函数
-- ============================================================================
CREATE OR REPLACE FUNCTION reindex_embeddings_hnsw(
    m INTEGER DEFAULT 16,
    ef_construction INTEGER DEFAULT 200
)
RETURNS TEXT AS $$
DECLARE
    row_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count FROM document_chunks;
    IF row_count > 0 THEN
        DROP INDEX IF EXISTS idx_chunks_embedding;
        EXECUTE format(
            'CREATE INDEX idx_chunks_embedding ON document_chunks '
            'USING hnsw (embedding vector_cosine_ops) WITH (m = %s, ef_construction = %s)',
            m, ef_construction
        );
    END IF;
    RETURN format('Reindexed HNSW(m=%s, ef_construction=%s) (rows=%s)', m, ef_construction, row_count);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION reindex_embeddings_hnsw IS '根据当前数据量重新构建 HNSW 向量索引';


-- ============================================================================
-- 5. BM25 全文检索说明
-- ============================================================================
-- 当前使用 PostgreSQL tsvector/GIN，无需像 pg_search 那样重建 BM25 索引。
-- 当文档大量写入后，可通过 REINDEX 整理索引性能：
--
--   REINDEX INDEX idx_chunks_text_search;
--
-- 后续迁移到 pg_bm25 后，会恢复使用专用的 reindex_bm25() 函数。
