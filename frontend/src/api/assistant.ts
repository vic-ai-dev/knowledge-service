import apiClient from './client';
import type {
  AssistantQueryRequest,
  QueryResult,
  Conversation,
  ConversationDetail,
} from '../types';

export const askAssistant = (data: AssistantQueryRequest) =>
  apiClient.post<QueryResult>('/assistant/query', data).then((r) => r.data);

export const getConversationHistory = (params?: { page?: number; page_size?: number }) =>
  apiClient.get<Conversation[]>('/assistant/history', { params }).then((r) => r.data);

export const getConversationDetail = (convId: string) =>
  apiClient.get<ConversationDetail>(`/assistant/history/${convId}`).then((r) => r.data);

export const deleteConversation = (convId: string) =>
  apiClient.delete(`/assistant/history/${convId}`).then((r) => r.data);
