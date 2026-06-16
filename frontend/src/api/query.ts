import apiClient, { unwrapPaginated } from './client';
import type { QueryRequest, QueryResult, QueryTrace, QueryMetrics } from '../types';

export const executeQuery = (data: QueryRequest) =>
  apiClient.post<QueryResult>('/query/search', null, { params: data }).then((r) => r.data);

export const getQueryTraces = (params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<QueryTrace>(apiClient.get('/query/traces', { params }));

export const getQueryTraceDetail = (traceId: string) =>
  apiClient.get<QueryTrace>(`/query/traces/${traceId}`).then((r) => r.data);

export const getQueryMetrics = (params?: { period?: string }) =>
  apiClient.get<QueryMetrics>('/query/traces/metrics', { params }).then((r) => r.data);
