import type { Threshold } from '../types';

export const calculateDrift = (base: number, range: number): number => {
  return parseFloat((base + (Math.random() - 0.5) * range).toFixed(1));
};

export const checkReadingStatus = (
  temp: number, 
  hum: number, 
  thresholds: Threshold
): 'normal' | 'warning' | 'critical' => {
  if (temp >= thresholds.tempCritical || hum >= thresholds.humCritical) {
    return 'critical';
  }
  if (temp >= thresholds.tempWarning || hum >= thresholds.humWarning) {
    return 'warning';
  }
  return 'normal';
};
