import { apiClient } from './apiClient';
import { wsManager } from './wsManager';
import { mockEngine } from '../mock/mockEngine';
import { USE_MOCK } from '../config';
import type { Threshold } from '../types';

export const settingsService = {
  async getThresholds(): Promise<Threshold> {
    if (USE_MOCK) {
      return mockEngine.getThresholds();
    }

    const res = await apiClient.get<{ data: { tempWarning: number; tempCritical: number; humWarning: number; humCritical: number } }>('/settings/thresholds');
    return {
      tempWarning: res.data.tempWarning,
      tempCritical: res.data.tempCritical,
      humWarning: res.data.humWarning,
      humCritical: res.data.humCritical
    };
  },

  async saveThresholds(t: Threshold): Promise<void> {
    if (USE_MOCK) {
      mockEngine.setThresholds(t);
      return;
    }

    await apiClient.put('/settings/thresholds', {
      temp_warning: t.tempWarning,
      temp_critical: t.tempCritical,
      hum_warning: t.humWarning,
      hum_critical: t.humCritical
    });
  },

  subscribeToThresholds(callback: (thresholds: Threshold) => void): () => void {
    if (USE_MOCK) {
      mockEngine.subscribe('thresholds', callback);
      return () => mockEngine.unsubscribe('thresholds', callback);
    }
    return wsManager.on('thresholds', callback);
  }
};

export type SettingsService = typeof settingsService;
