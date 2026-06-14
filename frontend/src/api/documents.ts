import apiClient from './client';
import type { DocumentInfo, ChunkRecord, Collection } from '../types';

export const listDocuments = (params?: {
  category?: string;
  language?: string;
  doc_type?: string;
  page?: number;
  page_size?: number;
}) => apiClient.get<DocumentInfo[]>('/documents', { params }).then((r) => r.data);

export const getDocumentDetail = (id: string) =>
  apiClient.get<DocumentInfo>(`/documents/${id}`).then((r) => r.data);

export const getDocumentChunks = (id: string) =>
  apiClient.get<ChunkRecord[]>(`/documents/${id}/chunks`).then((r) => r.data);

export const getChunkDetail = (chunkId: string) =>
  apiClient.get<ChunkRecord>(`/chunks/${chunkId}`).then((r) => r.data);

export const updateDocument = (id: string, data: Partial<DocumentInfo>) =>
  apiClient.put(`/documents/${id}`, data).then((r) => r.data);

export const deleteDocument = (id: string) =>
  apiClient.delete(`/documents/${id}`).then((r) => r.data);

export const batchDeleteDocuments = (ids: string[]) =>
  apiClient.post('/documents/batch-delete', { ids }).then((r) => r.data);

export const reindexDocument = (id: string) =>
  apiClient.post(`/documents/${id}/reindex`).then((r) => r.data);

export const listCollections = () =>
  apiClient.get<Collection[]>('/collections').then((r) => r.data);

export const createCollection = (data: { name: string; description?: string }) =>
  apiClient.post('/collections', data).then((r) => r.data);

export const deleteCollection = (name: string) =>
  apiClient.delete(`/collections/${name}`).then((r) => r.data);

export const getDocumentStats = () =>
  apiClient.get('/documents/stats').then((r) => r.data);
