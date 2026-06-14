import apiClient, { unwrapPaginated } from './client';
import type { EvalResult, EvalRunRequest } from '../types';

export const runEvaluation = (data?: EvalRunRequest) =>
  apiClient.post<{ task_id: string; status: string }>('/evaluation/run', data).then((r) => r.data);

export const getTestSets = (params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<Record<string, unknown>>(apiClient.get('/evaluation/testsets', { params }));

export const getEvaluationResults = (params?: { page?: number; page_size?: number }) =>
  unwrapPaginated<EvalResult>(apiClient.get('/evaluation/results', { params }));
