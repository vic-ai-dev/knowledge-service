import apiClient from './client';
import type { EvalResult, EvalRunRequest } from '../types';

export const runEvaluation = (data?: EvalRunRequest) =>
  apiClient.post<{ run_id: string }>('/evaluation/run', data).then((r) => r.data);

export const getEvaluationResults = (params?: { page?: number; page_size?: number }) =>
  apiClient.get<EvalResult[]>('/evaluation/results', { params }).then((r) => r.data);

export const getEvaluationDetail = (id: string) =>
  apiClient.get<EvalResult>(`/evaluation/results/${id}`).then((r) => r.data);

export const getEvaluationHistory = () =>
  apiClient.get<Record<string, unknown>[]>('/evaluation/history').then((r) => r.data);
