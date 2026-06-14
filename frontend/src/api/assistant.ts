import apiClient, { unwrapPaginated } from './client';
import type {
  AssistantQueryRequest,
  QueryResult,
  Conversation,
  ConversationDetail,
} from '../types';

export const askAssistant = (data: AssistantQueryRequest) =>
  apiClient.post<QueryResult>('/assistant/ask', data).then((r) => r.data);

export const getConversationHistory = (params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<Conversation>(apiClient.get('/assistant/sessions', { params }));

export const getConversationDetail = (sessionId: string) =>
  apiClient.get<ConversationDetail>(`/assistant/sessions/${sessionId}`).then((r) => r.data);

export const deleteConversation = (sessionId: string) =>
  apiClient.delete(`/assistant/sessions/${sessionId}`).then((r) => r.data);
