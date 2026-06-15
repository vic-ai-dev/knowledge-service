import apiClient, { unwrapPaginated } from './client';
import type { UploadResult, IngestionTrace, IngestionHistoryItem } from '../types';

export const uploadFile = (file: File, category: string = '', language: string = '', collection: string = 'default') => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);
  formData.append('language', language);
  formData.append('collection', collection);
  return apiClient.post<UploadResult>('/ingestion/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);
};

export const getIngestionHistory = (params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<IngestionHistoryItem>(apiClient.get('/ingestion/history', { params }));

export const getIngestionTraces = (params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<IngestionTrace>(apiClient.get('/ingestion/traces', { params }));

export const getIngestionTraceDetail = (traceId: string) =>
  apiClient.get<IngestionTrace>(`/ingestion/traces/${traceId}`).then((r) => r.data);

export const getIngestionStatus = (runId: string) =>
  apiClient.get(`/ingestion/status/${runId}`).then((r) => r.data);
