import { apiClient } from './apiClient';
import { wsManager } from './wsManager';
import { mockEngine } from '../mock/mockEngine';
import { USE_MOCK } from '../config';
import type { Alert } from '../types';

export const alertService = {
  async getAlerts(roomId?: string): Promise<Alert[]> {
    if (USE_MOCK) {
      const all = mockEngine.getAlerts();
      if (!roomId || roomId === 'all') return all;
      return all.filter(a => a.roomId === roomId);
    }

    const path = roomId ? `/alerts?room_id=${roomId}` : '/alerts';
    const res = await apiClient.get<{ data: Alert[] }>(path);
    return res.data;
  },

  async acknowledgeAlert(alertId: string, operator: string = 'sysadmin@visionguard.net'): Promise<Alert> {
    if (USE_MOCK) {
      mockEngine.acknowledgeAlert(alertId, operator);
      const all = mockEngine.getAlerts();
      return all.find(a => a.id === alertId) as Alert;
    }

    const res = await apiClient.patch<{ data: Alert }>(`/alerts/${alertId}/acknowledge`, {
      operator
    });
    return res.data;
  },

  async resolveAlert(alertId: string, operator: string, resolutionNotes: string): Promise<Alert> {
    if (USE_MOCK) {
      mockEngine.acknowledgeAlert(alertId, operator);
      const all = mockEngine.getAlerts();
      return all.find(a => a.id === alertId) as Alert;
    }

    const res = await apiClient.patch<{ data: Alert }>(`/alerts/${alertId}/resolve`, {
      operator,
      resolution_notes: resolutionNotes
    });
    return res.data;
  },

  // Subscribe to central database alerts list updates
  subscribeToAlerts(callback: (alerts: Alert[]) => void): () => void {
    if (USE_MOCK) {
      mockEngine.subscribe('alertsChanged', callback);
      return () => mockEngine.unsubscribe('alertsChanged', callback);
    }
    return wsManager.on('alertsChanged', callback);
  },

  // Subscribe to new triggered alarm alerts (for layout toasts)
  subscribeToAlertDispatch(callback: (data: { alert: Alert; roomName: string }) => void): () => void {
    if (USE_MOCK) {
      mockEngine.subscribe('alert', callback);
      return () => mockEngine.unsubscribe('alert', callback);
    }
    return wsManager.on('alert', callback);
  }
};

export type AlertService = typeof alertService;
