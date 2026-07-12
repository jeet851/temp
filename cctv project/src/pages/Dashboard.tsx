import React, { useEffect, useState, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { 
  Camera, 
  AlertTriangle,
  History,
  TrendingUp,
  CheckCircle
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { environmentService } from '../services/environmentService';
import { alertService } from '../services/alertService';
import type { 
  EnvironmentalReading, 
  Alert, 
  EnvironmentalHistory, 
  LayoutContextType 
} from '../types';
import { EnvironmentalGauge } from '../components/EnvironmentalGauge';

export const Dashboard: React.FC = () => {
  const { selectedRoom, cameras, thresholds } = useOutletContext<LayoutContextType>();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Local Page States (Subscribed to Services)
  const [readings, setReadings] = useState<EnvironmentalReading[]>([]);
  const [history, setHistory] = useState<EnvironmentalHistory[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  // Reload readings, history, and alerts when selectedRoom context changes
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [r, hData, a] = await Promise.all([
          environmentService.getReadings(selectedRoom.id),
          environmentService.getHistory(selectedRoom.id),
          alertService.getAlerts(selectedRoom.id)
        ]);
        setReadings(r);
        setHistory(hData.data);
        setAlerts(a);
      } catch (err) {
        console.error('Failed to load dashboard statistics data:', err);
      }
    };
    
    loadDashboardData();
  }, [selectedRoom.id]);

  // Subscribe to live updates from Mock Engine via Services
  useEffect(() => {
    // 1. Subscribe to new environmental live updates
    const unsubscribeReadings = environmentService.subscribeToReadings((newReading) => {
      if (newReading.roomId === selectedRoom.id) {
        setReadings(prev => [newReading, ...prev.slice(0, 499)]);
      }
    });

    // 2. Subscribe to alert logs updates (acknowledgements or new alerts)
    const unsubscribeAlerts = alertService.subscribeToAlerts((updatedAlerts) => {
      setAlerts(updatedAlerts.filter(a => a.roomId === selectedRoom.id));
    });

    // 3. Subscribe to environmental history log updates
    const unsubscribeHistory = environmentService.subscribeToHistory((updatedHistory) => {
      setHistory(updatedHistory);
    });

    return () => {
      unsubscribeReadings();
      unsubscribeAlerts();
      unsubscribeHistory();
    };
  }, [selectedRoom.id]);

  // Calculations
  const activeCamera = cameras.find(c => c.roomId === selectedRoom.id && c.status === 'online') 
    || cameras.find(c => c.roomId === selectedRoom.id);

  const latestReading = readings[0] || {
    temperature: 0.0,
    humidity: 0.0,
    ocrConfidence: 0.0,
    timestamp: new Date().toISOString(),
    status: 'normal'
  };

  // Highs and Lows computations for Today from historical records
  const tempValues = history.map(h => h.temperature);
  const humValues = history.map(h => h.humidity);
  
  const maxTemp = tempValues.length ? Math.max(...tempValues) : 0.0;
  const minTemp = tempValues.length ? Math.min(...tempValues) : 0.0;
  const maxHum = humValues.length ? Math.max(...humValues) : 0.0;
  const minHum = humValues.length ? Math.min(...humValues) : 0.0;

  // Chart data formatting using hourly history points
  const chartData = [...history].reverse().slice(-12).map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    temperature: h.temperature,
    humidity: h.humidity
  }));

  // Simulating the camera digital monitor crop canvas drawing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    
    const draw = () => {
      ctx.fillStyle = '#090d16';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw Grid / Scanlines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
      ctx.lineWidth = 1;
      const step = 20;
      for (let i = 0; i < canvas.width; i += step) {
        ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, canvas.height); ctx.stroke();
      }
      for (let i = 0; i < canvas.height; i += step) {
        ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(canvas.width, i); ctx.stroke();
      }

      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 4;
      ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);

      const gradient = ctx.createRadialGradient(
        canvas.width / 2, canvas.height / 2, 80,
        canvas.width / 2, canvas.height / 2, canvas.width / 2
      );
      gradient.addColorStop(0, 'rgba(0,0,0,0)');
      gradient.addColorStop(1, 'rgba(0,0,0,0.5)');
      ctx.fillStyle = gradient;
      ctx.fillRect(10, 10, canvas.width - 20, canvas.height - 20);

      ctx.fillStyle = '#111827';
      ctx.strokeStyle = '#334155';
      ctx.lineWidth = 2;
      
      const monX = 50;
      const monY = 35;
      const monW = canvas.width - 100;
      const monH = canvas.height - 70;
      
      ctx.fillRect(monX, monY, monW, monH);
      ctx.strokeRect(monX, monY, monW, monH);

      ctx.font = '700 12px "JetBrains Mono", monospace';
      ctx.fillStyle = '#64748b';
      ctx.fillText('VISIONGUARD INDUSTRIAL OCR v1.1', monX + 15, monY + 22);

      // Temperature LCD
      ctx.fillStyle = latestReading.temperature >= thresholds.tempCritical 
        ? '#ef4444' 
        : latestReading.temperature >= thresholds.tempWarning ? '#f59e0b' : '#10b981';
      ctx.font = '700 28px "JetBrains Mono", monospace';
      ctx.fillText(`${latestReading.temperature.toFixed(1)}°C`, monX + 25, monY + 60);
      
      ctx.font = '500 11px "Outfit", sans-serif';
      ctx.fillStyle = '#4b5563';
      ctx.fillText('TEMPERATURE', monX + 25, monY + 75);

      // Humidity LCD
      ctx.fillStyle = latestReading.humidity >= thresholds.humCritical 
        ? '#ef4444' 
        : latestReading.humidity >= thresholds.humWarning ? '#f59e0b' : '#3b82f6';
      ctx.font = '700 28px "JetBrains Mono", monospace';
      ctx.fillText(`${latestReading.humidity.toFixed(1)}%RH`, monX + 160, monY + 60);

      ctx.fillStyle = '#4b5563';
      ctx.font = '500 11px "Outfit", sans-serif';
      ctx.fillText('REL HUMIDITY', monX + 160, monY + 75);

      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(monX + 18, monY + 35, 110, 48);
      ctx.strokeRect(monX + 152, monY + 35, 115, 48);
      ctx.setLineDash([]);

      ctx.fillStyle = '#2563eb';
      ctx.fillRect(monX + 18, monY + 88, 120, 16);
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 8px "JetBrains Mono", monospace';
      ctx.fillText(`OCR CONF: ${latestReading.ocrConfidence.toFixed(1)}%`, monX + 24, monY + 99);

      ctx.fillStyle = '#10b981';
      ctx.fillRect(monX + 148, monY + 88, 115, 16);
      ctx.fillStyle = '#ffffff';
      ctx.fillText('STATE: VERIFIED', monX + 154, monY + 99);

      ctx.strokeStyle = 'rgba(34, 197, 94, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(40, 25); ctx.lineTo(25, 25); ctx.lineTo(25, 40); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(canvas.width - 40, 25); ctx.lineTo(canvas.width - 25, 25); ctx.lineTo(canvas.width - 25, 40); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(40, canvas.height - 25); ctx.lineTo(25, canvas.height - 25); ctx.lineTo(25, canvas.height - 40); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(canvas.width - 40, canvas.height - 25); ctx.lineTo(canvas.width - 25, canvas.height - 25); ctx.lineTo(canvas.width - 25, canvas.height - 40); ctx.stroke();

      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(15, canvas.height - 35, canvas.width - 30, 20);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px "JetBrains Mono", sans-serif';
      const camLabel = activeCamera ? `${activeCamera.name} | ${activeCamera.fps} FPS | ${activeCamera.latencyMs}ms` : 'NO LIVE CAMERA';
      ctx.fillText(camLabel, 22, canvas.height - 22);

      ctx.fillStyle = 'rgba(37, 99, 235, 0.05)';
      ctx.fillRect(10, 10 + (Math.sin(Date.now() / 600) + 1) * (canvas.height - 40) / 2, canvas.width - 20, 2);
    };

    const animate = () => {
      draw();
      animationId = requestAnimationFrame(animate);
    };
    animate();

    return () => cancelAnimationFrame(animationId);
  }, [latestReading, activeCamera, thresholds]);

  // Format Next capture timestamps
  const lastCaptureTime = readings[0] ? new Date(readings[0].timestamp).toLocaleTimeString() : 'N/A';
  const nextCaptureTime = readings[0] ? new Date(new Date(readings[0].timestamp).getTime() + 5000).toLocaleTimeString() : 'N/A';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      
      {/* Dynamic Animated circular Gauges */}
      <div className="chart-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <EnvironmentalGauge 
          value={latestReading.temperature}
          type="temperature"
          title={`${selectedRoom.name} - Temperature`}
          status={latestReading.status}
          min={10}
          max={45}
          unit="°C"
        />
        <EnvironmentalGauge 
          value={latestReading.humidity}
          type="humidity"
          title={`${selectedRoom.name} - Humidity`}
          status={latestReading.status}
          min={20}
          max={90}
          unit="%RH"
        />
      </div>

      {/* Enterprise Mini KPI Cards Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 20
      }}>
        {/* Temp Peak/Low Card */}
        <div className="glass-panel text-muted" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-warning)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Temp Extremes Today
          </span>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)' }}>{maxTemp.toFixed(1)}°C</p>
              <span style={{ fontSize: '0.65rem', color: 'var(--color-text-dark)' }}>HIGHEST</span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)' }}>{minTemp.toFixed(1)}°C</p>
              <span style={{ fontSize: '0.65rem', color: 'var(--color-text-dark)' }}>LOWEST</span>
            </div>
          </div>
        </div>

        {/* Humidity Peak/Low Card */}
        <div className="glass-panel text-muted" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-primary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Humidity Extremes Today
          </span>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)' }}>{maxHum.toFixed(1)}%</p>
              <span style={{ fontSize: '0.65rem', color: 'var(--color-text-dark)' }}>HIGHEST</span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)' }}>{minHum.toFixed(1)}%</p>
              <span style={{ fontSize: '0.65rem', color: 'var(--color-text-dark)' }}>LOWEST</span>
            </div>
          </div>
        </div>

        {/* Capture timings logs */}
        <div className="glass-panel text-muted" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            OCR Capture Timeline
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.8rem' }}>
            <div className="flex-row-center">
              <span>Last Snapshot:</span>
              <span style={{ fontWeight: 600, color: 'var(--color-text-main)', fontFamily: 'var(--font-mono)' }}>{lastCaptureTime}</span>
            </div>
            <div className="flex-row-center">
              <span>Next Scheduled:</span>
              <span style={{ fontWeight: 600, color: 'var(--color-primary)', fontFamily: 'var(--font-mono)' }}>{nextCaptureTime}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Section Grid Layout */}
      <div className="two-col-layout">
        
        {/* Left Col: Historical chart trends and records table */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          
          {/* Trends Area Chart */}
          <div className="glass-panel" style={{ padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Environmental Trends (Recent readings)</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Continuous analytics chart for {selectedRoom.name}</p>
              </div>
              <div style={{ display: 'flex', gap: 12, fontSize: '0.75rem', fontWeight: 600 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--color-warning)' }}>
                  <TrendingUp size={14} /> Temp (°C)
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--color-primary)' }}>
                  <TrendingUp size={14} /> Humidity (%)
                </span>
              </div>
            </div>

            <div style={{ width: '100%', height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chartData}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="tempColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-warning)" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="var(--color-warning)" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="humiColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="time" stroke="#64748b" fontSize={11} tickLine={false} />
                  <YAxis stroke="#64748b" fontSize={11} tickLine={false} domain={['auto', 'auto']} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--bg-card-solid)', 
                      borderColor: 'var(--border-color)',
                      color: 'var(--color-text-main)',
                      borderRadius: 8,
                      fontSize: 12
                    }} 
                  />
                  <Area 
                    type="monotone" 
                    dataKey="temperature" 
                    stroke="var(--color-warning)" 
                    strokeWidth={2.5} 
                    fillOpacity={1} 
                    fill="url(#tempColor)" 
                    name="Temperature (°C)"
                  />
                  <Area 
                    type="monotone" 
                    dataKey="humidity" 
                    stroke="var(--color-primary)" 
                    strokeWidth={2.5} 
                    fillOpacity={1} 
                    fill="url(#humiColor)" 
                    name="Humidity (%RH)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Mini Readings log table */}
          <div className="glass-panel" style={{ padding: 24 }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <History size={16} /> Recent Environmental Readings
            </h3>

            <div className="table-container">
              <table className="enterprise-table">
                <thead>
                  <tr>
                    <th>Date / Time</th>
                    <th>Temperature</th>
                    <th>Humidity</th>
                    <th>OCR Confidence</th>
                    <th>Alert Status</th>
                  </tr>
                </thead>
                <tbody>
                  {readings.slice(0, 5).map(reading => (
                    <tr key={reading.id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                        {new Date(reading.timestamp).toLocaleString()}
                      </td>
                      <td style={{ fontWeight: 600 }}>{reading.temperature.toFixed(1)} °C</td>
                      <td style={{ fontWeight: 600 }}>{reading.humidity.toFixed(1)} %RH</td>
                      <td>
                        <span style={{ 
                          color: reading.ocrConfidence >= 95 
                            ? 'var(--color-success)' 
                            : reading.ocrConfidence >= 85 
                              ? 'var(--color-warning)' 
                              : 'var(--color-critical)'
                        }}>
                          {reading.ocrConfidence.toFixed(1)}%
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${reading.status}`}>
                          {reading.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>

        {/* Right Col: CCTV feed canvas frame, active alerts list, system diagnostics health */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          
          {/* Latest Camera Crop Card */}
          <div className="glass-panel" style={{ padding: 20 }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Camera size={16} color="var(--color-primary)" /> Latest Camera Capture Frame
            </h3>
            
            <div style={{ position: 'relative', width: '100%', aspectRatio: '4/3', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border-color)' }}>
              <canvas 
                ref={canvasRef} 
                width={360} 
                height={270} 
                style={{ width: '100%', height: '100%', display: 'block' }}
              />
              <div className="camera-retrace" />
              <div style={{
                position: 'absolute',
                bottom: 8,
                right: 8,
                backgroundColor: 'rgba(0,0,0,0.7)',
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: '0.65rem',
                fontFamily: 'var(--font-mono)',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.1)'
              }}>
                [LIVE FEED]
              </div>
            </div>
          </div>

          {/* Active Alerts */}
          <div className="glass-panel" style={{ padding: 20 }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertTriangle size={16} color="var(--color-critical)" /> Recent Room Alerts ({alerts.filter(a => a.status === 'active').length})
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {alerts.length === 0 ? (
                <div style={{ padding: '20px 0', textTransform: 'uppercase', textAlign: 'center', color: 'var(--color-text-dark)', fontSize: '0.8rem', fontWeight: 600 }}>
                  <CheckCircle size={20} style={{ color: 'var(--color-success)', margin: '0 auto 8px', display: 'block' }} />
                  Room Status Secure
                </div>
              ) : (
                alerts.slice(0, 3).map(alert => (
                  <div 
                    key={alert.id}
                    className="glass-panel"
                    style={{
                      padding: 12,
                      background: 'rgba(15, 23, 42, 0.4)',
                      borderColor: alert.severity === 'critical' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 12,
                      fontSize: '0.8rem'
                    }}
                  >
                    <div style={{ color: alert.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)', marginTop: 2, flexShrink: 0 }}>
                      <AlertTriangle size={16} />
                    </div>
                    <div style={{ flexGrow: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                        <span style={{ color: alert.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)' }}>
                          {alert.type.toUpperCase()} LIMIT EXCEEDED ({alert.status.toUpperCase()})
                        </span>
                        <span style={{ color: 'var(--color-text-dark)', fontSize: '0.7rem' }}>
                          {new Date(alert.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p style={{ marginTop: 4, color: 'var(--color-text-muted)' }}>
                        Triggered reading: <strong style={{ color: 'var(--color-text-main)' }}>{alert.value}{alert.type === 'temperature' ? '°C' : '%RH'}</strong> (Limit: {alert.threshold}{alert.type === 'temperature' ? '°C' : '%RH'})
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
export default Dashboard;
