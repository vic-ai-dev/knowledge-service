-- ============================================================================
-- Knowledge Service -- knowledge_rag 库初始化
--
-- !!!  ParadeDB API 说明：
--     下面的 paradedb.create_bm25() 调用基于 ParadeDB v0.20+ 语法。
--     ParadeDB 在持续迭代中，API 可能有变化。实际安装后如遇报错：
--     1. 检查 ParadeDB 版本: SELECT * FROM paradedb.version();
--     2. 查看当前版本的官方文档: https://docs.paradedb.com/
--     3. 调整 create_bm25 的参数格式或改用 pg_bm25 原生语法
--     各阶段 B/C/D 中用到 BM25 检索的地方也需要同步验证
-- ============================================================================

-- ============================================================================
-- Knowledge Service — knowledge_rag 库初始化（向量 + BM25 全文检索）
-- ============================================================================
-- 运行方式：
--   createdb knowledge_rag
--   psql -d knowledge_rag -f scripts/init_knowledge_rag_db.sql
-- ============================================================================

-- ============================================================================
-- 扩展安装（需要先安装 pgvector + pg_bm25 + pg_search）
-- pgvector:     https://github.com/pgvector/pgvector
-- pg_bm25:      https://github.com/paradedb/paradedb/tree/dev/pg_bm25
-- pg_search:    https://github.com/paradedb/paradedb/tree/dev/pg_search
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_bm25;
CREATE EXTENSION IF NOT EXISTS pg_search;

-- 用于检查扩展版本
SELECT current_setting('server_version_num')::int / 10000 AS pg_major_version;


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
-- 2. 文档 Chunk 表（核心表）
--    同时支持：
--      - pgvector: Dense 语义向量检索（embedding 列）
--      - pg_bm25:  Sparse 关键词 BM25 检索（text + metadata 上的 bm25 索引）
--      - pg_search: 混合检索（Dense + Sparse 统一排序）
-- ============================================================================

-- 使用 pg_search 的 paradedb 虚拟表语法创建
CALL paradedb.create_bm25(
    table_name => 'document_chunks',
    schema_name => 'public',
    columns => '{
        "id": {"tokenizer": {"type": "raw"}},
        "text": {"tokenizer": {"type": "default", "record": "position"}},
        "metadata": {"tokenizer": {"type": "default", "record": "position"}},
        "category": {"tokenizer": {"type": "raw"}},
        "language": {"tokenizer": {"type": "raw"}},
        "doc_type": {"tokenizer": {"type": "raw"}}
    }'::jsonb,
    text_config => '{
        "default": "english",
        "zh": {"type": "chinese"}
    }'::jsonb
);

-- 给 document_chunks 添加向量列
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS doc_id UUID;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunk_index INTEGER;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS source_path TEXT;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS token_count INTEGER DEFAULT 0;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON TABLE document_chunks IS '文档 Chunk 表：文本 + BM25 + 向量 + 元数据，支持 Dense / Sparse / Hybrid 三种检索模式';
COMMENT ON COLUMN document_chunks.embedding IS 'Dense Vector：OpenAI text-embedding-3-small (1536 维)，余弦相似度检索';
COMMENT ON COLUMN document_chunks.metadata IS '灵活 Metadata：{ title, summary, tags, page, image_refs, section_title, ... }';

-- pgvector 向量索引（IVFFlat：本地开发推荐，lists = sqrt(rows)）
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- B-tree 过滤索引（用于检索前的预过滤）
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_category ON document_chunks(category);
CREATE INDEX IF NOT EXISTS idx_chunks_language ON document_chunks(language);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_type ON document_chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_chunks_collection ON document_chunks(collection);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON document_chunks(doc_id, chunk_index);


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

COMMENT ON TABLE retrieval_log IS '检索日志：记录每次查询的模式、参数和结果，用于调优分析';


-- ============================================================================
-- 4. 检索模式参考（非表，仅作为查询示例）
-- ============================================================================

-- 4.1 纯 Dense 检索（pgvector）
-- SELECT id, text, metadata,
--        1 - (embedding <=> '[0.01, ...]'::vector) AS score
-- FROM document_chunks
-- WHERE category = 'architecture' AND language = 'zh'
-- ORDER BY embedding <=> '[0.01, ...]'::vector
-- LIMIT 20;

-- 4.2 纯 Sparse 检索（pg_bm25）
-- SELECT id, text, metadata,
--       paradedb.score(id) AS score
-- FROM document_chunks
-- WHERE category = 'technical_spec'
--   AND text @@@ 'BM25 查询关键词'
-- ORDER BY score DESC
-- LIMIT 20;

-- 4.3 混合检索（pg_search）
-- SELECT id, text, metadata,
--       paradedb.rank_hybrid(embedding <=> '[0.01, ...]'::vector, id, '混合查询')
--        AS score
-- FROM document_chunks
-- WHERE category = 'architecture' AND language = 'zh'
-- ORDER BY score DESC
-- LIMIT 20;


-- ============================================================================
-- 5. 向量索引维护函数
-- ============================================================================
CREATE OR REPLACE FUNCTION reindex_embeddings(new_lists INTEGER DEFAULT NULL)
RETURNS TEXT AS $$
DECLARE
    row_count INTEGER;
    lists INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count FROM document_chunks;
    lists := COALESCE(new_lists, GREATEST(1, FLOOR(SQRT(row_count))::INTEGER));
    DROP INDEX IF EXISTS idx_chunks_embedding;
    EXECUTE format(
        'CREATE INDEX idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = %s)',
        lists
    );
    RETURN format('Reindexed with lists=%s (rows=%s)', lists, row_count);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION reindex_embeddings IS '根据当前数据量重新构建 IVFFlat 向量索引';
