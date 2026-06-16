import apiClient, { unwrapPaginated } from './client';
import type { IngestionHistoryItem } from '../types';

export const uploadFile = (file: File, category: string = '', language: string = '') => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);
  formData.append('language', language);
  return apiClient.post('/ingestion/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);
};

export const getIngestionHistory = (params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<IngestionHistoryItem>(apiClient.get('/ingestion/history', { params }));
