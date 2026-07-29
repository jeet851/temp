import { apiClient } from './apiClient';
import { mockEngine } from '../mock/mockEngine';
import { USE_MOCK } from '../config';
import { wsManager } from './wsManager';
import type { Camera } from '../types';

export const cameraService = {
  async getCameras(roomId?: string): Promise<Camera[]> {
    if (USE_MOCK) {
      const all = mockEngine.getCameras();
      if (!roomId || roomId === 'all') return all;
      return all.filter(c => c.roomId === roomId);
    }

    const path = roomId && roomId !== 'all' ? `/cameras?room_id=${roomId}` : '/cameras';
    const res = await apiClient.get<{ data: Camera[] }>(path);
    return res.data;
  },

  subscribeToCameraStatus(callback: (camera: Camera) => void): () => void {
    if (USE_MOCK) {
      return () => {};
    }
    return wsManager.on('cameraStatusChanged', callback);
  }
};

export type CameraService = typeof cameraService;
