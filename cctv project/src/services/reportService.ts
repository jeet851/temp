import { environmentService } from './environmentService';
import { alertService } from './alertService';
import { USE_MOCK, getApiBaseUrl } from '../config';
import type { ReportSummary } from '../types';

export const reportService = {
  async getAggregates(roomId: string): Promise<ReportSummary> {
    if (USE_MOCK) {
      let historyRes = await environmentService.getHistory(roomId, 'all', '', '', '', 1, 1000);
      let history = historyRes.data;
      let alerts = await alertService.getAlerts(roomId);

      const tempValues = history.map(h => h.temperature);
      const humValues = history.map(h => h.humidity);

      const avgTemp = tempValues.length
        ? parseFloat((tempValues.reduce((a, b) => a + b, 0) / tempValues.length).toFixed(1))
        : 0;
      const maxTemp = tempValues.length ? parseFloat(Math.max(...tempValues).toFixed(1)) : 0;
      const minTemp = tempValues.length ? parseFloat(Math.min(...tempValues).toFixed(1)) : 0;

      const avgHum = humValues.length
        ? parseFloat((humValues.reduce((a, b) => a + b, 0) / humValues.length).toFixed(1))
        : 0;
      const maxHum = humValues.length ? parseFloat(Math.max(...humValues).toFixed(1)) : 0;
      const minHum = humValues.length ? parseFloat(Math.min(...humValues).toFixed(1)) : 0;

      return {
        avgTemp, maxTemp, minTemp,
        avgHum, maxHum, minHum,
        totalCaptures: history.length,
        alertSummary: {
          total: alerts.length,
          warnings: alerts.filter(a => a.severity === 'warning').length,
          criticals: alerts.filter(a => a.severity === 'critical').length
        }
      };
    }

    // Call active backend endpoints
    const historyRes = await environmentService.getHistory(roomId, 'all', '', '', '', 1, 1000);
    const history = historyRes.data;
    const alerts = await alertService.getAlerts(roomId);

    const tempValues = history.map(h => h.temperature);
    const humValues = history.map(h => h.humidity);

    const avgTemp = tempValues.length ? parseFloat((tempValues.reduce((a, b) => a + b, 0) / tempValues.length).toFixed(1)) : 0;
    const maxTemp = tempValues.length ? Math.max(...tempValues) : 0;
    const minTemp = tempValues.length ? Math.min(...tempValues) : 0;

    const avgHum = humValues.length ? parseFloat((humValues.reduce((a, b) => a + b, 0) / humValues.length).toFixed(1)) : 0;
    const maxHum = humValues.length ? Math.max(...humValues) : 0;
    const minHum = humValues.length ? Math.min(...humValues) : 0;

    return {
      avgTemp,
      maxTemp,
      minTemp,
      avgHum,
      maxHum,
      minHum,
      totalCaptures: history.length,
      alertSummary: {
        total: alerts.length,
        warnings: alerts.filter(a => a.severity === 'warning').length,
        criticals: alerts.filter(a => a.severity === 'critical').length
      }
    };
  },

  async downloadReport(roomId: string, roomName: string, reportScale: string, format: 'csv' | 'excel' | 'pdf'): Promise<void> {
    if (USE_MOCK) {
      await new Promise(resolve => setTimeout(resolve, 1200));
      let historyRes = await environmentService.getHistory(roomId, 'all', '', '', '', 1, 1000);
      let history = historyRes.data;

      if (format === 'pdf') {
        const lines = [
          `VisionGuard Environmental Monitoring Report (Mock)`,
          `Room: ${roomName} | Scale: ${reportScale} | Generated: ${new Date().toLocaleString()}`,
          ``,
          `Timestamp,Temperature (°C),Humidity (%RH),Risk Level,Smoke,Fire`,
          ...history.map(h =>
            `${new Date(h.timestamp).toLocaleString()},${h.temperature},${h.humidity},${h.riskLevel},${h.smokeDetected},${h.fireDetected}`
          )
        ];
        const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
        triggerDownload(blob, `visionguard_report_${roomId}_${reportScale}.txt`);
        return;
      }

      const csvRows = [
        `Timestamp,Temperature (°C),Humidity (%RH),Risk Level,Smoke Detected,Fire Detected`,
        ...history.map(h =>
          `${new Date(h.timestamp).toLocaleString()},${h.temperature},${h.humidity},${h.riskLevel},${h.smokeDetected},${h.fireDetected}`
        )
      ];
      const csvContent = csvRows.join('\n');
      const mimeType = format === 'excel' ? 'application/vnd.ms-excel' : 'text/csv';
      const ext = format === 'excel' ? 'csv' : 'csv';
      const blob = new Blob([csvContent], { type: mimeType });
      triggerDownload(blob, `visionguard_history_${roomId}_${reportScale}.${ext}`);
      return;
    }

    // Call active backend export gateway endpoint
    const formatParam = format === 'excel' ? 'excel' : (format === 'pdf' ? 'pdf' : 'csv');
    const ext = format === 'excel' ? 'xlsx' : (format === 'pdf' ? 'pdf' : 'csv');
    const path = `/exports/history?room_id=${roomId}&format=${formatParam}`;
    
    const token = localStorage.getItem('vg_session_token');
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}${path}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error('Report export failed');
    }

    const blob = await response.blob();
    triggerDownload(blob, `visionguard_history_${roomId}_${reportScale}.${ext}`);
  }
};

function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export type ReportService = typeof reportService;
