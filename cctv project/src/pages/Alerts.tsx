import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { 
  AlertTriangle, 
  Check, 
  Eye, 
  Clock, 
  Server, 
  Camera,
  X,
  ShieldAlert,
  SlidersHorizontal
} from 'lucide-react';
import { alertService } from '../services/alertService';
import type { LayoutContextType, Alert } from '../types';
import { motion, AnimatePresence } from 'framer-motion';

export const Alerts: React.FC = () => {
  const { rooms, cameras } = useOutletContext<LayoutContextType>();

  const [filterType, setFilterType] = useState<'all' | 'temperature' | 'humidity'>('all');
  const [filterSeverity, setFilterSeverity] = useState<'all' | 'warning' | 'critical'>('all');
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'acknowledged'>('all');
  
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const modalCanvasRef = useRef<HTMLCanvasElement>(null);

  // Fetch initial alerts and subscribe to changes
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const loadedAlerts = await alertService.getAlerts();
        setAlerts(loadedAlerts);
      } catch (err) {
        console.error('Failed to load alerts list:', err);
      }
    };

    fetchAlerts();

    const unsubscribe = alertService.subscribeToAlerts((updatedAlerts) => {
      setAlerts(updatedAlerts);
    });
    return () => unsubscribe();
  }, []);

  // Filter alerts logic
  const filteredAlerts = alerts.filter(alert => {
    if (filterType !== 'all' && alert.type !== filterType) return false;
    if (filterSeverity !== 'all' && alert.severity !== filterSeverity) return false;
    if (filterStatus !== 'all' && alert.status !== filterStatus) return false;
    return true;
  });

  // Render modal canvas details
  useEffect(() => {
    if (!selectedAlert || !modalCanvasRef.current) return;
    const canvas = modalCanvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#08080f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 4;
    ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);

    ctx.fillStyle = '#090c15';
    ctx.fillRect(12, 12, canvas.width - 24, canvas.height - 24);

    const mX = 50;
    const mY = 40;
    const mW = canvas.width - 100;
    const mH = canvas.height - 80;

    ctx.fillStyle = '#020306';
    ctx.fillRect(mX, mY, mW, mH);
    ctx.strokeStyle = '#374151';
    ctx.strokeRect(mX, mY, mW, mH);

    ctx.fillStyle = selectedAlert.severity === 'critical' ? '#f87171' : '#fbbf24';
    ctx.font = '700 24px "JetBrains Mono", monospace';
    
    if (selectedAlert.type === 'temperature') {
      ctx.fillText(`${selectedAlert.value.toFixed(1)}°C`, mX + 25, mY + 50);
      ctx.fillStyle = '#ef4444';
      ctx.fillText('CRIT TEMP', mX + 155, mY + 50);
    } else {
      ctx.fillText(`${selectedAlert.value.toFixed(1)}%`, mX + 25, mY + 50);
      ctx.fillStyle = '#ef4444';
      ctx.fillText('CRIT HUMI', mX + 155, mY + 50);
    }

    ctx.fillStyle = '#4b5563';
    ctx.font = '700 8px "Outfit", sans-serif';
    ctx.fillText('EXTRACTED READ', mX + 25, mY + 68);
    ctx.fillText('ALERT METRIC', mX + 155, mY + 68);

    ctx.fillStyle = 'rgba(239, 68, 68, 0.1)';
    ctx.fillRect(14, canvas.height - 32, canvas.width - 28, 16);
    ctx.fillStyle = '#f87171';
    ctx.font = '700 8px "JetBrains Mono", monospace';
    
    const roomName = rooms.find(r => r.id === selectedAlert.roomId)?.name || 'UNKNOWN';
    ctx.fillText(`ALERT TRIGGER: ${new Date(selectedAlert.timestamp).toLocaleString()} | SITE: ${roomName.toUpperCase()}`, 20, canvas.height - 20);

    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.strokeRect(mX + 15, mY + 22, 105, 52);
    ctx.setLineDash([]);

    ctx.fillStyle = 'rgba(239, 68, 68, 0.08)';
    for (let y = 0; y < canvas.height; y += 6) {
      ctx.fillRect(0, y, canvas.width, 2);
    }

  }, [selectedAlert, rooms]);

  const handleAcknowledge = (id: string) => {
    alertService.acknowledgeAlert(id, 'sysadmin@visionguard.net');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      
      {/* Alert summaries cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 20
      }}>
        <div className="glass-panel" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16, borderLeft: '4px solid var(--color-critical)' }}>
          <div style={{ padding: 10, borderRadius: 8, background: 'rgba(239,68,68,0.1)', color: 'var(--color-critical)' }}>
            <ShieldAlert size={24} />
          </div>
          <div>
            <h4 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
              {alerts.filter(a => a.status === 'active' && a.severity === 'critical').length}
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Active Criticals</p>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16, borderLeft: '4px solid var(--color-warning)' }}>
          <div style={{ padding: 10, borderRadius: 8, background: 'rgba(245,158,11,0.1)', color: 'var(--color-warning)' }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <h4 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
              {alerts.filter(a => a.status === 'active' && a.severity === 'warning').length}
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Active Warnings</p>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16, borderLeft: '4px solid var(--color-success)' }}>
          <div style={{ padding: 10, borderRadius: 8, background: 'rgba(34,197,94,0.1)', color: 'var(--color-success)' }}>
            <Check size={24} />
          </div>
          <div>
            <h4 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
              {alerts.filter(a => a.status === 'acknowledged').length}
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Acknowledged Alerts</p>
          </div>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <SlidersHorizontal size={14} color="var(--color-text-dark)" />
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>FILTER DISPATCH</span>
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <select 
            className="form-input form-select"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as any)}
            style={{ padding: '6px 12px', fontSize: '0.8rem', height: 34 }}
          >
            <option value="all">All Metrics</option>
            <option value="temperature">Temperature Alerts</option>
            <option value="humidity">Humidity Alerts</option>
          </select>

          <select 
            className="form-input form-select"
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value as any)}
            style={{ padding: '6px 12px', fontSize: '0.8rem', height: 34 }}
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical Only</option>
            <option value="warning">Warning Only</option>
          </select>

          <select 
            className="form-input form-select"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as any)}
            style={{ padding: '6px 12px', fontSize: '0.8rem', height: 34 }}
          >
            <option value="all">All States</option>
            <option value="active">Active Alerts</option>
            <option value="acknowledged">Acknowledged</option>
          </select>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: 24 }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16 }}>Active and Resolved Alerts Log</h3>

        <div className="table-container">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Date / Time</th>
                <th>Room</th>
                <th>Source Camera</th>
                <th>Type</th>
                <th>Reading</th>
                <th>Threshold</th>
                <th>Severity</th>
                <th>Status</th>
                <th style={{ textAlign: 'center' }}>Details</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.map(alert => {
                const dateObj = new Date(alert.timestamp);
                const room = rooms.find(r => r.id === alert.roomId);
                const cam = cameras.find(c => c.id === alert.cameraId);
                const unit = alert.type === 'temperature' ? '°C' : '%RH';

                return (
                  <tr 
                    key={alert.id}
                    style={{
                      backgroundColor: alert.status === 'active' 
                        ? (alert.severity === 'critical' ? 'rgba(239,68,68,0.03)' : 'rgba(245,158,11,0.02)')
                        : 'transparent'
                    }}
                  >
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                      {dateObj.toLocaleDateString()} {dateObj.toLocaleTimeString()}
                    </td>
                    <td style={{ fontWeight: 500 }}>{room?.name || alert.roomId}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>{cam?.name || alert.cameraId}</td>
                    <td style={{ fontWeight: 600, textTransform: 'uppercase', fontSize: '0.8rem' }}>{alert.type}</td>
                    <td style={{ fontWeight: 700, color: alert.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)' }}>
                      {alert.value.toFixed(1)} {unit}
                    </td>
                    <td>{alert.threshold} {unit}</td>
                    <td>
                      <span className={`status-badge ${alert.severity}`}>
                        {alert.severity}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${alert.status === 'active' ? 'critical' : 'normal'}`} style={{ textTransform: 'capitalize' }}>
                        {alert.status}
                      </span>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button 
                        className="icon-button"
                        onClick={() => setSelectedAlert(alert)}
                        style={{ color: 'var(--color-primary)', background: 'rgba(37,99,235,0.08)' }}
                      >
                        <Eye size={14} />
                      </button>
                    </td>
                    <td>
                      {alert.status === 'active' ? (
                        <button 
                          onClick={() => handleAcknowledge(alert.id)}
                          className="btn btn-primary"
                          style={{
                            padding: '4px 10px',
                            fontSize: '0.75rem',
                            borderRadius: 'var(--border-radius-sm)',
                            backgroundColor: 'rgba(34,197,94,0.1)',
                            border: '1px solid rgba(34,197,94,0.3)',
                            color: 'var(--color-success)',
                            boxShadow: 'none'
                          }}
                        >
                          <span>Acknowledge</span>
                        </button>
                      ) : (
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-dark)', display: 'flex', flexDirection: 'column' }}>
                          <span>Ack by Admin</span>
                          <span style={{ fontSize: '0.65rem' }}>{new Date(alert.acknowledgedAt || '').toLocaleTimeString()}</span>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}

              {filteredAlerts.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ textAlign: 'center', padding: '40px 0', color: 'var(--color-text-dark)' }}>
                    No system alerts recorded for this filter selection.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Alert Image Modal */}
      <AnimatePresence>
        {selectedAlert && (
          <div className="modal-overlay" onClick={() => setSelectedAlert(null)}>
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="modal-content"
              onClick={(e) => e.stopPropagation()}
              style={{ width: '100%', maxWidth: 440, borderColor: selectedAlert.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)' }}
            >
              <div className="modal-header">
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-critical)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertTriangle size={18} /> OCR Frame Crop (Alert State)
                  </h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>ID: {selectedAlert.id}</p>
                </div>
                <button className="icon-button" onClick={() => setSelectedAlert(null)}>
                  <X size={18} />
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ position: 'relative', width: '100%', aspectRatio: '4/3', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border-color)' }}>
                  <canvas 
                    ref={modalCanvasRef}
                    width={380}
                    height={285}
                    style={{ width: '100%', height: '100%', display: 'block' }}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.8rem' }}>
                  <div className="flex-row-center" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: 6 }}>
                    <span style={{ color: 'var(--color-text-muted)' }}><Server size={12} style={{ marginRight: 6, display: 'inline-block' }} /> Monitoring Site</span>
                    <span style={{ fontWeight: 600 }}>{rooms.find(r => r.id === selectedAlert.roomId)?.name}</span>
                  </div>

                  <div className="flex-row-center" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: 6 }}>
                    <span style={{ color: 'var(--color-text-muted)' }}><Camera size={12} style={{ marginRight: 6, display: 'inline-block' }} /> Hardware Source</span>
                    <span style={{ fontWeight: 600 }}>{cameras.find(c => c.id === selectedAlert.cameraId)?.name}</span>
                  </div>

                  <div className="flex-row-center" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: 6 }}>
                    <span style={{ color: 'var(--color-text-muted)' }}><Clock size={12} style={{ marginRight: 6, display: 'inline-block' }} /> Timestamp</span>
                    <span style={{ fontWeight: 600 }}>{new Date(selectedAlert.timestamp).toLocaleString()}</span>
                  </div>

                  <div className="flex-row-center">
                    <span style={{ color: 'var(--color-text-muted)' }}>Threshold Exceeded</span>
                    <span style={{ fontWeight: 600, color: 'var(--color-critical)' }}>
                      {selectedAlert.value} {selectedAlert.type === 'temperature' ? '°C' : '%RH'} (Threshold: {selectedAlert.threshold} {selectedAlert.type === 'temperature' ? '°C' : '%RH'})
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                  <button className="btn btn-secondary" onClick={() => setSelectedAlert(null)}>
                    Close Panel
                  </button>
                  {selectedAlert.status === 'active' && (
                    <button 
                      className="btn btn-primary"
                      onClick={() => {
                        handleAcknowledge(selectedAlert.id);
                        setSelectedAlert(null);
                      }}
                    >
                      <Check size={14} />
                      <span>Acknowledge Alert</span>
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
};
export default Alerts;
