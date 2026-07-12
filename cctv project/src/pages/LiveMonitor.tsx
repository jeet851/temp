import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { 
  Camera, 
  Play, 
  Pause, 
  Activity, 
  Terminal, 
  RefreshCw
} from 'lucide-react';
import { environmentService } from '../services/environmentService';
import type { LayoutContextType } from '../types';
import { AnimatePresence, motion } from 'framer-motion';

export const LiveMonitor: React.FC = () => {
  const { selectedRoom, cameras } = useOutletContext<LayoutContextType>();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const selectedCam = cameras[0];

  const [isPlaying, setIsPlaying] = useState(true);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [showNoise, setShowNoise] = useState(true);
  const [showScanlines, setShowScanlines] = useState(true);
  const [isFlashing, setIsFlashing] = useState(false);
  const [wsLogs, setWsLogs] = useState<string[]>([]);
  
  // Simulated changing environment values for local canvas rendering
  const [simTemp, setSimTemp] = useState(24.5);
  const [simHum, setSimHum] = useState(58.2);
  const [ocrConfidence, setOcrConfidence] = useState(96.4);
  const [ocrLatency, setOcrLatency] = useState(124); // ms

  // Webcam states
  const [videoDevices, setVideoDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<string>(() => {
    return localStorage.getItem('vg_selected_device') || 'simulation';
  });
  const [webcamStream, setWebcamStream] = useState<MediaStream | null>(null);

  // Persist camera selection
  useEffect(() => {
    localStorage.setItem('vg_selected_device', selectedDevice);
  }, [selectedDevice]);

  // Enumerate video devices on mount
  useEffect(() => {
    navigator.mediaDevices.enumerateDevices()
      .then(devices => {
        const videoInputs = devices.filter(d => d.kind === 'videoinput');
        setVideoDevices(videoInputs);
      })
      .catch(err => {
        console.error("Error enumerating devices:", err);
      });
  }, []);

  // Handle webcam stream start/stop
  useEffect(() => {
    if (selectedDevice === 'simulation') {
      if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        setWebcamStream(null);
      }
      return;
    }

    // Stop current stream first
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
    }

    const constraints = {
      video: selectedDevice === 'webcam' ? true : { deviceId: { exact: selectedDevice } }
    };

    navigator.mediaDevices.getUserMedia(constraints)
      .then(stream => {
        setWebcamStream(stream);
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(e => console.error("Error playing video:", e));
        }
        setWsLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] [SYSTEM] Local webcam stream initialized successfully.`
        ]);
      })
      .catch(err => {
        console.error("Error accessing webcam:", err);
        setSelectedDevice('simulation');
        setWsLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] [ERROR] Failed to access webcam: ${err.message}`
        ]);
      });

    return () => {
      if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
      }
    };
  }, [selectedDevice]);

  // Simulated environment values loop (only active in simulation mode)
  useEffect(() => {
    if (!isPlaying || selectedDevice !== 'simulation') return;
    const interval = setInterval(() => {
      setSimTemp(prev => parseFloat((prev + (Math.random() - 0.5) * 0.4).toFixed(1)));
      setSimHum(prev => parseFloat(Math.max(10, Math.min(100, prev + (Math.random() - 0.5) * 0.8)).toFixed(1)));
      setOcrConfidence(prev => parseFloat(Math.max(80, Math.min(100, prev + (Math.random() - 0.5) * 2)).toFixed(1)));
      setOcrLatency(prev => Math.floor(Math.max(90, Math.min(200, prev + (Math.random() - 0.5) * 20))));
    }, 4000);

    return () => clearInterval(interval);
  }, [isPlaying, selectedDevice]);

  // WebSocket Log simulator (only active in simulation mode)
  useEffect(() => {
    if (!isPlaying || selectedDevice !== 'simulation') return;
    
    setWsLogs([
      `[${new Date().toLocaleTimeString()}] [WS] Connection established to wss://ems-stream.visionguard.net/live/${selectedRoom.id}`,
      `[${new Date().toLocaleTimeString()}] [WS] Handshake approved. RTSP frame decoding initialized.`,
      `[${new Date().toLocaleTimeString()}] [OCR] PaddleOCR engine warm. Ready for reading.`
    ]);

    const logTemplates = [
      () => `[${new Date().toLocaleTimeString()}] [WS] Received frame ${Math.floor(Math.random() * 1000)} (Size: 134KB, Latency: ${Math.floor(Math.random() * 10) + 5}ms)`,
      () => `[${new Date().toLocaleTimeString()}] [OCR] Read event. Extracted Values: Temp=${simTemp}°C, Hum=${simHum}% [Confidence: ${ocrConfidence}%]`,
      () => `[${new Date().toLocaleTimeString()}] [DB] Sync complete. Values registered in PostgreSQL.`,
      () => `[${new Date().toLocaleTimeString()}] [SYS] Camera feed health normal. Avg Jitter: 2.1ms, FPS: ${selectedCam?.fps || 30}`
    ];

    const interval = setInterval(() => {
      const randomTemplate = logTemplates[Math.floor(Math.random() * logTemplates.length)];
      setWsLogs(prev => [...prev.slice(-30), randomTemplate()]);
    }, 3000);

    return () => clearInterval(interval);
  }, [isPlaying, simTemp, simHum, ocrConfidence, selectedRoom.id, selectedCam, selectedDevice]);

  // Main canvas renderer loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      if (selectedDevice !== 'simulation') {
        // Draw real webcam stream frame
        if (videoRef.current && videoRef.current.readyState >= 2) {
          ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
        } else {
          ctx.fillStyle = '#090d16';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = '#64748b';
          ctx.font = '500 13px "Outfit", sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('CONNECTING TO LOCAL WEBCAM FEED...', canvas.width / 2, canvas.height / 2);
        }
      } else {
        // Draw simulated CCTV graphics
        ctx.fillStyle = '#05070c';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        if (selectedCam?.status === 'offline') {
          ctx.fillStyle = '#1e293b';
          ctx.fillRect(20, 20, canvas.width - 40, canvas.height - 40);
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 2;
          ctx.strokeRect(20, 20, canvas.width - 40, canvas.height - 40);

          ctx.fillStyle = '#ef4444';
          ctx.font = '700 16px "Outfit", sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('CAMERA OFFLINE - RTSP CONNECTION FAILED', canvas.width / 2, canvas.height / 2 - 10);
          
          ctx.fillStyle = '#94a3b8';
          ctx.font = '12px "JetBrains Mono", monospace';
          ctx.fillText(`TARGET URL: ${selectedCam.rtspUrl}`, canvas.width / 2, canvas.height / 2 + 15);
          return;
        }

        if (!isPlaying) {
          ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = '#fff';
          ctx.font = '700 20px "Outfit", sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('STREAM PAUSED', canvas.width / 2, canvas.height / 2);
          return;
        }

        ctx.save();
        ctx.strokeStyle = 'rgba(255,255,255,0.015)';
        ctx.lineWidth = 1;
        for (let x = 0; x < canvas.width; x += 15) {
          ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
        }
        for (let y = 0; y < canvas.height; y += 15) {
          ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
        }

        ctx.fillStyle = '#0f172a';
        ctx.fillRect(40, 40, canvas.width - 80, canvas.height - 80);

        ctx.fillStyle = '#1e293b';
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 8;
        ctx.shadowColor = '#000';
        ctx.shadowBlur = 15;
        
        const gX = canvas.width / 2 - 180;
        const gY = canvas.height / 2 - 100;
        const gW = 360;
        const gH = 190;

        ctx.fillRect(gX, gY, gW, gH);
        ctx.strokeRect(gX, gY, gW, gH);
        ctx.shadowBlur = 0;

        ctx.fillStyle = '#090d16';
        ctx.fillRect(gX + 15, gY + 15, gW - 30, gH - 35);
        
        ctx.fillStyle = '#04060b';
        ctx.fillRect(gX + 25, gY + 30, 140, 110);
        ctx.fillRect(gX + 195, gY + 30, 140, 110);

        ctx.fillStyle = '#34d399';
        ctx.shadowColor = ctx.fillStyle;
        ctx.shadowBlur = 8;
        ctx.font = '700 44px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`${simTemp.toFixed(1)}`, gX + 95, gY + 95);
        ctx.shadowBlur = 0;
        ctx.font = '700 12px "Outfit", sans-serif';
        ctx.fillText('°C', gX + 148, gY + 70);

        ctx.fillStyle = '#64748b';
        ctx.font = '600 10px "Outfit", sans-serif';
        ctx.fillText('TEMPERATURE', gX + 95, gY + 125);

        ctx.fillStyle = '#60a5fa';
        ctx.shadowColor = ctx.fillStyle;
        ctx.shadowBlur = 8;
        ctx.font = '700 44px "JetBrains Mono", monospace';
        ctx.fillText(`${simHum.toFixed(1)}`, gX + 265, gY + 95);
        ctx.shadowBlur = 0;
        ctx.font = '700 12px "Outfit", sans-serif';
        ctx.fillText('%', gX + 318, gY + 70);

        ctx.fillStyle = '#64748b';
        ctx.font = '600 10px "Outfit", sans-serif';
        ctx.fillText('RELATIVE HUMIDITY', gX + 265, gY + 125);

        ctx.font = '700 11px "JetBrains Mono", monospace';
        ctx.fillStyle = '#475569';
        ctx.fillText('VISIONGUARD MONITOR SENSOR S-200', gX + gW / 2, gY + gH - 10);
        ctx.restore();
      }

      // Draw bounding boxes overlays
      if (showBoundingBoxes) {
        ctx.lineWidth = 2;
        if (selectedDevice === 'simulation') {
          const gX = canvas.width / 2 - 180;
          const gY = canvas.height / 2 - 100;
          ctx.strokeStyle = '#2563eb';
          ctx.strokeRect(gX + 20, gY + 25, 150, 118);
          ctx.fillStyle = '#2563eb';
          ctx.font = '700 8px "JetBrains Mono", monospace';
          ctx.textAlign = 'left';
          ctx.fillRect(gX + 20, gY + 13, 70, 12);
          ctx.fillStyle = '#ffffff';
          ctx.fillText('OCR TEMP', gX + 24, gY + 22);

          ctx.strokeStyle = '#2563eb';
          ctx.strokeRect(gX + 190, gY + 25, 150, 118);
          ctx.fillStyle = '#2563eb';
          ctx.fillRect(gX + 190, gY + 13, 70, 12);
          ctx.fillStyle = '#ffffff';
          ctx.fillText('OCR HUMI', gX + 194, gY + 22);
        } else {
          // Bounding boxes scaled from 360x270 to canvas dimensions
          const scaleX = canvas.width / 360;
          const scaleY = canvas.height / 270;
          ctx.strokeStyle = '#10b981';

          // Temp ROI
          ctx.strokeRect(43 * scaleX, 58 * scaleY, 110 * scaleX, 48 * scaleY);
          ctx.fillStyle = '#10b981';
          ctx.fillRect(43 * scaleX, (58 - 14) * scaleY, 65 * scaleX, 14 * scaleY);
          ctx.fillStyle = '#ffffff';
          ctx.font = '700 9px "JetBrains Mono", monospace';
          ctx.textAlign = 'left';
          ctx.fillText('ROI TEMP', (43 + 4) * scaleX, (58 - 4) * scaleY);

          // Humidity ROI
          ctx.strokeStyle = '#10b981';
          ctx.strokeRect(175 * scaleX, 58 * scaleY, 115 * scaleX, 48 * scaleY);
          ctx.fillStyle = '#10b981';
          ctx.fillRect(175 * scaleX, (58 - 14) * scaleY, 65 * scaleX, 14 * scaleY);
          ctx.fillStyle = '#ffffff';
          ctx.fillText('ROI HUMID', (175 + 4) * scaleX, (58 - 4) * scaleY);
        }
      }

      // CCTV text overlays
      ctx.fillStyle = 'rgba(0,0,0,0.5)';
      ctx.fillRect(15, 15, 180, 36);
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 10px "JetBrains Mono", monospace';
      ctx.textAlign = 'left';
      ctx.fillText(selectedDevice === 'simulation' ? (selectedCam?.name || 'CCTV CAM-101') : 'WEBCAM LOCAL FEED', 22, 28);
      ctx.font = '500 8px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(255,255,255,0.6)';
      ctx.fillText(selectedDevice === 'simulation' ? `RTSP: ${selectedCam?.rtspUrl?.substring(7, 28) || ''}...` : 'DEVICE: Browser Media Capture', 22, 40);

      const flashes = Math.floor(Date.now() / 600) % 2 === 0;
      ctx.fillStyle = 'rgba(0,0,0,0.5)';
      ctx.fillRect(canvas.width - 95, 15, 80, 24);
      ctx.fillStyle = flashes ? '#ef4444' : '#7f1d1d';
      ctx.beginPath();
      ctx.arc(canvas.width - 80, 27, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 9px "Outfit", sans-serif';
      ctx.fillText('LIVE • REC', canvas.width - 70, 30);

      ctx.fillStyle = 'rgba(0,0,0,0.5)';
      ctx.fillRect(canvas.width - 200, canvas.height - 35, 185, 20);
      ctx.fillStyle = '#ffffff';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillText(new Date().toLocaleString(), canvas.width - 192, canvas.height - 22);

      ctx.fillStyle = 'rgba(0,0,0,0.5)';
      ctx.fillRect(15, canvas.height - 35, 180, 20);
      ctx.fillStyle = '#10b981';
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillText(`FPS: ${selectedCam?.fps || 30} | JITTER: 1.8ms | LATENCY: ${selectedCam?.latencyMs || 120}ms`, 22, canvas.height - 22);

      if (showNoise) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.015)';
        for (let i = 0; i < 400; i++) {
          const rx = Math.random() * canvas.width;
          const ry = Math.random() * canvas.height;
          ctx.fillRect(rx, ry, 2, 2);
        }
      }

      if (showScanlines) {
        ctx.fillStyle = 'rgba(0,0,0,0.15)';
        for (let y = 0; y < canvas.height; y += 4) {
          ctx.fillRect(0, y, canvas.width, 1);
        }
      }

      ctx.fillStyle = 'rgba(37, 99, 235, 0.06)';
      ctx.fillRect(0, (Math.sin(Date.now() / 400) + 1) * canvas.height / 2, canvas.width, 4);
    };

    const loop = () => {
      render();
      animId = requestAnimationFrame(loop);
    };
    loop();

    return () => cancelAnimationFrame(animId);
  }, [selectedCam, isPlaying, showBoundingBoxes, showNoise, showScanlines, simTemp, simHum, selectedDevice]);

  const handleCaptureSnapshot = async () => {
    setIsFlashing(true);
    setTimeout(() => setIsFlashing(false), 200);
    
    if (selectedDevice === 'simulation') {
      setWsLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] [ACTION] Snap triggered manually by Operator.`,
        `[${new Date().toLocaleTimeString()}] [OCR] Reading snapshot values...`,
        `[${new Date().toLocaleTimeString()}] [OCR] SUCCESS. Temp: ${simTemp}°C, Hum: ${simHum}%RH [Confidence: ${ocrConfidence}%]`
      ]);

      // Dispatch snapshot read events to the singleton Mock Engine
      await environmentService.triggerManualCapture(selectedRoom.id, simTemp, simHum);
      return;
    }

    // Webcam mode!
    const canvas = canvasRef.current;
    if (!canvas) return;

    setWsLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] [ACTION] Local webcam snapshot triggered.`,
      `[${new Date().toLocaleTimeString()}] [OCR] Resizing and encoding frame to JPEG...`
    ]);

    // Create a temporary canvas of size 360x270 to match backend's configured ROI
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = 360;
    tempCanvas.height = 270;
    const tempCtx = tempCanvas.getContext('2d');
    
    if (tempCtx && videoRef.current) {
      tempCtx.drawImage(videoRef.current, 0, 0, 360, 270);
      
      tempCanvas.toBlob(async (blob) => {
        if (!blob) {
          setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [ERROR] Failed to capture canvas frame.`]);
          return;
        }

        setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [OCR] Uploading frame to backend for extraction...`]);

        try {
          const startTime = Date.now();
          const result = await environmentService.extractOcr(blob, selectedRoom.id);
          const endTime = Date.now();
          const totalMs = endTime - startTime;

          // Update OCR values in UI
          setSimTemp(result.temperature);
          setSimHum(result.humidity);
          setOcrConfidence(result.ocrConfidence);
          setOcrLatency(result.processingMs || totalMs);

          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [OCR] SUCCESS. Extracted Temp: ${result.temperature}°C, Hum: ${result.humidity}%RH`,
            `[${new Date().toLocaleTimeString()}] [OCR] Extraction confidence: ${result.ocrConfidence}%, backend latency: ${result.processingMs}ms`,
            `[${new Date().toLocaleTimeString()}] [DB] Logging readings to environment history...`
          ]);

          // Write record to database
          await environmentService.triggerManualCapture(selectedRoom.id, result.temperature, result.humidity);

          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [DB] Sync complete. Readings logged successfully.`
          ]);

        } catch (err: any) {
          console.error("OCR Extraction failed:", err);
          setWsLogs(prev => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] [ERROR] OCR Pipeline failed: ${err.message || err}`
          ]);
        }
      }, 'image/jpeg', 0.90);
    } else {
      setWsLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] [ERROR] Webcam video feed not ready.`]);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <video ref={videoRef} style={{ display: 'none' }} playsInline muted />
      
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Active Feed Source</label>
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
              minWidth: 240,
              cursor: 'pointer'
            }}
          >
            <option value="simulation">{selectedCam?.name || 'Alpha CCTV-1'} (Simulation)</option>
            <option value="webcam">Default Webcam</option>
            {videoDevices.map((device, index) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label || `Camera ${index + 1}`}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={showBoundingBoxes} 
              onChange={() => setShowBoundingBoxes(!showBoundingBoxes)}
              style={{ accentColor: 'var(--color-primary)' }} 
            />
            <span>OCR Overlay</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={showNoise} 
              onChange={() => setShowNoise(!showNoise)}
              style={{ accentColor: 'var(--color-primary)' }} 
            />
            <span>Interference</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={showScanlines} 
              onChange={() => setShowScanlines(!showScanlines)}
              style={{ accentColor: 'var(--color-primary)' }} 
            />
            <span>Scanlines</span>
          </label>
        </div>
      </div>

      <div className="two-col-layout">
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', borderRadius: 'var(--border-radius-lg)', overflow: 'hidden', border: '1px solid var(--border-color)', boxShadow: '0 20px 40px rgba(0,0,0,0.5)' }}>
            <canvas 
              ref={canvasRef} 
              width={640} 
              height={360} 
              style={{ width: '100%', height: '100%', display: 'block' }}
            />
            
            <AnimatePresence>
              {isFlashing && (
                <motion.div 
                  initial={{ opacity: 1 }}
                  animate={{ opacity: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  style={{
                    position: 'absolute',
                    top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: '#fff',
                    zIndex: 90,
                    pointerEvents: 'none'
                  }}
                />
              )}
            </AnimatePresence>

            <div className="camera-scanline" />
          </div>

          <div className="glass-panel" style={{ padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', gap: 10 }}>
              <button 
                className="btn btn-secondary" 
                onClick={() => setIsPlaying(!isPlaying)}
                style={{ padding: '8px 16px' }}
                disabled={selectedCam?.status === 'offline' && selectedDevice === 'simulation'}
              >
                {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                <span>{isPlaying ? 'Pause Stream' : 'Resume Feed'}</span>
              </button>
              <button 
                className="btn btn-secondary" 
                style={{ padding: '8px 16px' }}
                onClick={() => setWsLogs([])}
              >
                <RefreshCw size={14} />
                <span>Clear Logs</span>
              </button>
            </div>
            
            <div>
              <button 
                onClick={handleCaptureSnapshot}
                className="btn btn-primary"
                style={{ padding: '8px 16px' }}
                disabled={!isPlaying || (selectedCam?.status === 'offline' && selectedDevice === 'simulation')}
              >
                <Camera size={14} />
                <span>Take Snapshot Frame</span>
              </button>
            </div>
          </div>

        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          
          <div className="glass-panel" style={{ padding: 20 }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Activity size={16} color="var(--color-primary)" /> OCR Extractor Engine
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderRadius: 8, background: 'rgba(15,23,42,0.4)', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Temperature reading</span>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-success)' }}>
                  {simTemp.toFixed(1)} °C
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderRadius: 8, background: 'rgba(15,23,42,0.4)', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Relative Humidity</span>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-primary)' }}>
                  {simHum.toFixed(1)} %RH
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 10 }}>
                <span style={{ color: 'var(--color-text-muted)' }}>OCR Confidence level</span>
                <span style={{ fontWeight: 600, color: 'var(--color-success)' }}>{ocrConfidence.toFixed(1)}%</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>OCR Extract Latency</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{ocrLatency}ms</span>
              </div>
            </div>
          </div>

          <div className="glass-panel" style={{ padding: 20, flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 220 }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Terminal size={14} color="var(--color-primary)" /> Raw WebSocket Message Console
            </h3>

            <div style={{
              flexGrow: 1,
              backgroundColor: '#05070c',
              border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: 6,
              padding: 10,
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              color: '#34d399',
              overflowY: 'auto',
              maxHeight: 220,
              display: 'flex',
              flexDirection: 'column',
              gap: 4
            }}>
              {wsLogs.map((log, i) => (
                <div key={i} style={{ lineBreak: 'anywhere' }}>{log}</div>
              ))}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};

export default LiveMonitor;
