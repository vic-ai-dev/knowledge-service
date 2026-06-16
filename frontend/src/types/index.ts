/* ============================================================================
 * Knowledge Service — TypeScript 类型定义
 * ============================================================================ */

// ── 文档类型 ──────────────────────────────────────────────

export type DocType = 'pdf' | 'md' | 'html';
export type Category = 'employee_handbook' | 'compliance' | 'technical_spec' | 'architecture';
export type Language = 'zh' | 'en';
export type SearchMode = 'vector_only' | 'hybrid';
export type IngestionStatus = 'success' | 'failed' | 'processing';

export interface DocumentInfo {
  id: string;
  source_path: string;
  title?: string;
  category: Category;
  language: Language;
  doc_type: DocType;
  file_size?: number;
  chunk_count: number;
  ingested_at?: string;
  updated_at?: string;
  is_deleted: boolean;
}

export interface ChunkRecord {
  id: string;
  doc_id: string;
  chunk_index: number;
  text: string;
  metadata: Record<string, unknown>;
  source_path: string;
  token_count: number;
  embedding?: number[];
  created_at: string;
}


// ── 摄取 ──────────────────────────────────────────────────

export interface UploadResult {
  file_path: string;
  file_hash: string;
  doc_type: DocType;
  category: Category;
}

export interface IngestionRunResult {
  task_id: string;
  status: string
  filename?: string;
  size?: number;
  message?: string;
}

export interface IngestionHistoryItem {
  id: string;
  file_hash: string;
  file_path: string;
  file_size: number;
  status: string;
  category: string;
  language: string;
  doc_type: string;
  chunk_count: number;
  error_msg: string | null;
  processed_at: string | null;
}

export interface IngestionTrace {
  trace_id: string;
  source_path: string;
  total_latency_ms: number;
  status: IngestionStatus;
  total_chunks: number;
  total_images: number;
  stages?: Record<string, unknown>;
  error?: string;
  created_at: string;
}

// ── 查询 ──────────────────────────────────────────────────

export interface QueryRequest {
  query: string;
  search_mode: SearchMode;
  rerank: boolean;
}

export interface RetrievalResult {
  chunk_id: string;
  text: string;
  metadata: Record<string, unknown>;
  score: number;
  source_path?: string;
}

export interface QueryResult {
  query: string;
  results: RetrievalResult[];
  trace_id: string;
  total_latency_ms: number;
  answer: string;
  citations: Array<{ chunk_id: string; text: string; source: string }>;
  session_id: string;
}

export interface QueryTrace {
  trace_id: string;
  user_query: string;
  category?: Category;
  language?: Language;
  total_latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cache_hit: boolean;
  rejected: boolean;
  rejection_reason?: string;
  compliance_score?: number;
  stages?: Record<string, unknown>;
  top_k_results?: RetrievalResult[];
  error?: string;
  created_at: string;
}

export interface QueryMetrics {
  p50_latency_ms: number;
  p95_latency_ms: number;
  total_queries: number;
  total_input_tokens: number;
  total_output_tokens: number;
  cache_hit_rate: number;
  rejection_rate: number;
  avg_compliance_score: number;
}

// ── 评估 ──────────────────────────────────────────────────

export interface EvalResult {
  id: string;
  metrics: Record<string, number>;
  test_set: string;
  backends_used: string[];
  created_at: string;
}

export interface EvalRunRequest {
  test_set?: string;
  backends?: string[];
}

// ── AI 助手 ───────────────────────────────────────────────

export interface AssistantQueryRequest {
  query: string;
  search_mode: SearchMode;
  rerank: boolean;
  session_id?: string;
}

export interface Conversation {
  id: string;
  title: string;
  model: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{ chunk_id: string; text: string; source: string }>;
  token_count?: number;
  timestamp: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

// ── 系统 ──────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface SystemConfig {
  server: { port: number; max_file_size: number; allowed_extensions: string[] };
  database: { host: string; port: number; database: string };
  vector_store: { backend: string; host: string; port: number; database: string };
  llm: { provider: string; model: string };
  embedding: { provider: string; model: string };
  rerank: { provider: string; model: string; enabled: boolean };
  retrieval: { sparse_backend: string; fusion_algorithm: string };
}

export interface SystemStats {
  total_documents: number;
  total_chunks: number;
  total_categories: number;
  total_size_bytes: number;
  by_category: Record<string, number>;
  by_language: Record<string, number>;
}


// ── Paginated API response wrapper ──────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ── Collection wrapper ──────────────────────────────────────

// ── Category & Language types ──────────────────────────────
export interface CategoryItem {
  id: string;
  name: string;
}

export interface CategoriesResponse {
  categories: CategoryItem[];
}

export interface LanguagesResponse {
  languages: CategoryItem[];
}
