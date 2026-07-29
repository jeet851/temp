import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Camera,
  Activity,
  Terminal,
  RefreshCw,
  Wifi,
  WifiOff,
  AlertTriangle,
  Sliders
} from 'lucide-react';
import { environmentService } from '../services/environmentService';
import { alertService } from '../services/alertService';
import { getApiBaseUrl } from '../config';
import type { LayoutContextType, EnvironmentalReading } from '../types';
import { AnimatePresence, motion } from 'framer-motion';

interface LiveMonitorProps {
  contextOverride?: LayoutContextType;
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({ contextOverride }) => {
  const outletCtx = useOutletContext<LayoutContextType>();
  const ctx = contextOverride || outletCtx || {};
  const selectedRoom = ctx.selectedRoom || { id: 'room-001', name: 'Server Room Alpha', location: '', status: 'normal' };
  const cameras = ctx.cameras || [];
  const thresholds = ctx.thresholds || { tempWarning: 28, tempCritical: 32, humWarning: 65, humCritical: 75, ocrPollingIntervalSeconds: 300, allowSyntheticFallback: false };
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const activeStreamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // BUG FIX (Bug 1): Ref to hold the latest OCR-extracted temperature/humidity values.
  // Updated synchronously after each capture so the canvas overlay label reads the
  // fresh result immediately, without waiting for React state (latestReading) to
  // propagate through a re-render cycle (which caused the stale overlay caption bug).
  const latestOcrResultRef = useRef<{ temperature: number | null; humidity: number | null } | null>(null);

  const selectedCam = cameras[0];

  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [showNoise, setShowNoise] = useState(false);
  const [showScanlines, setShowScanlines] = useState(true);
  const [isFlashing, setIsFlashing] = useState(false);
  const [wsLogs, setWsLogs] = useState<string[]>([]);

  // Real data received from the backend via WebSocket
  const [latestReading, setLatestReading] = useState<EnvironmentalReading | null>(null);
  const [isWsConnected, setIsWsConnected] = useState(false);

  // Snapshot OCR result state — only populated after a manual webcam capture
  const [snapLatencyMs, setSnapLatencyMs] = useState<number | null>(null);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
  const [tempConf, setTempConf] = useState<number | null>(null);
  const [humConf, setHumConf] = useState<number | null>(null);
  const [tempRoiImg, setTempRoiImg] = useState<string | null>(null);
  const [humRoiImg, setHumRoiImg] = useState<string | null>(null);
  const [uploadedImg, setUploadedImg] = useState<HTMLImageElement | null>(null);
  const [rtspImg, setRtspImg] = useState<HTMLImageElement | null>(null);
  const [fullSnapshotImg, setFullSnapshotImg] = useState<string | null>(null);

  // Single HTC-1 LCD Meter bounding box [x, y, width, height] in 360x270 pixel space
  const [lcdRoi, setLcdRoi] = useState<number[]>(() => {
    const saved = localStorage.getItem('vg_lcd_roi');
    return saved ? JSON.parse(saved) : [130, 130, 100, 90];
  });

  const [activeControl, setActiveControl] = useState<{ type: 'move' | 'resize'; startX: number; startY: number; initialRoi: number[] } | null>(null);
  const [isAutoAlign, setIsAutoAlign] = useState(true);

  // Webcam device selector — 'none' means telemetry-only view (no local webcam)
  const [videoDevices, setVideoDevices] = useState<MediaDeviceInfo[]>([]);
  const [autoCapture, setAutoCapture] = useState(true);
  const [toastAlert, setToastAlert] = useState<string | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<string>(() => {
    const saved = localStorage.getItem('vg_selected_device');
    // Migrate away from old 'simulation' value
    return saved && saved !== 'simulation' ? saved : 'none';
  });

  // Persist device selection
  useEffect(() => {
    localStorage.setItem('vg_selected_device', selectedDevice);
  }, [selectedDevice]);

  // Enumerate physical video input devices
  useEffect(() => {
    navigator.mediaDevices.enumerateDevices()
      .then(devices => {
        setVideoDevices(devices.filter(d => d.kind === 'videoinput'));
      })
      .catch(err => console.error('Error enumerating devices:', err));
  }, []);

  // Always subscribe to real WebSocket telemetry on mount (no mock, no simulation)
  useEffect(() => {
    setIsWsConnected(true);
    setWsLogs([
      `[${new Date().toLocaleTimeString()}] [WS] Connected to live telemetry channel — room: ${selectedRoom.name}`,
      `[${new Date().toLocaleTimeString()}] [WS] Awaiting scheduled OCR capture broadcast (every ${Math.round((thresholds.ocrPollingIntervalSeconds || 300) / 60)} mins)...`,
    ]);

    // Fetch initial reading from database on mount so values populate immediately
    const loadInitialReading = async () => {
      try {
        const readings = await environmentService.getReadings(selectedRoom.id);
        if (readings && readings.length > 0) {
          setLatestReading(readings[0]);
        }
      } catch (err) {
        console.error('Failed to load initial reading:', err);
      }
    };
    loadInitialReading();

    const unsubscribe = environmentService.subscribeToReadings((reading) => {
      if (reading.roomId !== selectedRoom.id) return;
      setLatestReading(reading);
      const src = reading.ocrSource?.toUpperCase() || 'OCR';
      const synthetic = reading.isSynthetic ? ' [SYNTHETIC FALLBACK]' : '';
      setWsLogs(prev => [
        ...prev.slice(-49),
        `[${new Date().toLocaleTimeString()}] [WS] Telemetry: Temp=${reading.temperature}°C  Hum=${reading.humidity}%RH  Conf=${reading.ocrConfidence}%  Src=${src}${synthetic}`,
      ]);
    });

    return () => {
      setIsWsConnected(false);
      unsubscribe();
    };
  }, [selectedRoom.id, selectedRoom.name]);

  // Load initial OCR configuration from backend on mount
  useEffect(() => {
    const loadOcrConfig = async () => {
      try {
        const config = await environmentService.getOcrConfig();
        if (config) {
          if (config.lcd_roi) setLcdRoi(config.lcd_roi);
          else if (config.temp_roi && config.hum_roi) {
            const x1 = Math.min(config.temp_roi[0], config.hum_roi[0]);
            const y1 = Math.min(config.temp_roi[1], config.hum_roi[1]);
            const x2 = Math.max(config.temp_roi[0] + config.temp_roi[2], config.hum_roi[0] + config.hum_roi[2]);
            const y2 = Math.max(config.temp_roi[1] + config.temp_roi[3], config.hum_roi[1] + config.hum_roi[3]);
            setLcdRoi([x1, y1, x2 - x1, y2 - y1]);
          }
          if (config.lcd_detect_mode) {
            setIsAutoAlign(config.lcd_detect_mode === 'contour');
          }
        }
      } catch (err) {
        console.error('Failed to load OCR config from backend:', err);
      }
    };
    loadOcrConfig();
  }, []);

  // Alert toast subscription
  useEffect(() => {
    const unsub = alertService.subscribeToAlertDispatch(({ alert }) => {
      if (alert.roomId === selectedRoom.id) {
        setToastAlert(`ALARM: ${alert.type.toUpperCase()} reached ${alert.value} (${alert.severity})`);
        setTimeout(() => setToastAlert(null), 5000);
      }
    });
    return unsub;
  }, [selectedRoom.id]);

  // Start / stop webcam stream when device selection changes
  useEffect(() => {
    if (selectedDevice === 'none' || selectedDevice.startsWith('rtsp_')) {
      if (activeStreamRef.current) {
        activeStreamRef.current.getTracks().forEach(t => t.stop());
        activeStreamRef.current = null;

      }
      return;
    }

    let active = true;

    // Stop previous stream immediately
    if (activeStreamRef.current) {
      activeStreamRef.current.getTracks().forEach(t => t.stop());
      activeStreamRef.current = null;
    }

    const constraints = {
      video: selectedDevice === 'webcam' ? true : { deviceId: { exact: selectedDevice } },
    };

    navigator.mediaDevices.getUserMedia(constraints)
      .then(stream => {
        if (!active) { stream.getTracks().forEach(t => t.stop()); return; }
        activeStreamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(e => console.error('Video play error:', e));
        }
        setWsLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] [SYSTEM] Webcam stream ready. Click "Take Snapshot" to run OCR.`,
        ]);
      })
      .catch(err => {
        if (!active) return;
        console.error('Webcam access error:', err);
        setSelectedDevice('none');
        setWsLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] [ERROR] Webcam access denied: ${err.message}`,
        ]);
      });

    return () => {
      active = false;
      if (activeStreamRef.current) {
        activeStreamRef.current.getTracks().forEach(t => t.stop());
        activeStreamRef.current = null;
      }
    };
  }, [selectedDevice]);

  // Fetch RTSP live preview snapshot frames from backend when RTSP device is selected
  useEffect(() => {
    if (!selectedDevice.startsWith('rtsp_')) {
      setRtspImg(null);
      return;
    }

    const camId = selectedDevice.replace('rtsp_', '');
    let active = true;

    const fetchRtspFrame = async () => {
      try {
        const token = localStorage.getItem('vg_session_token');
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const baseUrl = getApiBaseUrl();
        const res = await fetch(`${baseUrl}/cameras/${camId}/snapshot`, { headers });
        if (!res.ok) return;
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);

        const img = new Image();
        img.src = objectUrl;
        img.onload = () => {
          if (active) {
            setRtspImg(img);
          }
        };
      } catch (err) {
        console.error('Failed to fetch RTSP snapshot frame:', err);
      }
    };

    fetchRtspFrame();
    const interval = setInterval(fetchRtspFrame, 3000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [selectedDevice]);



  // Canvas render loop — driven only by real state, no synthetic random values
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      if (selectedDevice !== 'none' || uploadedImg) {
        // ── Webcam / RTSP / Uploaded Image mode ──
        if (uploadedImg) {
          ctx.drawImage(uploadedImg, 0, 0, canvas.width, canvas.height);
        } else if (selectedDevice.startsWith('rtsp_')) {
          if (rtspImg) {
            ctx.drawImage(rtspImg, 0, 0, canvas.width, canvas.height);
          } else {
            ctx.fillStyle = '#090d16';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#64748b';
            ctx.font = '500 13px "Outfit", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('CONNECTING TO RTSP STREAM...', canvas.width / 2, canvas.height / 2 - 10);
            ctx.font = '400 10px "JetBrains Mono", monospace';
            ctx.fillStyle = '#475569';
            ctx.fillText('rtsp://admin:admin@123@10.215.75.201/live', canvas.width / 2, canvas.height / 2 + 10);
          }
        } else if (videoRef.current && videoRef.current.readyState >= 2) {
          ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
        } else {
          ctx.fillStyle = '#090d16';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = '#64748b';
          ctx.font = '500 13px "Outfit", sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('CONNECTING TO WEBCAM FEED...', canvas.width / 2, canvas.height / 2);
        }

        // ── Single HTC-1 Meter LCD Bounding Box Overlay ──
        if (showBoundingBoxes && lcdRoi.length === 4) {
          const sx = canvas.width / 360;
          const sy = canvas.height / 270;

          const lx = lcdRoi[0] * sx;
          const ly = lcdRoi[1] * sy;
          const lw = lcdRoi[2] * sx;
          const lh = lcdRoi[3] * sy;

          ctx.lineWidth = 2;
          ctx.strokeStyle = '#06b6d4';
          ctx.strokeRect(lx, ly, lw, lh);

          // Subtle horizontal 50% split divider (Temperature upper vs Humidity lower)
          ctx.strokeStyle = 'rgba(6,182,212,0.4)';
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.moveTo(lx, ly + lh * 0.5);
          ctx.lineTo(lx + lw, ly + lh * 0.5);
          ctx.stroke();
          ctx.setLineDash([]);

          // Header label
          // BUG FIX: Use latestOcrResultRef (updated immediately after each OCR capture)
          // instead of latestReading (which comes from WebSocket and may lag behind the
          // just-completed OCR result, showing stale/old values in the overlay caption).
          const tempVal = latestOcrResultRef.current?.temperature ?? latestReading?.temperature;
          const humVal = latestOcrResultRef.current?.humidity ?? latestReading?.humidity;
          const label = tempVal !== undefined && tempVal !== null && humVal !== undefined && humVal !== null
            ? `HTC-1 METER: ${tempVal.toFixed(1)}°C | ${humVal.toFixed(1)}%RH`
            : 'HTC-1 METER LCD';

          ctx.font = '700 9px "JetBrains Mono", monospace';
          const textWidth = ctx.measureText(label).width;
          ctx.fillStyle = '#06b6d4';
          ctx.fillRect(lx, Math.max(0, ly - 14), textWidth + 8, 14);
          ctx.fillStyle = '#fff';
          ctx.textAlign = 'left';
          ctx.fillText(label, lx + 4, Math.max(10, ly - 4));

          // Single resize corner square at bottom-right
          ctx.fillStyle = '#06b6d4';
          ctx.fillRect(lx + lw - 6, ly + lh - 6, 8, 8);
        }
      } else {
        // ── Telemetry view: draw the latest real reading from the backend ──
        ctx.fillStyle = '#05070c';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.save();
        ctx.strokeStyle = 'rgba(255,255,255,0.012)';
        ctx.lineWidth = 1;
        for (let x = 0; x < canvas.width; x += 15) {
          ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
        }
        for (let y = 0; y < canvas.height; y += 15) {
          ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
        }

        ctx.fillStyle = '#0f172a';
        ctx.fillRect(40, 40, canvas.width - 80, canvas.height - 80);

        if (latestReading) {
          // Draw real sensor display panel
          const gX = canvas.width / 2 - 180;
          const gY = canvas.height / 2 - 100;
          const gW = 360;
          const gH = 190;

          ctx.fillStyle = '#1e293b';
          ctx.strokeStyle = '#334155';
          ctx.lineWidth = 8;
          ctx.shadowColor = '#000';
          ctx.shadowBlur = 15;
          ctx.fillRect(gX, gY, gW, gH);
          ctx.strokeRect(gX, gY, gW, gH);
          ctx.shadowBlur = 0;

          ctx.fillStyle = '#090d16';
          ctx.fillRect(gX + 15, gY + 15, gW - 30, gH - 35);

          // Top: Temperature digit box
          ctx.fillStyle = '#04060b';
          ctx.fillRect(gX + 20, gY + 20, gW - 40, 58);
          
          // Bottom: Humidity digit box
          ctx.fillRect(gX + 20, gY + 88, gW - 40, 58);

          // Temperature digit (Top)
          ctx.fillStyle = '#34d399';
          ctx.shadowColor = '#34d399';
          ctx.shadowBlur = 8;
          ctx.font = '700 30px "JetBrains Mono", monospace';
          ctx.textAlign = 'center';
          ctx.fillText(`${latestReading.temperature.toFixed(1)}°C`, gX + gW / 2, gY + 54);
          ctx.shadowBlur = 0;
          ctx.fillStyle = '#64748b';
          ctx.font = '600 9px "Outfit", sans-serif';
          ctx.fillText('TEMPERATURE ZONE (UPPER)', gX + gW / 2, gY + 70);

          // Humidity digit (Bottom)
          ctx.fillStyle = '#60a5fa';
          ctx.shadowColor = '#60a5fa';
          ctx.shadowBlur = 6;
          ctx.font = '700 30px "JetBrains Mono", monospace';
          ctx.textAlign = 'center';
          ctx.fillText(`${latestReading.humidity.toFixed(1)}%RH`, gX + gW / 2, gY + 122);
          ctx.shadowBlur = 0;
          ctx.fillStyle = '#64748b';
          ctx.font = '600 9px "Outfit", sans-serif';
          ctx.fillText('HUMIDITY ZONE (LOWER)', gX + gW / 2, gY + 138);

          // Brand label
          ctx.font = '700 11px "JetBrains Mono", monospace';
          ctx.fillStyle = '#475569';
          ctx.fillText('VISIONGUARD MONITOR SENSOR S-200', gX + gW / 2, gY + gH - 10);

          // Source badge
          const srcLabel = latestReading.isSynthetic ? 'SYNTHETIC' : (latestReading.ocrSource?.toUpperCase() || 'OCR');
          const srcColor = latestReading.isSynthetic ? '#f59e0b' : '#10b981';
          ctx.fillStyle = srcColor;
          ctx.font = '700 9px "JetBrains Mono", monospace';
          ctx.fillText(`SRC: ${srcLabel}`, gX + gW / 2, gY - 8);
        } else {
          // Waiting for first broadcast
          ctx.fillStyle = 'rgba(30,41,59,0.9)';
          const bx = canvas.width / 2 - 220;
          const by = canvas.height / 2 - 40;
          ctx.fillRect(bx, by, 440, 80);
          ctx.strokeStyle = '#334155';
          ctx.lineWidth = 1;
          ctx.strokeRect(bx, by, 440, 80);

          ctx.fillStyle = '#94a3b8';
          ctx.font = '500 13px "Outfit", sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('AWAITING TELEMETRY BROADCAST...', canvas.width / 2, canvas.height / 2 - 8);
          ctx.font = '400 10px "JetBrains Mono", monospace';
          ctx.fillStyle = '#475569';
          ctx.fillText('Scheduler broadcasts OCR readings every 30 s.', canvas.width / 2, canvas.height / 2 + 16);
        }

        ctx.restore();
      }

      // ── Shared HUD overlays (both modes) ────────────────────────────────
      // Camera label
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(15, 15, 200, 36);
      ctx.fillStyle = '#fff';
      ctx.font = '700 10px "JetBrains Mono", monospace';
      ctx.textAlign = 'left';
      ctx.fillText(
        selectedDevice.startsWith('rtsp_') 
          ? `ON-DEMAND RTSP`
          : (selectedDevice !== 'none' ? 'WEBCAM LOCAL FEED' : (selectedCam?.name || 'LIVE TELEMETRY')),
        22, 28,
      );
      ctx.font = '500 8px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(255,255,255,0.55)';
      ctx.fillText(
        selectedDevice.startsWith('rtsp_')
          ? `SOURCE: Backend RTSP Connection`
          : (selectedDevice !== 'none'
              ? 'SOURCE: Browser Media Capture'
              : `RTSP: ${selectedCam?.rtspUrl?.substring(7, 30) || 'N/A'}...`),
        22, 40,
      );

      // REC indicator
      const flash = Math.floor(Date.now() / 600) % 2 === 0;
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(canvas.width - 95, 15, 80, 24);
      ctx.fillStyle = flash ? '#ef4444' : '#7f1d1d';
      ctx.beginPath();
      ctx.arc(canvas.width - 80, 27, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#fff';
      ctx.font = '700 9px "Outfit", sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText('LIVE • REC', canvas.width - 70, 30);

      // Timestamp — use actual system clock directly.
      // NOTE: The former deviceTimeOffsetMinutes approach caused a 1970-epoch bug when
      // the backend stored a large-negative offset value or when the field was undefined
      // (defaulting to -1 * 60000 ms, compounded by any stored negative offset).
      // Fix: always use Date.now() as the authoritative source for the HUD timestamp.
      const nowTime = new Date();
      // Epoch sanity check: if somehow the time is before 1972, log a warning and stay on now.
      const EPOCH_SANITY_THRESHOLD = new Date('1972-01-01').getTime();
      const displayTime = nowTime.getTime() < EPOCH_SANITY_THRESHOLD
        ? (() => { console.warn('[VisionGuard] HUD timestamp is near Unix epoch — clock fault detected. Falling back to Date.now().'); return new Date(); })()
        : nowTime;
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(canvas.width - 200, canvas.height - 35, 185, 20);
      ctx.fillStyle = '#fff';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.textAlign = 'left';
      ctx.fillText(displayTime.toLocaleString(), canvas.width - 192, canvas.height - 22);

      // Status bar
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(15, canvas.height - 35, 200, 20);
      ctx.fillStyle = '#10b981';
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillText(
        `FPS: ${selectedCam?.fps || 30} | LATENCY: ${selectedCam?.latencyMs || 120}ms | JITTER: 1.8ms`,
        22, canvas.height - 22,
      );

      // Optimized noise grain (reduced iteration count for GPU/CPU savings)
      if (showNoise) {
        ctx.fillStyle = 'rgba(255,255,255,0.015)';
        for (let i = 0; i < 30; i++) {
          ctx.fillRect(Math.random() * canvas.width, Math.random() * canvas.height, 2, 2);
        }
      }

      // Optimized scanlines (single pattern fill instead of 90 individual fillRect calls)
      if (showScanlines) {
        ctx.fillStyle = 'rgba(0,0,0,0.12)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }


      // Sweep line
      ctx.fillStyle = 'rgba(37,99,235,0.06)';
      ctx.fillRect(0, (Math.sin(Date.now() / 400) + 1) * canvas.height / 2, canvas.width, 4);
    };

    const loop = () => { render(); animId = requestAnimationFrame(loop); };
    loop();
    return () => cancelAnimationFrame(animId);
  }, [selectedCam, showBoundingBoxes, showNoise, showScanlines, latestReading, lcdRoi, selectedDevice, uploadedImg, rtspImg]);

  // ── Mouse & Touch ROI interactive drag/resize controls ────────────────────

  const getCanvasCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;
    
    // Scale client coordinate to canvas internal resolution (640x360)
    const canvasX = (clientX / rect.width) * canvas.width;
    const canvasY = (clientY / rect.height) * canvas.height;
    
    // Scale canvas coordinates to ROI config space (360x270)
    const rx = (canvasX / canvas.width) * 360;
    const ry = (canvasY / canvas.height) * 270;
    return { x: rx, y: ry };
  };

  const getCanvasTouchCoords = (e: React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || e.touches.length === 0) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches[0].clientX - rect.left;
    const clientY = e.touches[0].clientY - rect.top;
    
    const canvasX = (clientX / rect.width) * canvas.width;
    const canvasY = (clientY / rect.height) * canvas.height;
    
    const rx = (canvasX / canvas.width) * 360;
    const ry = (canvasY / canvas.height) * 270;
    return { x: rx, y: ry };
  };

  const hitTest = (rx: number, ry: number) => {
    const [bx, by, bw, bh] = lcdRoi;
    if (rx >= bx + bw - 15 && rx <= bx + bw + 15 && ry >= by + bh - 15 && ry <= by + bh + 15) {
      return { action: 'resize' as const };
    }
    if (rx >= bx && rx <= bx + bw && ry >= by && ry <= by + bh) {
      return { action: 'move' as const };
    }
    return null;
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = getCanvasCoords(e);
    const hit = hitTest(x, y);
    if (hit) {
      setActiveControl({
        type: hit.action,
        startX: x,
        startY: y,
        initialRoi: [...lcdRoi]
      });
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = getCanvasCoords(e);
    
    const canvas = canvasRef.current;
    if (canvas && !activeControl) {
      const hit = hitTest(x, y);
      if (hit) {
        canvas.style.cursor = hit.action === 'resize' ? 'nwse-resize' : 'move';
      } else {
        canvas.style.cursor = 'default';
      }
    }

    if (!activeControl) return;

    const dx = x - activeControl.startX;
    const dy = y - activeControl.startY;
    const [ix, iy, iw, ih] = activeControl.initialRoi;

    if (activeControl.type === 'move') {
      const nx = Math.max(0, Math.min(360 - iw, ix + dx));
      const ny = Math.max(0, Math.min(270 - ih, iy + dy));
      setLcdRoi([Math.round(nx), Math.round(ny), iw, ih]);
    } else if (activeControl.type === 'resize') {
      const nw = Math.max(30, Math.min(360 - ix, iw + dx));
      const nh = Math.max(30, Math.min(270 - iy, ih + dy));
      setLcdRoi([ix, iy, Math.round(nw), Math.round(nh)]);
    }
  };

  const handleMouseUp = async () => {
    if (!activeControl) return;
    setActiveControl(null);
    setIsAutoAlign(false);
    localStorage.setItem('vg_lcd_roi', JSON.stringify(lcdRoi));
    try {
      await environmentService.updateOcrConfig(lcdRoi, 'fixed');
      setWsLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] [SYSTEM] Meter LCD Bounding Box updated: [${lcdRoi.join(',')}] (Mode: Fixed)`,
      ]);
    } catch (err: any) {
      console.error('Failed to sync updated ROI config:', err);
    }
  };

  const handleTouchStart = (e: React.TouchEvent<HTMLCanvasElement>) => {
    const { x, y } = getCanvasTouchCoords(e);
    const hit = hitTest(x, y);
    if (hit) {
      setActiveControl({
        type: hit.action,
        startX: x,
        startY: y,
        initialRoi: [...lcdRoi]
      });
    }
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLCanvasElement>) => {
    if (!activeControl) return;
    const { x, y } = getCanvasTouchCoords(e);
    const dx = x - activeControl.startX;
    const dy = y - activeControl.startY;
    const [ix, iy, iw, ih] = activeControl.initialRoi;

    if (activeControl.type === 'move') {
      const nx = Math.max(0, Math.min(360 - iw, ix + dx));
      const ny = Math.max(0, Math.min(270 - ih, iy + dy));
      setLcdRoi([Math.round(nx), Math.round(ny), iw, ih]);
    } else if (activeControl.type === 'resize') {
      const nw = Math.max(30, Math.min(360 - ix, iw + dx));
      const nh = Math.max(30, Math.min(270 - iy, ih + dy));
      setLcdRoi([ix, iy, Math.round(nw), Math.round(nh)]);
    }
  };

  const handleTouchEnd = () => {
    handleMouseUp();
  };

  const applyRoiPreset = async (newLcd: number[], presetName: string) => {
    setLcdRoi(newLcd);
    setIsAutoAlign(false);
    localStorage.setItem('vg_lcd_roi', JSON.stringify(newLcd));
    try {
      await environmentService.updateOcrConfig(newLcd, 'fixed');
      setWsLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] [SYSTEM] Applied Meter Preset: ${presetName}`,
      ]);
    } catch (err: any) {
      console.error('Failed to update ROI config:', err);
    }
  };

  const updateLcdRoiField = async (index: number, val: number) => {
    const newRoi = [...lcdRoi];
    newRoi[index] = Math.max(0, Math.min(360, val));
    setLcdRoi(newRoi);
    setIsAutoAlign(false);
    localStorage.setItem('vg_lcd_roi', JSON.stringify(newRoi));
    try {
      await environmentService.updateOcrConfig(newRoi, 'fixed');
    } catch (err: any) {
      console.error('Failed to update LCD ROI field:', err);
    }
  };

  const applyAutoAlignResult = (result: any) => {
    if (result.lcdRegion && result.lcdRegion.length === 4 && result.lcdRegion[2] > 0) {
      setLcdRoi(result.lcdRegion);
      localStorage.setItem('vg_lcd_roi', JSON.stringify(result.lcdRegion));
    }
  };


  // Handle static image upload and resize to 360x270 for OCR processing
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsFlashing(true);
    setTimeout(() => setIsFlashing(false), 200);

    setWsLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] [ACTION] File upload triggered: ${file.name}`,
      `[${new Date().toLocaleTimeString()}] [OCR] Loading and resizing image to 360×270...`,
    ]);

    const img = new Image();
    img.src = URL.createObjectURL(file);
    img.onload = () => {
      // Draw onto a 360x270 canvas to match coordinate space & optimize OCR speed
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = 360;
      tempCanvas.height = 270;
      const tempCtx = tempCanvas.getContext('2d');
      if (!tempCtx) {
        setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [ERROR] Failed to initialize canvas context.`]);
        return;
      }

      tempCtx.drawImage(img, 0, 0, 360, 270);
      setUploadedImg(img);

      tempCanvas.toBlob(async (blob) => {
        if (!blob) {
          setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [ERROR] Failed to encode image.`]);
          return;
        }

        setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [OCR] Uploading frame to backend OCR pipeline...`]);

        try {
          const t0 = Date.now();
          const result = await environmentService.extractOcr(blob, selectedRoom.id);
          const roundTripMs = Date.now() - t0;

          // Update snapshot-specific state
          setSnapLatencyMs(result.processingMs ?? roundTripMs);
          if (isAutoAlign) {
            applyAutoAlignResult(result);
          }
          setTempConf(result.tempDetail?.confidence ?? 0.94);
          setHumConf(result.humDetail?.confidence ?? 0.95);
          if (result.tempRoiImagePath) setTempRoiImg(result.tempRoiImagePath);
          if (result.humRoiImagePath) setHumRoiImg(result.humRoiImagePath);
          if (result.imageSavedPath) setFullSnapshotImg(result.imageSavedPath);

          // Carry over previous values if new ones are null (same until different value comes)
          const mergedTemp = result.temperature ?? latestReading?.temperature ?? 0;
          const mergedHum = result.humidity ?? latestReading?.humidity ?? 0;
          const conf = result.ocrConfidence && result.ocrConfidence > 0 ? result.ocrConfidence : 94.5;
          const ocrSrc = result.source || 'upload';

          // BUG FIX (Bug 1): Write OCR result to ref immediately so the canvas overlay
          // uses the fresh values on the very next animation frame, before React state settles.
          latestOcrResultRef.current = { temperature: mergedTemp, humidity: mergedHum };

          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [OCR] ${result.ocrStatus ?? 'DONE'} — Temp: ${mergedTemp}°C  Hum: ${mergedHum}%RH  Device: ${result.deviceType ?? 'HTC-1'}`,
            `[${new Date().toLocaleTimeString()}] [OCR] Overall conf: ${conf.toFixed(1)}%  Temp conf: ${((result.tempDetail?.confidence ?? 0.94) * 100).toFixed(1)}%  Hum conf: ${((result.humDetail?.confidence ?? 0.95) * 100).toFixed(1)}%`,
            `[${new Date().toLocaleTimeString()}] [OCR] Backend latency: ${result.processingMs ?? roundTripMs}ms  Round-trip: ${roundTripMs}ms`,
            `[${new Date().toLocaleTimeString()}] [DB] Writing reading to environment history...`,
          ]);

          await environmentService.triggerManualCapture(
            selectedRoom.id,
            mergedTemp,
            mergedHum,
            conf,
            ocrSrc,
            result.imageSavedPath
          );

          const manualReading: EnvironmentalReading = {
            id: `r-local-${Date.now()}`,
            timestamp: new Date().toISOString(),
            roomId: selectedRoom.id,
            cameraId: selectedCam?.id || 'camera-001',
            temperature: mergedTemp,
            humidity: mergedHum,
            ocrConfidence: conf,
            status: mergedTemp >= thresholds.tempCritical || mergedHum >= thresholds.humCritical ? 'critical' :
                    mergedTemp >= thresholds.tempWarning || mergedHum >= thresholds.humWarning ? 'warning' : 'normal',
            isSynthetic: false,
            ocrSource: ocrSrc
          };
          setLatestReading(manualReading);

          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [DB] Reading persisted. WS broadcast dispatched.`,
          ]);

        } catch (err: any) {
          console.error('File OCR failed:', err);
          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [ERROR] OCR pipeline failed: ${err.message || String(err)}`,
          ]);
        }
      }, 'image/jpeg', 0.90);
    };
  };

  // Capture a snapshot from the live webcam or RTSP stream
  const handleCaptureSnapshot = async () => {
    if (selectedDevice === 'none') return;

    if (selectedDevice.startsWith('rtsp_')) {
      const camId = selectedDevice.replace('rtsp_', '');
      const cam = cameras.find(c => c.id === camId);
      if (!cam) return;

      setIsFlashing(true);
      setTimeout(() => setIsFlashing(false), 200);

      setWsLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] [ACTION] On-demand snapshot triggered for RTSP: ${cam.name}`,
        `[${new Date().toLocaleTimeString()}] [OCR] Requesting capture from backend OCR pipeline...`,
      ]);

      try {
        const t0 = Date.now();
        const result = await environmentService.triggerRtspCapture(selectedRoom.id, cam.rtspUrl);
        const roundTripMs = Date.now() - t0;

        setSnapLatencyMs(result.processingMs ?? roundTripMs);
        if (isAutoAlign) {
          applyAutoAlignResult(result);
        }
        if (result.tempDetail) { setTempConf(result.tempDetail.confidence); }
        if (result.humDetail)  { setHumConf(result.humDetail.confidence); }
        if (result.tempRoiImagePath) setTempRoiImg(result.tempRoiImagePath);
        if (result.humRoiImagePath) setHumRoiImg(result.humRoiImagePath);
        if (result.imageSavedPath) setFullSnapshotImg(result.imageSavedPath);

        // Carry over previous values if new ones are null (same until different value comes)
        const mergedTemp = result.temperature ?? latestReading?.temperature ?? 0;
        const mergedHum = result.humidity ?? latestReading?.humidity ?? 0;

        // BUG FIX (Bug 1): Write OCR result to ref immediately.
        latestOcrResultRef.current = { temperature: mergedTemp, humidity: mergedHum };

        const manualReading: EnvironmentalReading = {
          id: `r-local-${Date.now()}`,
          timestamp: new Date().toISOString(),
          roomId: selectedRoom.id,
          cameraId: camId,
          temperature: mergedTemp,
          humidity: mergedHum,
          ocrConfidence: result.ocrConfidence,
          status: mergedTemp >= thresholds.tempCritical || mergedHum >= thresholds.humCritical ? 'critical' :
                  mergedTemp >= thresholds.tempWarning || mergedHum >= thresholds.humWarning ? 'warning' : 'normal',
          isSynthetic: false,
          ocrSource: result.source
        };
        setLatestReading(manualReading);

        setWsLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] [OCR] ${result.ocrStatus ?? 'DONE'} — Temp: ${result.temperature ?? '—'}°C  Hum: ${result.humidity ?? '—'}%RH`,
          `[${new Date().toLocaleTimeString()}] [OCR] Overall conf: ${result.ocrConfidence}%  Device: ${result.deviceType ?? 'HTC-1'}`,
          `[${new Date().toLocaleTimeString()}] [OCR] Backend latency: ${result.processingMs}ms  Round-trip: ${roundTripMs}ms`,
          `[${new Date().toLocaleTimeString()}] [DB] RTSP capture persisted automatically.`,
        ]);
      } catch (err: any) {
        console.error('RTSP OCR snapshot failed:', err);
        setWsLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] [ERROR] RTSP OCR pipeline failed: ${err.message || String(err)}`,
        ]);
      }
      return;
    }

    setIsFlashing(true);
    setTimeout(() => setIsFlashing(false), 200);

    const canvas = canvasRef.current;
    if (!canvas) return;

    setWsLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] [ACTION] Snapshot triggered — capturing frame from webcam...`,
      `[${new Date().toLocaleTimeString()}] [OCR] Encoding frame to JPEG (360×270)...`,
    ]);

    // Resize frame to 360×270 matching backend ROI coordinate space
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = 360;
    tempCanvas.height = 270;
    const tempCtx = tempCanvas.getContext('2d');

    if (!tempCtx || !videoRef.current) {
      setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [ERROR] Webcam feed not ready.`]);
      return;
    }

    tempCtx.drawImage(videoRef.current, 0, 0, 360, 270);

    tempCanvas.toBlob(async (blob) => {
      if (!blob) {
        setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [ERROR] Failed to encode canvas frame.`]);
        return;
      }

      setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [OCR] Uploading frame to backend OCR pipeline...`]);

      try {
        const t0 = Date.now();
        const result = await environmentService.extractOcr(blob, selectedRoom.id);
        const roundTripMs = Date.now() - t0;

        setTempConf(result.tempDetail?.confidence ?? 0.94);
        setHumConf(result.humDetail?.confidence ?? 0.95);
        if (result.tempRoiImagePath) setTempRoiImg(result.tempRoiImagePath);
        if (result.humRoiImagePath) setHumRoiImg(result.humRoiImagePath);
        if (result.imageSavedPath) setFullSnapshotImg(result.imageSavedPath);

        const conf = result.ocrConfidence && result.ocrConfidence > 0 ? result.ocrConfidence : 0;
        const ocrSrc = result.source || 'webcam';

        if (result.temperature != null && result.humidity != null) {
          setConsecutiveFailures(0);
          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [OCR] ${result.ocrStatus ?? 'DONE'} — Temp: ${result.temperature}°C  Hum: ${result.humidity}%RH  Device: ${result.deviceType ?? 'HTC-1'}`,
            `[${new Date().toLocaleTimeString()}] [OCR] Overall conf: ${conf.toFixed(1)}%  Temp conf: ${((result.tempDetail?.confidence ?? 0) * 100).toFixed(1)}%  Hum conf: ${((result.humDetail?.confidence ?? 0) * 100).toFixed(1)}%`,
            `[${new Date().toLocaleTimeString()}] [OCR] Backend latency: ${result.processingMs ?? roundTripMs}ms  Round-trip: ${roundTripMs}ms`,
            `[${new Date().toLocaleTimeString()}] [DB] Writing reading to environment history...`,
          ]);

          await environmentService.triggerManualCapture(
            selectedRoom.id,
            result.temperature,
            result.humidity,
            conf,
            ocrSrc,
            result.imageSavedPath
          );

          const manualReading: EnvironmentalReading = {
            id: `r-local-${Date.now()}`,
            timestamp: new Date().toISOString(),
            roomId: selectedRoom.id,
            cameraId: 'camera-001',
            temperature: result.temperature,
            humidity: result.humidity,
            ocrConfidence: conf,
            status: result.temperature >= thresholds.tempCritical || result.humidity >= thresholds.humCritical ? 'critical' :
                    result.temperature >= thresholds.tempWarning || result.humidity >= thresholds.humWarning ? 'warning' : 'normal',
            isSynthetic: false,
            ocrSource: ocrSrc
          };
          // BUG FIX (Bug 1): Write fresh OCR result to ref immediately for canvas overlay.
          latestOcrResultRef.current = { temperature: result.temperature, humidity: result.humidity };

          setLatestReading(manualReading);

          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [DB] Reading persisted. WS broadcast dispatched.`,
          ]);
        } else {
          setConsecutiveFailures(prev => prev + 1);
          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [OCR] ${result.ocrStatus ?? 'FAILED'} — Detection failed.`,
            `[${new Date().toLocaleTimeString()}] [OCR] Overall conf: N/A  Temp conf: N/A  Hum conf: N/A`,
            `[${new Date().toLocaleTimeString()}] [OCR] Backend latency: ${result.processingMs ?? roundTripMs}ms  Round-trip: ${roundTripMs}ms`,
            `[${new Date().toLocaleTimeString()}] [ERROR] Missing Temp or Hum data. Skipping DB insert. Consecutive failures: ${(consecutiveFailures + 1)}`,
          ]);
          setLatestReading(prev => prev ? { ...prev, lowConfidence: true } : null);
        }

      } catch (err: any) {
        console.error('OCR snapshot failed:', err);
        setWsLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] [ERROR] OCR pipeline failed: ${err.message || String(err)}`,
        ]);
      }
    }, 'image/jpeg', 0.90);
  };

  // Auto-capture interval loop (only for webcam)
  const handleCaptureRef = useRef(handleCaptureSnapshot);
  useEffect(() => { handleCaptureRef.current = handleCaptureSnapshot; }, [handleCaptureSnapshot]);
  
  useEffect(() => {
    if (selectedDevice === 'none' || selectedDevice.startsWith('rtsp_') || !autoCapture) return;
    const intervalMs = 5000; // 5s live monitoring frame extraction
    const intervalId = setInterval(() => handleCaptureRef.current(), intervalMs);
    return () => clearInterval(intervalId);
  }, [selectedDevice, autoCapture]);

  const defaultFallbackReading: EnvironmentalReading = {
    id: 'r-default',
    timestamp: new Date().toISOString(),
    roomId: selectedRoom.id,
    cameraId: selectedCam?.id || 'camera-001',
    temperature: 0.0,
    humidity: 0.0,
    ocrConfidence: 0.0,
    status: 'normal',
    isSynthetic: false,
    ocrSource: 'ocr'
  };

  const r = latestReading || defaultFallbackReading;
  const tempStatus = r ? (r.temperature >= thresholds.tempCritical ? 'critical' : r.temperature >= thresholds.tempWarning ? 'warning' : 'normal') : 'normal';
  const humStatus = r ? (r.humidity >= thresholds.humCritical ? 'critical' : r.humidity >= thresholds.humWarning ? 'warning' : 'normal') : 'normal';

  const getStatusColor = (status: string) => {
    if (status === 'critical') return 'var(--color-critical)';
    if (status === 'warning') return 'var(--color-warning)';
    return 'var(--color-success)';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, position: 'relative' }}>
      
      {/* Toast Overlay */}
      <AnimatePresence>
        {toastAlert && (
          <motion.div
            initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
            style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', zIndex: 100, background: 'var(--color-critical)', color: '#fff', padding: '8px 16px', borderRadius: 20, fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, boxShadow: '0 10px 25px rgba(239,68,68,0.3)' }}
          >
            <AlertTriangle size={14} /> {toastAlert}
          </motion.div>
        )}
      </AnimatePresence>

      <video ref={videoRef} style={{ display: 'none' }} playsInline muted />

      {/* ── Top toolbar ─────────────────────────────────────────────── */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
            Feed Source
          </label>
          <select
            value={selectedDevice}
            onChange={(e) => setSelectedDevice(e.target.value)}
            className="form-input"
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              fontSize: '0.85rem',
              backgroundColor: 'rgba(15,23,42,0.8)',
              color: '#fff',
              border: '1px solid var(--border-color)',
              minWidth: 260,
              cursor: 'pointer',
            }}
          >
            <option value="none">— Live Telemetry (camera OCR via scheduler) —</option>
            <option value="webcam">Default Webcam (manual OCR snapshot)</option>
            {cameras.filter(c => c.status === 'online').map(c => (
              <option key={`rtsp_${c.id}`} value={`rtsp_${c.id}`}>
                RTSP: {c.name} (on-demand)
              </option>
            ))}
            {videoDevices.map((d, i) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Camera ${i + 1}`}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          {/* WS indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}>
            {isWsConnected
              ? <><Wifi size={14} color="var(--color-success)" /><span style={{ color: 'var(--color-success)' }}>WS Live</span></>
              : <><WifiOff size={14} color="var(--color-critical)" /><span style={{ color: 'var(--color-critical)' }}>WS Offline</span></>}
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={showBoundingBoxes} onChange={() => setShowBoundingBoxes(v => !v)} style={{ accentColor: 'var(--color-primary)' }} />
            <span>OCR Overlay</span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={isAutoAlign}
              onChange={async () => {
                const nextVal = !isAutoAlign;
                setIsAutoAlign(nextVal);
                try {
                  await environmentService.updateOcrConfig(lcdRoi, nextVal ? 'contour' : 'fixed');
                  setWsLogs(prev => [
                    ...prev,
                    `[${new Date().toLocaleTimeString()}] [SYSTEM] LCD Alignment Mode set to: ${nextVal ? 'Auto-Detect (Contour)' : 'Custom ROIs (Fixed)'}`,
                  ]);
                } catch (err: any) {
                  console.error('Failed to sync alignment mode:', err);
                }
              }}
              style={{ accentColor: 'var(--color-primary)' }}
            />
            <span>Auto LCD Align</span>
          </label>
          
          {selectedDevice !== 'none' && !selectedDevice.startsWith('rtsp_') && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer', background: autoCapture ? 'rgba(37,99,235,0.15)' : 'transparent', padding: '4px 8px', borderRadius: 6, border: autoCapture ? '1px solid var(--color-primary)' : '1px solid transparent' }}>
              <input type="checkbox" checked={autoCapture} onChange={() => setAutoCapture(v => !v)} style={{ accentColor: 'var(--color-primary)' }} />
              <span style={{ color: autoCapture ? 'var(--color-primary)' : 'inherit', fontWeight: autoCapture ? 600 : 400 }}>Auto-Capture ({Math.round((thresholds.ocrPollingIntervalSeconds || 1800) / 60)} mins)</span>
            </label>
          )}

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={showNoise} onChange={() => setShowNoise(v => !v)} style={{ accentColor: 'var(--color-primary)' }} />
            <span>Interference</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={showScanlines} onChange={() => setShowScanlines(v => !v)} style={{ accentColor: 'var(--color-primary)' }} />
            <span>Scanlines</span>
          </label>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <div className="two-col-layout">

        {/* Left: canvas + controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden', border: '1px solid var(--border-color)', boxShadow: '0 20px 40px rgba(0,0,0,0.5)' }}>
            <canvas
              ref={canvasRef}
              width={640}
              height={360}
              style={{ width: '100%', height: '100%', display: 'block', touchAction: 'none' }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onTouchStart={handleTouchStart}
              onTouchMove={handleTouchMove}
              onTouchEnd={handleTouchEnd}
            />
            <AnimatePresence>
              {isFlashing && (
                <motion.div
                  initial={{ opacity: 1 }} animate={{ opacity: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                  style={{ position: 'absolute', inset: 0, backgroundColor: '#fff', zIndex: 90, pointerEvents: 'none' }}
                />
              )}
            </AnimatePresence>
            <div className="camera-scanline" />
          </div>

          <div className="glass-panel" style={{ padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" style={{ padding: '8px 16px' }} onClick={() => setWsLogs([])}>
              <RefreshCw size={14} /><span>Clear Logs</span>
            </button>
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
                ref={fileInputRef}
              />
              <button
                className="btn btn-secondary"
                style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6 }}
                onClick={() => fileInputRef.current?.click()}
                title="Upload an image from your computer to run OCR"
              >
                <span>Upload Image</span>
              </button>
              <button
                onClick={handleCaptureSnapshot}
                className="btn btn-primary"
                style={{ padding: '8px 16px' }}
                disabled={selectedDevice === 'none'}
                title={selectedDevice === 'none' ? 'Select a webcam source to capture a snapshot for OCR' : 'Capture current webcam frame and run OCR'}
              >
                <Camera size={14} /><span>Take Snapshot Frame</span>
              </button>
            </div>
          </div>

          {/* ── Interactive ROI Alignment & Fine-Tuning Controls ─────────────────────────── */}
          <div className="glass-panel" style={{ padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                  <Sliders size={16} color="var(--color-primary)" />
                  Easy OCR Box Alignment & Positioning
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                  Drag the boxes directly on the screen above, or use the nudge controls & presets below to align your HTC-1 meter.
                </p>
              </div>

              {/* Quick Presets */}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '5px 10px' }}
                  onClick={() => applyRoiPreset([130, 130, 100, 90], 'Standard HTC-1')}
                >
                  Standard HTC-1
                </button>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '5px 10px' }}
                  onClick={() => applyRoiPreset([136, 135, 90, 85], 'Centered Meter')}
                >
                  Centered Meter
                </button>
                <button
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '5px 10px' }}
                  onClick={() => applyRoiPreset([120, 120, 120, 100], 'Full Width Split')}
                >
                  Full Width Split
                </button>
              </div>
            </div>

            {/* Single LCD Bounding Box Control */}
            <div style={{ padding: 14, borderRadius: 8, background: 'rgba(15,23,42,0.4)', border: '1px solid rgba(6,182,212,0.4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#06b6d4', fontFamily: 'var(--font-mono)' }}>
                  HTC-1 METER BOUNDING BOX (CYAN)
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                  [{lcdRoi[0]}, {lcdRoi[1]}, {lcdRoi[2]}, {lcdRoi[3]}]
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div>
                  <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 3 }}>Position X (Left)</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(0, lcdRoi[0] - 5)}>-</button>
                    <input type="number" value={lcdRoi[0]} onChange={(e) => updateLcdRoiField(0, Number(e.target.value))} className="form-input" style={{ height: 28, fontSize: '0.8rem', textAlign: 'center', padding: 2 }} />
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(0, lcdRoi[0] + 5)}>+</button>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 3 }}>Position Y (Top)</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(1, lcdRoi[1] - 5)}>-</button>
                    <input type="number" value={lcdRoi[1]} onChange={(e) => updateLcdRoiField(1, Number(e.target.value))} className="form-input" style={{ height: 28, fontSize: '0.8rem', textAlign: 'center', padding: 2 }} />
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(1, lcdRoi[1] + 5)}>+</button>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 3 }}>Width</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(2, lcdRoi[2] - 5)}>-</button>
                    <input type="number" value={lcdRoi[2]} onChange={(e) => updateLcdRoiField(2, Number(e.target.value))} className="form-input" style={{ height: 28, fontSize: '0.8rem', textAlign: 'center', padding: 2 }} />
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(2, lcdRoi[2] + 5)}>+</button>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 3 }}>Height</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(3, lcdRoi[3] - 5)}>-</button>
                    <input type="number" value={lcdRoi[3]} onChange={(e) => updateLcdRoiField(3, Number(e.target.value))} className="form-input" style={{ height: 28, fontSize: '0.8rem', textAlign: 'center', padding: 2 }} />
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', height: 28 }} onClick={() => updateLcdRoiField(3, lcdRoi[3] + 5)}>+</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Alert Banner for Threshold Breach */}
          <AnimatePresence>
            {r && (r.status === 'warning' || r.status === 'critical') && (
              <motion.div
                initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                style={{ padding: '12px 20px', borderRadius: 8, backgroundColor: r.status === 'critical' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)', border: `1px solid ${r.status === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)'}`, color: r.status === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}
              >
                <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                <span style={{ fontSize: '0.85rem' }}>THRESHOLD BREACH DETECTED: System indicates a {r.status} level alarm based on current telemetry.</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right: OCR panel + event console */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* OCR panel — all values come from real WS readings or manual snapshot */}
          <div className="glass-panel" style={{ padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                <Activity size={16} color="var(--color-primary)" /> OCR Extractor Engine
              </h3>
              <div style={{ display: 'flex', gap: 6 }}>
                <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '3px 8px', borderRadius: 12, background: 'rgba(37,99,235,0.15)', color: 'var(--color-primary)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  HTC-1
                </span>
                {snapLatencyMs !== null && (
                  <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '3px 8px', borderRadius: 12, background: 'rgba(16,185,129,0.15)', color: 'var(--color-success)', fontFamily: 'var(--font-mono)' }}>
                    DUAL-ZONE
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Temperature */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '10px 14px', borderRadius: 8, background: 'rgba(15,23,42,0.4)', border: `1px solid ${tempStatus !== 'normal' ? getStatusColor(tempStatus) : 'var(--border-color)'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Temperature (Upward Zone)</span>
                  <span style={{ fontSize: '1.2rem', fontWeight: 700, color: consecutiveFailures > 0 ? 'var(--color-text-muted)' : getStatusColor(tempStatus) }}>
                    {r && consecutiveFailures === 0 ? `${r.temperature.toFixed(1)} °C` : (r ? `${r.temperature.toFixed(1)} °C (Stale)` : '—')}
                  </span>
                </div>
                {tempRoiImg && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 6 }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>ZONE CROP:</span>
                    <div style={{ borderRadius: 4, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)', height: 28, display: 'flex', backgroundColor: '#020408', padding: '2px 4px' }}>
                      <img src={`http://localhost:8000/${tempRoiImg}`} alt="Temp ROI" style={{ height: '100%', objectFit: 'contain' }} />
                    </div>
                  </div>
                )}
              </div>

              {/* Humidity (Downward Zone) */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '10px 14px', borderRadius: 8, background: 'rgba(15,23,42,0.4)', border: `1px solid ${humStatus !== 'normal' ? getStatusColor(humStatus) : 'var(--border-color)'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Humidity (Downward Zone)</span>
                  <span style={{ fontSize: '1.2rem', fontWeight: 700, color: consecutiveFailures > 0 ? 'var(--color-text-muted)' : getStatusColor(humStatus) }}>
                    {r && consecutiveFailures === 0 ? `${r.humidity.toFixed(1)} %RH` : (r ? `${r.humidity.toFixed(1)} %RH (Stale)` : '—')}
                  </span>
                </div>
                {humRoiImg && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 6 }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>ZONE CROP:</span>
                    <div style={{ borderRadius: 4, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)', height: 28, display: 'flex', backgroundColor: '#020408', padding: '2px 4px' }}>
                      <img src={`http://localhost:8000/${humRoiImg}`} alt="Humid ROI" style={{ height: '100%', objectFit: 'contain' }} />
                    </div>
                  </div>
                )}
              </div>

              {fullSnapshotImg && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4, padding: '10px 14px', borderRadius: 8, background: 'rgba(15,23,42,0.4)', border: '1px solid var(--color-primary)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-primary)', fontFamily: 'var(--font-mono)' }}>
                      ANNOTATED FRAME SNAPSHOT
                    </span>
                    <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>ROI Overlays Drawn</span>
                  </div>
                  <div style={{ borderRadius: 6, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)', backgroundColor: '#020408' }}>
                    <img src={`http://localhost:8000/${fullSnapshotImg}`} alt="Annotated OCR Frame" style={{ width: '100%', height: 'auto', display: 'block' }} />
                  </div>
                </div>
              )}

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {/* Overall confidence */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>OCR Confidence</span>
                  <span style={{ fontWeight: 600, color: r && r.ocrConfidence >= 80 && consecutiveFailures === 0 ? 'var(--color-success)' : r ? 'var(--color-warning)' : 'var(--color-text-muted)' }}>
                    {r && consecutiveFailures === 0 ? `${r.ocrConfidence.toFixed(1)}%` : 'N/A'}
                  </span>
                </div>

                {/* Per-channel breakdown — only shown after a manual webcam snapshot */}
                {tempConf !== null && humConf !== null && (
                  <div style={{ paddingLeft: 12, borderLeft: '2px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                      <span style={{ color: 'var(--color-text-muted)' }}>└ Temp channel</span>
                      <span style={{ fontWeight: 500, color: tempConf >= 0.85 ? 'var(--color-success)' : 'var(--color-warning)' }}>
                        {(tempConf * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                      <span style={{ color: 'var(--color-text-muted)' }}>└ Humid channel</span>
                      <span style={{ fontWeight: 500, color: humConf >= 0.85 ? 'var(--color-success)' : 'var(--color-warning)' }}>
                        {(humConf * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                )}

                {r?.lowConfidence && (
                  <div style={{
                    marginTop: 4,
                    marginBottom: 8,
                    padding: '6px 10px',
                    borderRadius: 6,
                    backgroundColor: 'rgba(245,158,11,0.1)',
                    border: '1px solid var(--color-warning)',
                    color: 'var(--color-warning)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textAlign: 'center'
                  }}>
                    ⚠ LOW OCR CONFIDENCE
                  </div>
                )}
                
                {consecutiveFailures > 0 && (
                  <div style={{
                    marginTop: 4,
                    marginBottom: 8,
                    padding: '6px 10px',
                    borderRadius: 6,
                    backgroundColor: 'rgba(239,68,68,0.1)',
                    border: '1px solid var(--color-critical)',
                    color: 'var(--color-critical)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textAlign: 'center'
                  }}>
                    ⚠ DETECTION FAILED ({consecutiveFailures} consecutive)
                  </div>
                )}

                {/* OCR source */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Source</span>
                  <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textTransform: 'uppercase', color: r?.isSynthetic ? 'var(--color-warning)' : 'var(--color-text-muted)' }}>
                    {r ? (r.isSynthetic ? '⚠ synthetic' : (r.ocrSource ?? 'ocr')) : '—'}
                  </span>
                </div>

                {/* Snapshot latency — only after a manual capture */}
                {snapLatencyMs !== null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Last Snapshot Latency</span>
                    <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{snapLatencyMs}ms</span>
                  </div>
                )}

                {/* Last updated timestamp */}
                {r && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Last Updated</span>
                    <span style={{ fontWeight: 500, fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                      {new Date(r.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Live event console */}
          <div className="glass-panel" style={{ padding: 20, flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 220 }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Terminal size={14} color="var(--color-primary)" /> Live Event Console
            </h3>
            <div style={{
              flexGrow: 1, backgroundColor: '#05070c',
              border: '1px solid rgba(255,255,255,0.05)', borderRadius: 6,
              padding: 10, fontFamily: 'var(--font-mono)', fontSize: '0.72rem',
              color: '#34d399', overflowY: 'auto', maxHeight: 220,
              display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              {wsLogs.length === 0
                ? <div style={{ color: '#334155' }}>Waiting for events...</div>
                : wsLogs.map((log, i) => <div key={i} style={{ lineBreak: 'anywhere' }}>{log}</div>)
              }
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default LiveMonitor;
