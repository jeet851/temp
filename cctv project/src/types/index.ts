export interface Room {
  id: string;
  name: string;
  location: string;
  status: 'normal' | 'warning' | 'critical';
}

export interface Camera {
  id: string;
  name: string;
  roomId: string;
  rtspUrl: string;
  status: 'online' | 'offline';
  fps: number;
  latencyMs: number;
  ocrConfidence: number;
  lastSeenAt: string | null;
}

export interface EnvironmentalReading {
  id: string;
  timestamp: string;
  roomId: string;
  cameraId: string;
  temperature: number;
  humidity: number;
  ocrConfidence: number;
  status: 'normal' | 'warning' | 'critical';
  isSynthetic: boolean;   // true = random fallback, false = real OCR read
  ocrSource?: string;     // 'rtsp' | 'upload' | 'synthetic' | 'test'
  lowConfidence?: boolean;
}

export interface Alert {
  id: string;
  timestamp: string;
  roomId: string;
  cameraId: string;
  type: 'temperature' | 'humidity' | 'camera_offline';
  value: number;
  threshold: number;
  severity: 'warning' | 'critical';
  status: 'active' | 'acknowledged' | 'resolved';
  imageUrl: string;
  acknowledgedBy?: string;
  acknowledgedAt?: string;
}

export interface EnvironmentalHistory {
  id: string;
  timestamp: string;
  roomId: string;
  cameraId: string;
  temperature: number;
  humidity: number;
  smokeDetected: boolean;
  fireDetected: boolean;
  riskLevel: 'low' | 'medium' | 'high';
  imagePath: string;
  isSynthetic: boolean;   // true = synthetic fallback, false = real OCR
  ocrSource?: string;     // 'rtsp' | 'upload' | 'synthetic' | 'test'
  lowConfidence?: boolean;
}

export interface Threshold {
  tempWarning: number;
  tempCritical: number;
  humWarning: number;
  humCritical: number;
  ocrPollingIntervalSeconds: number;
  allowSyntheticFallback: boolean;
  deviceTimeOffsetMinutes?: number;
}

export interface Notification {
  id: string;
  timestamp: string;
  title: string;
  message: string;
  read: boolean;
  type: 'info' | 'warning' | 'critical';
}

export interface ReportSummary {
  avgTemp: number;
  maxTemp: number;
  minTemp: number;
  avgHum: number;
  maxHum: number;
  minHum: number;
  totalCaptures: number;
  alertSummary: {
    total: number;
    warnings: number;
    criticals: number;
  };
}

export interface LayoutContextType {
  selectedRoom: Room;
  setSelectedRoom: (room: Room) => void;
  rooms: Room[];
  cameras: Camera[];
  thresholds: Threshold;
  setThresholds: (t: Threshold) => void;
}

export interface OcrDigitResult {
  rawText: string;
  value: number;
  confidence: number;
  roi: number[];
}

export interface OcrResult {
  temperature: number | null;
  humidity: number | null;
  ocrConfidence: number;
  tempDetail: OcrDigitResult | null;
  humDetail: OcrDigitResult | null;
  source: string;
  processingMs: number;
  imageSavedPath?: string;
  deviceType?: string;
  ocrStatus?: string;
  lcdRegion?: number[];
  lcdDetectConfidence?: 'high' | 'low';
  tempRoiImagePath?: string;
  humRoiImagePath?: string;
}
