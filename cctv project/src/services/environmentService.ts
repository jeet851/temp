import { apiClient } from './apiClient';
import { wsManager } from './wsManager';
import { mockEngine } from '../mock/mockEngine';
import { USE_MOCK } from '../config';
import type { Room, EnvironmentalReading, EnvironmentalHistory, OcrResult } from '../types';

export const environmentService = {
  async getRooms(): Promise<Room[]> {
    if (USE_MOCK) {
      return mockEngine.getRooms();
    }
    const res = await apiClient.get<{ data: Room[] }>('/rooms');
    return res.data;
  },

  async getReadings(roomId?: string): Promise<EnvironmentalReading[]> {
    if (USE_MOCK) {
      const all = mockEngine.getReadings();
      if (!roomId || roomId === 'all') return all;
      return all.filter(r => r.roomId === roomId);
    }

    const path = roomId && roomId !== 'all' 
      ? `/environment/readings?room_id=${roomId}` 
      : '/environment/readings';
    const res = await apiClient.get<{ data: EnvironmentalReading[] }>(path);
    return res.data;
  },

  async getHistory(
    roomId?: string,
    riskLevel?: string,
    search?: string,
    startDate?: string,
    endDate?: string,
    page = 1,
    perPage = 10
  ): Promise<{ data: EnvironmentalHistory[]; total: number; pages: number }> {
    if (USE_MOCK) {
      let data = mockEngine.getHistory();
      if (roomId && roomId !== 'all') {
        data = data.filter(h => h.roomId === roomId);
      }
      if (riskLevel && riskLevel !== 'all') {
        data = data.filter(h => h.riskLevel === riskLevel);
      }
      if (search) {
        const q = search.toLowerCase();
        data = data.filter(h =>
          h.roomId.toLowerCase().includes(q) ||
          h.riskLevel.toLowerCase().includes(q)
        );
      }
      const total = data.length;
      const pages = Math.ceil(total / perPage);
      const start = (page - 1) * perPage;
      const paged = data.slice(start, start + perPage);
      return { data: paged, total, pages };
    }

    let path = `/environment/history?page=${page}&per_page=${perPage}`;
    if (roomId) path += `&room_id=${roomId}`;
    if (riskLevel && riskLevel !== 'all') path += `&risk_level=${riskLevel}`;
    if (search) path += `&search_query=${encodeURIComponent(search)}`;
    if (startDate) path += `&start_date=${encodeURIComponent(startDate)}`;
    if (endDate) path += `&end_date=${encodeURIComponent(endDate)}`;

    const res = await apiClient.get<{ data: EnvironmentalHistory[]; meta: { total: number; pages: number } }>(path);
    return {
      data: res.data,
      total: res.meta.total,
      pages: res.meta.pages
    };
  },

  async triggerManualCapture(
    roomId: string,
    temp: number,
    hum: number,
    ocrConfidence?: number,
    ocrSource?: string,
    imageSavedPath?: string
  ): Promise<EnvironmentalHistory> {
    if (USE_MOCK) {
      mockEngine.triggerManualCapture(roomId, temp, hum);
      const history = mockEngine.getHistory();
      return history[0];
    }

    const res = await apiClient.post<{ data: EnvironmentalHistory }>('/environment/history', {
      room_id: roomId,
      temperature: temp,
      humidity: hum,
      ocr_confidence: ocrConfidence,
      ocr_source: ocrSource,
      image_saved_path: imageSavedPath
    });
    return res.data;
  },

  async extractOcr(file: Blob, roomId: string): Promise<OcrResult> {
    if (USE_MOCK) {
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            temperature: parseFloat((22 + Math.random() * 5).toFixed(1)),
            humidity: parseFloat((45 + Math.random() * 15).toFixed(1)),
            ocrConfidence: parseFloat((92 + Math.random() * 7).toFixed(1)),
            tempDetail: { rawText: '24.5', value: 24.5, confidence: 0.96, roi: [50, 50, 105, 50] },
            humDetail: { rawText: '58.2', value: 58.2, confidence: 0.97, roi: [178, 50, 109, 50] },
            source: 'upload',
            processingMs: 120
          });
        }, 800);
      });
    }

    const formData = new FormData();
    formData.append('file', file, 'snapshot.jpg');
    formData.append('room_id', roomId);
    formData.append('save_annotated', 'true');

    const res = await apiClient.post<{ data: OcrResult }>('/ocr/extract', formData);
    return res.data;
  },

  async updateOcrConfig(lcdRoi: number[], lcdDetectMode?: 'contour' | 'fixed'): Promise<any> {
    if (USE_MOCK) {
      return { success: true };
    }
    const payload: any = {
      lcd_roi: lcdRoi,
      temp_roi: [lcdRoi[0], lcdRoi[1], lcdRoi[2], Math.round(lcdRoi[3] * 0.5)],
      hum_roi: [lcdRoi[0] + Math.round(lcdRoi[2] * 0.45), lcdRoi[1] + Math.round(lcdRoi[3] * 0.48), Math.round(lcdRoi[2] * 0.55), Math.round(lcdRoi[3] * 0.52)]
    };
    if (lcdDetectMode) {
      payload.lcd_detect_mode = lcdDetectMode;
    }
    const res = await apiClient.put<any>('/ocr/config', payload);
    return res.data;
  },

  async getOcrConfig(): Promise<any> {
    if (USE_MOCK) {
      return {
        lcd_roi: [130, 130, 100, 90],
        temp_roi: [130, 130, 100, 42],
        hum_roi: [178, 175, 52, 42],
        lcd_detect_mode: 'contour'
      };
    }
    const res = await apiClient.get<any>('/ocr/config');
    return res.data;
  },

  async triggerRtspCapture(roomId: string, rtspUrl?: string): Promise<OcrResult> {
    if (USE_MOCK) {
      const res = await this.extractOcr(new Blob(), roomId);
      res.source = 'rtsp';
      return res;
    }

    const payload: Record<string, string> = { source: 'rtsp', room_id: roomId };
    if (rtspUrl) payload.rtsp_url = rtspUrl;

    const res = await apiClient.post<{ data: OcrResult }>('/ocr/capture', payload);
    return res.data;
  },

  subscribeToReadings(callback: (reading: EnvironmentalReading) => void): () => void {
    if (USE_MOCK) {
      mockEngine.subscribe('reading', callback);
      return () => mockEngine.unsubscribe('reading', callback);
    }
    return wsManager.on('reading', callback);
  },

  subscribeToRooms(callback: (rooms: Room[]) => void): () => void {
    if (USE_MOCK) {
      mockEngine.subscribe('rooms', callback);
      return () => mockEngine.unsubscribe('rooms', callback);
    }
    return wsManager.on('rooms', callback);
  },

  subscribeToHistory(callback: (history: EnvironmentalHistory[]) => void): () => void {
    if (USE_MOCK) {
      mockEngine.subscribe('historyChanged', callback);
      return () => mockEngine.unsubscribe('historyChanged', callback);
    }
    return wsManager.on('historyChanged', callback);
  }
};

export type EnvironmentService = typeof environmentService;
