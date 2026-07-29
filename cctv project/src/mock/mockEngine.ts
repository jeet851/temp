import { initialRooms } from './rooms';
import { initialCameras } from './camera';
import { generateInitialReadings, generateInitialHistory } from './environment';
import { initialAlerts } from './alerts';
import { calculateDrift, checkReadingStatus } from './generator';
import type { Room, Camera, EnvironmentalReading, Alert, EnvironmentalHistory, Threshold } from '../types';

type Listener = (data: any) => void;

class MockEngine {
  private rooms: Room[] = [...initialRooms];
  private cameras: Camera[] = [...initialCameras];
  private readings: EnvironmentalReading[] = [];
  private history: EnvironmentalHistory[] = [];
  private alerts: Alert[] = [...initialAlerts];
  private thresholds: Threshold = {
    tempWarning: 28.0,
    tempCritical: 32.0,
    humWarning: 65.0,
    humCritical: 75.0,
    ocrPollingIntervalSeconds: 30,
    allowSyntheticFallback: false
  };

  private listeners: { [event: string]: Listener[] } = {};
  private timer: any = null;
  private tickCount = 0;

  constructor() {
    this.readings = generateInitialReadings();
    this.history = generateInitialHistory();
    this.startEngine();
  }

  private startEngine() {
    if (this.timer) return;
    this.timer = setInterval(() => {
      this.tick();
    }, 5000);
  }

  private tick() {
    // Ticks only for the single room Room-001
    const room = this.rooms[0];
    const camera = this.cameras[0];
    if (!room || !camera) return;

    const tempBase = 22.0;
    const humBase = 45.0;

    const temperature = calculateDrift(tempBase, 5);
    const humidity = calculateDrift(humBase, 10);
    const ocrConfidence = parseFloat((94 + Math.random() * 5.5).toFixed(1));
    const status = checkReadingStatus(temperature, humidity, this.thresholds);

    const newReading: EnvironmentalReading = {
      id: `r-sim-${Date.now()}`,
      timestamp: new Date().toISOString(),
      roomId: room.id,
      cameraId: camera.id,
      temperature,
      humidity,
      ocrConfidence,
      status,
      isSynthetic: false
    };

    this.readings.unshift(newReading);
    if (this.readings.length > 500) this.readings.pop();

    // Check thresholds to trigger alert
    if (status !== 'normal') {
      const type = (temperature >= this.thresholds.tempWarning) ? 'temperature' : 'humidity';
      const limitValue = type === 'temperature' ? temperature : humidity;
      const limitThreshold = type === 'temperature'
        ? (status === 'critical' ? this.thresholds.tempCritical : this.thresholds.tempWarning)
        : (status === 'critical' ? this.thresholds.humCritical : this.thresholds.humWarning);

      const hasActive = this.alerts.some(a => a.roomId === room.id && a.type === type && a.status === 'active');

      if (!hasActive) {
        const newAlert: Alert = {
          id: `alt-sim-${Date.now()}`,
          timestamp: new Date().toISOString(),
          roomId: room.id,
          cameraId: camera.id,
          type,
          value: limitValue,
          threshold: limitThreshold,
          severity: status === 'critical' ? 'critical' : 'warning',
          status: 'active',
          imageUrl: 'crop_sim.jpg'
        };

        this.alerts.unshift(newAlert);
        this.emit('alert', { alert: newAlert, roomName: room.name });
        this.emit('alertsChanged', this.alerts);
      }
    }

    // Recalculate room severity status based on active alerts
    this.rooms = this.rooms.map(r => {
      const rAlerts = this.alerts.filter(a => a.roomId === r.id && a.status === 'active');
      let rStatus: 'normal' | 'warning' | 'critical' = 'normal';
      if (rAlerts.some(a => a.severity === 'critical')) rStatus = 'critical';
      else if (rAlerts.some(a => a.severity === 'warning')) rStatus = 'warning';
      return { ...r, status: rStatus };
    });

    this.emit('reading', newReading);
    this.emit('rooms', this.rooms);

    // Simulate hourly snapshot logging: every 12 ticks (60 seconds) = 1 hour passing in simulator
    this.tickCount++;
    if (this.tickCount >= 12) {
      this.tickCount = 0;
      this.captureHourlySnapshot();
    }
  }

  private captureHourlySnapshot() {
    const latestReading = this.readings[0];
    if (!latestReading) return;

    const roomId = 'room-001';
    const cameraId = 'camera-001';
    const temp = latestReading.temperature;
    const hum = latestReading.humidity;
    const status = latestReading.status;

    let smoke = false;
    let fire = false;
    let risk: 'low' | 'medium' | 'high' = 'low';

    if (status === 'critical') {
      smoke = Math.random() > 0.4;
      fire = Math.random() > 0.6;
      risk = 'high';
    } else if (status === 'warning') {
      smoke = Math.random() > 0.7;
      risk = 'medium';
    }

    const newHistory: EnvironmentalHistory = {
      id: `h-sim-auto-${Date.now()}`,
      timestamp: new Date().toISOString(),
      roomId,
      cameraId,
      temperature: temp,
      humidity: hum,
      smokeDetected: smoke,
      fireDetected: fire,
      riskLevel: risk,
      imagePath: `images/snapshot_room-001_auto_${Date.now()}.jpg`,
      isSynthetic: false
    };

    this.history.unshift(newHistory);
    if (this.history.length > 200) this.history.pop();
    this.emit('historyChanged', this.history);
  }

  public getRooms(): Room[] { return this.rooms; }
  public getCameras(): Camera[] { return this.cameras; }
  public getReadings(): EnvironmentalReading[] { return this.readings; }
  public getHistory(): EnvironmentalHistory[] { return this.history; }
  public getAlerts(): Alert[] { return this.alerts; }
  public getThresholds(): Threshold { return this.thresholds; }

  public setThresholds(t: Threshold) {
    this.thresholds = t;
    this.emit('thresholds', this.thresholds);
  }

  public acknowledgeAlert(alertId: string, operator: string) {
    this.alerts = this.alerts.map(a => {
      if (a.id === alertId) {
        return {
          ...a,
          status: 'acknowledged',
          acknowledgedBy: operator,
          acknowledgedAt: new Date().toISOString()
        };
      }
      return a;
    });
    this.emit('alertsChanged', this.alerts);
  }

  public triggerManualCapture(roomId: string, temp: number, hum: number) {
    const room = this.rooms.find(r => r.id === roomId) || this.rooms[0];
    const camera = this.cameras.find(c => c.roomId === roomId && c.status === 'online') || this.cameras[0];
    if (!room) return;

    const status = checkReadingStatus(temp, hum, this.thresholds);

    // Emit live reading
    const newReading: EnvironmentalReading = {
      id: `r-manual-${Date.now()}`,
      timestamp: new Date().toISOString(),
      roomId: room.id,
      cameraId: camera.id,
      temperature: temp,
      humidity: hum,
      ocrConfidence: 99.4,
      status,
      isSynthetic: false
    };

    this.readings.unshift(newReading);
    this.emit('reading', newReading);

    // Save manual capture straight to Environmental History
    let smoke = false;
    let fire = false;
    let risk: 'low' | 'medium' | 'high' = 'low';

    if (status === 'critical') {
      smoke = Math.random() > 0.4;
      fire = Math.random() > 0.6;
      risk = 'high';
    } else if (status === 'warning') {
      smoke = Math.random() > 0.7;
      risk = 'medium';
    }

    const manualHistory: EnvironmentalHistory = {
      id: `h-sim-manual-${Date.now()}`,
      timestamp: new Date().toISOString(),
      roomId: room.id,
      cameraId: camera.id,
      temperature: temp,
      humidity: hum,
      smokeDetected: smoke,
      fireDetected: fire,
      riskLevel: risk,
      imagePath: `images/snapshot_room-001_manual_${Date.now()}.jpg`,
      isSynthetic: false
    };

    this.history.unshift(manualHistory);
    if (this.history.length > 200) this.history.pop();
    this.emit('historyChanged', this.history);

    // Process Alert triggering
    if (status !== 'normal') {
      const type = (temp >= this.thresholds.tempWarning) ? 'temperature' : 'humidity';
      const limitThreshold = type === 'temperature'
        ? (status === 'critical' ? this.thresholds.tempCritical : this.thresholds.tempWarning)
        : (status === 'critical' ? this.thresholds.humCritical : this.thresholds.humWarning);

      const hasActive = this.alerts.some(a => a.roomId === room.id && a.type === type && a.status === 'active');
      if (!hasActive) {
        const manualAlert: Alert = {
          id: `alt-manual-${Date.now()}`,
          timestamp: new Date().toISOString(),
          roomId: room.id,
          cameraId: camera.id,
          type,
          value: type === 'temperature' ? temp : hum,
          threshold: limitThreshold,
          severity: status === 'critical' ? 'critical' : 'warning',
          status: 'active',
          imageUrl: 'crop_manual.jpg'
        };
        this.alerts.unshift(manualAlert);
        this.emit('alert', { alert: manualAlert, roomName: room.name });
        this.emit('alertsChanged', this.alerts);
      }
    }
  }

  public subscribe(event: string, callback: Listener) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
  }

  public unsubscribe(event: string, callback: Listener) {
    if (!this.listeners[event]) return;
    this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
  }

  private emit(event: string, data: any) {
    if (!this.listeners[event]) return;
    this.listeners[event].forEach(cb => cb(data));
  }
}

export const mockEngine = new MockEngine();
export type { MockEngine };
