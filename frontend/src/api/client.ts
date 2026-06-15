/* ============================================================================
 * Knowledge Service — Axios HTTP 客户端
 * ============================================================================ */

import axios from 'axios';
import type { PaginatedResponse } from '../types';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// ── 请求去重（仅对 GET）：同一 URL + params 的并发请求共享 Promise ──
const inflightRequests = new Map<string, Promise<unknown>>();

const originalGet = apiClient.get.bind(apiClient);
apiClient.get = ((url: string, config?: Record<string, unknown>) => {
  const key = `${url}:${JSON.stringify(config?.params ?? {})}`;
  const existing = inflightRequests.get(key);
  if (existing) return existing as ReturnType<typeof originalGet>;

  const promise = originalGet(url, config).finally(() => {
    setTimeout(() => inflightRequests.delete(key), 0);
  });
  inflightRequests.set(key, promise);
  return promise;
}) as typeof apiClient.get;

// 响应拦截：统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败';
    console.error('[API Error]', message);
    return Promise.reject(error);
  },
);

// ── Pagination unwrap helper ────────────────────────────────
// Backend paginated endpoints return { items, total, page, page_size }
export async function unwrapPaginated<T>(
  promise: Promise<{ data: PaginatedResponse<T> }>,
): Promise<{ items: T[]; total: number; page: number; page_size: number }> {
  const r = await promise;
  return r.data;
}

export default apiClient;
