/* ============================================================================
 * Knowledge Service — Axios HTTP 客户端
 * ============================================================================ */

import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// 响应拦截：统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败';
    console.error('[API Error]', message);
    return Promise.reject(error);
  },
);

export default apiClient;
