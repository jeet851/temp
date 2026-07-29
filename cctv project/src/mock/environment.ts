import type { EnvironmentalReading, EnvironmentalHistory } from '../types';

export const generateInitialReadings = (): EnvironmentalReading[] => {
  const readings: EnvironmentalReading[] = [];
  const now = new Date();

  // Generate 50 points of recent live readings at 5-second intervals for Room-001
  for (let i = 50; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 5000);
    const temp = parseFloat((21.5 + Math.sin(i / 10) * 0.8 + Math.random() * 0.4).toFixed(1));
    const hum = parseFloat((43.0 + Math.cos(i / 10) * 1.5 + Math.random() * 0.8).toFixed(1));

    readings.push({
      id: `r-sim-init-${50 - i}`,
      timestamp: time.toISOString(),
      roomId: 'room-001',
      cameraId: 'camera-001',
      temperature: temp,
      humidity: hum,
      ocrConfidence: parseFloat((96.0 + Math.random() * 3.5).toFixed(1)),
      status: 'normal',
      isSynthetic: false
    });
  }
  return readings;
};

export const generateInitialHistory = (): EnvironmentalHistory[] => {
  const history: EnvironmentalHistory[] = [];
  const now = new Date();

  // Generate 24 hourly records representing the past 24 hours
  for (let i = 24; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60 * 60 * 1000);
    const hour = time.getHours();
    
    // Add cyclical daily wave
    const cycle = Math.sin((hour - 6) * (Math.PI / 12));
    const temp = parseFloat((22.0 + cycle * 2.0 + Math.random() * 0.8).toFixed(1));
    const hum = parseFloat((44.0 + cycle * 5.0 + Math.random() * 2.0).toFixed(1));

    let smoke = false;
    let fire = false;
    let risk: 'low' | 'medium' | 'high' = 'low';

    // Simulate anomaly states when temp/humidity is elevated
    if (temp >= 32.0 || hum >= 75.0) {
      smoke = Math.random() > 0.4;
      fire = Math.random() > 0.6;
      risk = 'high';
    } else if (temp >= 28.0 || hum >= 65.0) {
      smoke = Math.random() > 0.7;
      risk = 'medium';
    }

    history.push({
      id: `h-sim-${24 - i}`,
      timestamp: time.toISOString(),
      roomId: 'room-001',
      cameraId: 'camera-001',
      temperature: temp,
      humidity: hum,
      smokeDetected: smoke,
      fireDetected: fire,
      riskLevel: risk,
      imagePath: `images/snapshot_room-001_hour_${24 - i}.jpg`,
      isSynthetic: false
    });
  }

  return history.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
};
