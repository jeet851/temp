import type { Camera } from '../types';

export const initialCameras: Camera[] = [
  { 
    id: 'camera-001', 
    name: 'CCTV CAM-101 (Rack A1-A4)', 
    roomId: 'room-001', 
    rtspUrl: 'rtsp://admin:admin@123@10.215.75.201/live', 
    status: 'online', 
    fps: 30, 
    latencyMs: 45, 
    ocrConfidence: 98.4,
    lastSeenAt: null
  }
];
