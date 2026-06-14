/* ============================================================================
 * Knowledge Service — 系统配置 & 统计 API
 * ============================================================================ */

import apiClient from './client';
import type { SystemConfig, SystemStats } from '../types';

/** 获取系统配置 */
export const getConfig = () =>
  apiClient.get<SystemConfig>('/system/config').then((r) => r.data);

/** 获取系统统计信息 */
export const getStats = () =>
  apiClient.get<SystemStats>('/system/stats').then((r) => r.data);
