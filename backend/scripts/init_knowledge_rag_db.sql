-- ============================================================================
-- Knowledge Service — knowledge_rag 库初始化（向量 + 全文检索）
--
-- 向量检索使用 pgvector 扩展。
-- 全文检索使用 rank_bm25（Python 内存库），BM25 评分在应用层实现。
-- ============================================================================
-- 运行方式：
--   psql -d knowledge_rag -f scripts/init_knowledge_rag_db.sql
-- ============================================================================

-- ============================================================================
-- 扩展安装
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 注意事项（BM25 全文检索）
-- ============================================================================
-- BM25 稀疏检索使用 rank_bm25（Python 内存库），在应用层完成。
-- 索引构建流程：
--   1. 从 document_chunks 表加载全量文本
--   2. jieba 分词（中英文混合）
--   3. BM25Okapi 模型构建于内存
-- 数据更新后通过脏标记（dirty flag）在下次 query 时自动重建。
--
-- 当前方案优势：
--   1. 无需数据库扩展，零依赖
--   2. BM25 参数（k1, b）可在应用层灵活调优
--   3. 与 pgvector 完全兼容，混合同一查询
--   4. 支持中英文混合分词
--
-- 参见 TODOLIST: T11 - BM25 索引重建与预热策略
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
    metadata          JSONB DEFAULT '{}'::jsonb,
    category          TEXT,
    language          TEXT,
    doc_type          TEXT,
    doc_id            UUID,
    chunk_index       INTEGER,
    source_path       TEXT,
    token_count       INTEGER DEFAULT 0,
    embedding         vector(1024),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE document_chunks IS '文档 Chunk 表：文本 + BM25 全文检索 + 向量 + 元数据，支持 Dense / Sparse / Hybrid 三种检索模式';

-- pgvector HNSW 索引（高并发场景推荐）
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- B-tree 过滤索引
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_category ON document_chunks(category);
CREATE INDEX IF NOT EXISTS idx_chunks_language ON document_chunks(language);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_type ON document_chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON document_chunks(doc_id, chunk_index);

-- ============================================================================
-- 3. 检索日志表
-- ============================================================================


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
-- BM25 稀疏检索基于 rank_bm25（Python 内存库），
-- 索引由 BM25Indexer 在应用层维护。
-- 数据写入后通过脏标记自动重建，无需 DBA 手动处理。
--
-- 参见 TODOLIST: T12 - BM25 索引增量更新（避免全量重建）
