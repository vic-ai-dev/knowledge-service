import apiClient from './client';
import type { QueryRequest, QueryResult, QueryTrace, QueryMetrics } from '../types';

export const executeQuery = (data: QueryRequest) =>
  apiClient.post<QueryResult>('/query', data).then((r) => r.data);

export const getQueryTraces = (params?: { page?: number; page_size?: number }) =>
  apiClient.get<QueryTrace[]>('/query/traces', { params }).then((r) => r.data);

export const getQueryTraceDetail = (traceId: string) =>
  apiClient.get<QueryTrace>(`/query/traces/${traceId}`).then((r) => r.data);

export const getQueryMetrics = (params?: { period?: string }) =>
  apiClient.get<QueryMetrics>('/query/metrics', { params }).then((r) => r.data);
