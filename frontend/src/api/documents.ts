import apiClient, { unwrapPaginated } from './client';
import type { DocumentInfo, ChunkRecord, Collection, CollectionsResponse, CategoriesResponse, LanguagesResponse } from '../types';

export const listDocuments = (params?: {
  category?: string;
  language?: string;
  doc_type?: string;
  page?: number;
  page_size?: number;
}) => unwrapPaginated<DocumentInfo>(apiClient.get('/documents', { params }));

export const getDocumentDetail = (id: string) =>
  apiClient.get<DocumentInfo>(`/documents/${id}`).then((r) => r.data);

export const getDocumentChunks = (id: string, params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<ChunkRecord>(apiClient.get(`/documents/${id}/chunks`, { params }));

export const getChunkDetail = (chunkId: string) =>
  apiClient.get<ChunkRecord>(`/data/chunks/${chunkId}`).then((r) => r.data);

export const updateDocument = (id: string, data: Partial<DocumentInfo>) =>
  apiClient.put(`/documents/${id}`, data).then((r) => r.data);

export const deleteDocument = (id: string) =>
  apiClient.delete(`/documents/${id}`).then((r) => r.data);

export const batchDeleteDocuments = (ids: string[]) =>
  apiClient.post('/documents/batch-delete', { ids }).then((r) => r.data);

export const reindexDocument = (id: string) =>
  apiClient.post(`/documents/${id}/reindex`).then((r) => r.data);

export const listCollections = () =>
  apiClient.get<CollectionsResponse>('/data/collections').then((r) => r.data.collections);

export const createCollection = (data: { name: string; description?: string }) =>
  apiClient.post('/data/collections', data).then((r) => r.data);

export const deleteCollection = (name: string) =>
  apiClient.delete(`/data/collections/${name}`).then((r) => r.data);

export const getDocumentStats = () =>
  apiClient.get('/documents/stats').then((r) => r.data);

export const getCategories = () =>
  apiClient.get<CategoriesResponse>('/data/categories').then((r) => r.data.categories);

export const getLanguages = () =>
  apiClient.get<LanguagesResponse>('/data/languages').then((r) => r.data.languages);
