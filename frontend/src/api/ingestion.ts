import apiClient from './client';
import type { UploadResult, IngestionRunResult, IngestionTrace } from '../types';

export const uploadFile = (file: File, docType: string, category: string) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('doc_type', docType);
  formData.append('category', category);
  return apiClient.post<UploadResult>('/ingestion/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);
};

export const runIngestion = (data: {
  file_path: string;
  collection?: string;
  category?: string;
  language?: string;
}) => apiClient.post<IngestionRunResult>('/ingestion/run', data).then((r) => r.data);

export const getIngestionStatus = (runId: string) =>
  apiClient.get<IngestionRunResult>(`/ingestion/status/${runId}`).then((r) => r.data);

export const getIngestionHistory = (params?: { page?: number; page_size?: number }) =>
  apiClient.get<IngestionTrace[]>('/ingestion/history', { params }).then((r) => r.data);

export const getIngestionTraces = (params?: { page?: number; page_size?: number }) =>
  apiClient.get<IngestionTrace[]>('/ingestion/traces', { params }).then((r) => r.data);

export const getIngestionTraceDetail = (traceId: string) =>
  apiClient.get<IngestionTrace>(`/ingestion/traces/${traceId}`).then((r) => r.data);
