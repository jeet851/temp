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
}

export interface Alert {
  id: string;
  timestamp: string;
  roomId: string;
  cameraId: string;
  type: 'temperature' | 'humidity';
  value: number;
  threshold: number;
  severity: 'warning' | 'critical';
  status: 'active' | 'acknowledged';
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
}

export interface Threshold {
  tempWarning: number;
  tempCritical: number;
  humWarning: number;
  humCritical: number;
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
  temperature: number;
  humidity: number;
  ocrConfidence: number;
  tempDetail: OcrDigitResult;
  humDetail: OcrDigitResult;
  source: string;
  processingMs: number;
  imageSavedPath?: string;
}
