import type { Alert } from '../types';

export const initialAlerts: Alert[] = [
  {
    id: 'alt-101',
    timestamp: new Date(Date.now() - 32 * 60000).toISOString(), // 32 mins ago
    roomId: 'room-001',
    cameraId: 'camera-001',
    type: 'temperature',
    value: 29.4,
    threshold: 28.0,
    severity: 'warning',
    status: 'active',
    imageUrl: 'crop_sim.jpg'
  }
];
