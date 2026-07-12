import { apiClient } from './apiClient';
import { mockEngine } from '../mock/mockEngine';
import { USE_MOCK } from '../config';
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
  }
};

export type CameraService = typeof cameraService;
