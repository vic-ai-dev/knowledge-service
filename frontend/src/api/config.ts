/* ============================================================================
 * Knowledge Service — 系统配置 & 统计 API
 * ============================================================================ */

import apiClient from './client';
import type { HealthResponse, SystemConfig, SystemStats } from '../types';

export const getHealth = () =>
  apiClient.get<HealthResponse>('/health').then((r) => r.data);

export const getConfig = () =>
  apiClient.get<SystemConfig>('/config').then((r) => r.data);

export const getStats = () =>
  apiClient.get<SystemStats>('/stats').then((r) => r.data);
