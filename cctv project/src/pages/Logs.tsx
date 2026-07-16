import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { 
  Search, 
  Filter, 
  Image as ImageIcon, 
  ChevronLeft, 
  ChevronRight, 
  Calendar,
  X,
  FileSpreadsheet,
  AlertTriangle,
  Flame
} from 'lucide-react';
import { environmentService } from '../services/environmentService';
import type { LayoutContextType, EnvironmentalHistory } from '../types';
import { motion, AnimatePresence } from 'framer-motion';

export const Logs: React.FC = () => {
  const { selectedRoom } = useOutletContext<LayoutContextType>();

  const [searchTerm, setSearchTerm] = useState('');
  const [filterRisk, setFilterRisk] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Local History records list
  const [history, setHistory] = useState<EnvironmentalHistory[]>([]);

  // Modal State
  const [selectedRecord, setSelectedRecord] = useState<EnvironmentalHistory | null>(null);
  const modalCanvasRef = useRef<HTMLCanvasElement>(null);

  // Fetch initial history logs
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await environmentService.getHistory(selectedRoom.id, 'all', '', '', '', 1, 1000);
        setHistory(res.data);
      } catch (err) {
        console.error('Failed to fetch history logs:', err);
      }
    };
    fetchHistory();
  }, [selectedRoom.id]);

  // Subscribe to live history captures in the background to update the table dynamically
  useEffect(() => {
    const unsubscribe = environmentService.subscribeToHistory((updatedHistory) => {
      setHistory(updatedHistory);
    });
    return () => unsubscribe();
  }, []);

  // Reset page index on filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, filterRisk, startDate, endDate]);

  // Filters logic
  const filteredHistory = history.filter(record => {
    if (filterRisk !== 'all' && record.riskLevel !== filterRisk) return false;
    
    if (searchTerm) {
      const formattedDate = new Date(record.timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }).toLowerCase();
      const tempStr = record.temperature.toString();
      const humStr = record.humidity.toString();
      const riskStr = record.riskLevel.toLowerCase();
      if (!formattedDate.includes(searchTerm.toLowerCase()) && 
          !tempStr.includes(searchTerm) && 
          !humStr.includes(searchTerm) &&
          !riskStr.includes(searchTerm.toLowerCase())) {
        return false;
      }
    }

    // Date inputs give "YYYY-MM-DD" which JS parses as UTC midnight.
    // record.timestamp comes from backend as "...Z" (UTC).
    // Convert start/end to IST-midnight boundaries for a correct comparison.
    if (startDate) {
      // Parse the date string as IST start-of-day (UTC midnight + 5:30 offset)
      const [sy, sm, sd] = startDate.split('-').map(Number);
      const startUTC = new Date(Date.UTC(sy, sm - 1, sd, 0, 0, 0) - 5.5 * 60 * 60 * 1000); // subtract IST offset
      if (new Date(record.timestamp) < startUTC) return false;
    }
    if (endDate) {
      const [ey, em, ed] = endDate.split('-').map(Number);
      // End of day IST = next day UTC 00:00 - IST offset (i.e. 18:30 UTC of the selected day)
      const endUTC = new Date(Date.UTC(ey, em - 1, ed, 23, 59, 59, 999) - 5.5 * 60 * 60 * 1000);
      if (new Date(record.timestamp) > endUTC) return false;
    }

    return true;
  });

  const totalItems = filteredHistory.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage) || 1;
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedHistory = filteredHistory.slice(startIndex, startIndex + itemsPerPage);

  // Draw snapshot canvas in details modal
  useEffect(() => {
    if (!selectedRecord || !modalCanvasRef.current) return;
    const canvas = modalCanvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#080c14';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = selectedRecord.riskLevel === 'high' 
      ? '#ef4444' 
      : selectedRecord.riskLevel === 'medium' ? '#f59e0b' : '#334155';
    ctx.lineWidth = 6;
    ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);

    ctx.fillStyle = '#0b0f19';
    ctx.fillRect(13, 13, canvas.width - 26, canvas.height - 26);

    const grad = ctx.createRadialGradient(
      canvas.width/2, canvas.height/2, 100,
      canvas.width/2, canvas.height/2, canvas.width/2
    );
    grad.addColorStop(0, 'rgba(37, 99, 235, 0.05)');
    grad.addColorStop(1, 'rgba(0,0,0,0.7)');
    ctx.fillStyle = grad;
    ctx.fillRect(13, 13, canvas.width - 26, canvas.height - 26);

    const sX = 60;
    const sY = 40;
    const sW = canvas.width - 120;
    const sH = canvas.height - 85;

    ctx.fillStyle = '#030712';
    ctx.fillRect(sX, sY, sW, sH);
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 2;
    ctx.strokeRect(sX, sY, sW, sH);

    // Temperature LCD
    ctx.fillStyle = selectedRecord.temperature >= 28 ? '#fbbf24' : '#10b981';
    ctx.font = '700 24px "JetBrains Mono", monospace';
    ctx.fillText(`${selectedRecord.temperature.toFixed(1)}°C`, sX + 20, sY + 50);

    ctx.fillStyle = '#4b5563';
    ctx.font = '700 9px "Outfit", sans-serif';
    ctx.fillText('TEMP SENSOR', sX + 20, sY + 68);

    // Humidity LCD
    ctx.fillStyle = selectedRecord.humidity >= 65 ? '#fbbf24' : '#2563eb';
    ctx.font = '700 24px "JetBrains Mono", monospace';
    ctx.fillText(`${selectedRecord.humidity.toFixed(1)}%`, sX + 160, sY + 50);

    ctx.fillStyle = '#4b5563';
    ctx.font = '700 9px "Outfit", sans-serif';
    ctx.fillText('RH HUMIDITY', sX + 160, sY + 68);

    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.strokeRect(sX + 12, sY + 22, 105, 52);
    ctx.strokeRect(sX + 152, sY + 22, 105, 52);
    ctx.setLineDash([]);

    ctx.fillStyle = '#ffffff';
    ctx.font = '700 8px "JetBrains Mono", monospace';
    ctx.fillText(`AI RISK LEVEL: ${selectedRecord.riskLevel.toUpperCase()}`, sX + 15, sY + 95);
    ctx.fillText(`SMOKE: ${selectedRecord.smokeDetected ? 'DETECTED' : 'CLEAR'}  |  FIRE: ${selectedRecord.fireDetected ? 'DETECTED' : 'CLEAR'}`, sX + 15, sY + 110);

    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(15, canvas.height - 32, canvas.width - 30, 16);
    ctx.fillStyle = '#64748b';
    ctx.font = '8px "JetBrains Mono", monospace';
    ctx.fillText(`SNAP TIMESTAMP: ${new Date(selectedRecord.timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: true })} IST | ZONE: SERVER ROOM ALPHA`, 20, canvas.height - 20);

    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(30, 20); ctx.lineTo(15, 20); ctx.lineTo(15, 35);
    ctx.moveTo(canvas.width - 30, 20); ctx.lineTo(canvas.width - 15, 20); ctx.lineTo(canvas.width - 15, 35);
    ctx.stroke();

    ctx.fillStyle = 'rgba(0,0,0,0.1)';
    for(let i=0; i<canvas.height; i+=4) {
      ctx.fillRect(0, i, canvas.width, 1);
    }
  }, [selectedRecord]);

  const handleExportCSV = () => {
    let csvContent = 'data:text/csv;charset=utf-8,';
    csvContent += 'Timestamp,Room,Camera,Temperature(C),Humidity(%RH),Smoke,Fire,Risk Level,Image Path\n';
    
    filteredHistory.forEach(h => {
      const timeStr = new Date(h.timestamp).toISOString();
      const smokeText = h.smokeDetected ? 'DETECTED' : 'CLEAR';
      const fireText = h.fireDetected ? 'DETECTED' : 'CLEAR';
      csvContent += `"${timeStr}","Server Room Alpha","Camera-001",${h.temperature},${h.humidity},"${smokeText}","${fireText}","${h.riskLevel}","${h.imagePath}"\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `visionguard_history_room-001.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      
      {/* Filters Search Panel */}
      <div className="glass-panel" style={{ padding: 20 }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Filter size={16} color="var(--color-primary)" /> Search & Audit Filters
        </h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16
        }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Search History Records</label>
            <div style={{ position: 'relative' }}>
              <Search size={14} color="var(--color-text-dark)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
              <input 
                type="text" 
                className="form-input" 
                placeholder="Search Temp, Hum, Risk..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ width: '100%', paddingLeft: 32, fontSize: '0.85rem', height: 38 }}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">AI Risk Severity</label>
            <select 
              className="form-input form-select"
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value)}
              style={{ width: '100%', fontSize: '0.85rem', height: 38 }}
            >
              <option value="all">All Risks</option>
              <option value="low">Low Risk</option>
              <option value="medium">Medium Risk</option>
              <option value="high">High Risk</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Start Date</label>
            <div style={{ position: 'relative' }}>
              <Calendar size={14} color="var(--color-text-dark)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
              <input 
                type="date" 
                className="form-input" 
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                style={{ width: '100%', paddingLeft: 32, fontSize: '0.85rem', height: 38 }}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">End Date</label>
            <div style={{ position: 'relative' }}>
              <Calendar size={14} color="var(--color-text-dark)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
              <input 
                type="date" 
                className="form-input" 
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                style={{ width: '100%', paddingLeft: 32, fontSize: '0.85rem', height: 38 }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="glass-panel" style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Hourly Environmental Snapshots Database</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Showing {Math.min(totalItems, startIndex + 1)}-{Math.min(totalItems, startIndex + itemsPerPage)} of {totalItems} total logs</p>
          </div>

          <button 
            className="btn btn-secondary" 
            onClick={handleExportCSV}
            disabled={filteredHistory.length === 0}
            style={{ fontSize: '0.85rem', padding: '6px 12px' }}
          >
            <FileSpreadsheet size={14} />
            <span>Export CSV / Excel</span>
          </button>
        </div>

        <div className="table-container">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Room Zone</th>
                <th>Camera Feed</th>
                <th>Temperature</th>
                <th>Humidity</th>
                <th style={{ textAlign: 'center' }}>Smoke Status</th>
                <th style={{ textAlign: 'center' }}>Fire Status</th>
                <th>AI Risk Level</th>
                <th style={{ textAlign: 'center' }}>OCR Source</th>
                <th style={{ textAlign: 'center' }}>Snapshot</th>
                <th style={{ textAlign: 'center' }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {paginatedHistory.map(record => {
                const dateObj = new Date(record.timestamp);
                
                return (
                  <tr key={record.id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                      {new Date(record.timestamp).toLocaleString('en-IN', {
                        timeZone: 'Asia/Kolkata',
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: true
                      })}
                    </td>
                    <td style={{ fontWeight: 600 }}>Server Room Alpha</td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Camera-001</td>
                    <td style={{ fontWeight: 700 }}>{record.temperature.toFixed(1)} °C</td>
                    <td style={{ fontWeight: 700 }}>{record.humidity.toFixed(1)} %RH</td>
                    <td style={{ textAlign: 'center' }}>
                      {record.smokeDetected ? (
                        <span className="status-badge critical" style={{ fontSize: '0.7rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <AlertTriangle size={10} /> SMOKE
                        </span>
                      ) : (
                        <span className="status-badge normal" style={{ fontSize: '0.7rem' }}>CLEAR</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {record.fireDetected ? (
                        <span className="status-badge critical" style={{ fontSize: '0.7rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <Flame size={10} /> FIRE
                        </span>
                      ) : (
                        <span className="status-badge normal" style={{ fontSize: '0.7rem' }}>CLEAR</span>
                      )}
                    </td>
                    <td>
                      <span className={`status-badge ${record.riskLevel === 'high' ? 'critical' : record.riskLevel === 'medium' ? 'warning' : 'normal'}`} style={{ textTransform: 'capitalize' }}>
                        {record.riskLevel} Risk
                      </span>
                    </td>
                    {/* ✅ Step 4c: Synthetic data indicator */}
                    <td style={{ textAlign: 'center' }}>
                      {record.isSynthetic ? (
                        <span
                          className="status-badge warning"
                          style={{ fontSize: '0.65rem', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                          title="This reading was randomly generated — not from a real OCR extraction"
                        >
                          ⚠ SYNTHETIC
                        </span>
                      ) : (
                        <span
                          className="status-badge normal"
                          style={{ fontSize: '0.65rem', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                          title={`Source: ${record.ocrSource || 'ocr'}`}
                        >
                          ✓ {(record.ocrSource || 'OCR').toUpperCase()}
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {/* LCD Display Thumbnail Simulation */}
                      <div 
                        className="glass-panel"
                        style={{
                          padding: '4px 8px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          background: 'rgba(15,23,42,0.6)',
                          borderColor: record.riskLevel === 'high' 
                            ? 'rgba(239, 68, 68, 0.3)' 
                            : record.riskLevel === 'medium'
                              ? 'rgba(245, 158, 11, 0.3)' 
                              : 'rgba(34, 197, 94, 0.3)',
                          borderRadius: 4,
                          fontSize: '0.7rem',
                          fontFamily: 'var(--font-mono)'
                        }}
                      >
                        <span style={{ color: 'var(--color-warning)' }}>{record.temperature.toFixed(1)}°</span>
                        <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
                        <span style={{ color: 'var(--color-primary)' }}>{record.humidity.toFixed(0)}%</span>
                      </div>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button 
                        className="icon-button"
                        onClick={() => setSelectedRecord(record)}
                        style={{ color: 'var(--color-primary)', background: 'rgba(37,99,235,0.08)' }}
                      >
                        <ImageIcon size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}

              {paginatedHistory.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ textAlign: 'center', padding: '40px 0', color: 'var(--color-text-dark)' }}>
                    No environmental history records match the filter selections.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="pagination-controls">
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              Page {currentPage} of {totalPages}
            </span>

            <div style={{ display: 'flex', gap: 6 }}>
              <button 
                className="btn btn-secondary"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                style={{ padding: '6px 12px' }}
              >
                <ChevronLeft size={16} />
                <span>Prev</span>
              </button>
              <button 
                className="btn btn-secondary"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                style={{ padding: '6px 12px' }}
              >
                <span>Next</span>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Snapshot Preview modal */}
      <AnimatePresence>
        {selectedRecord && (
          <div className="modal-overlay" onClick={() => setSelectedRecord(null)}>
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="modal-content"
              onClick={(e) => e.stopPropagation()}
              style={{ width: '100%', maxWidth: 440 }}
            >
              <div className="modal-header">
                <div>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>OCR Frame Image Capture</h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Capture Index: {selectedRecord.id}</p>
                </div>
                <button className="icon-button" onClick={() => setSelectedRecord(null)}>
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

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: '0.8rem' }}>
                  <div className="glass-panel" style={{ padding: '8px 12px', background: 'rgba(15,23,42,0.3)' }}>
                    <div style={{ color: 'var(--color-text-muted)' }}>Temperature</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: 4, color: selectedRecord.temperature >= 28 ? 'var(--color-warning)' : 'var(--color-success)' }}>
                      {selectedRecord.temperature} °C
                    </div>
                  </div>
                  <div className="glass-panel" style={{ padding: '8px 12px', background: 'rgba(15,23,42,0.3)' }}>
                    <div style={{ color: 'var(--color-text-muted)' }}>Humidity</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: 4, color: selectedRecord.humidity >= 65 ? 'var(--color-warning)' : 'var(--color-primary)' }}>
                      {selectedRecord.humidity} %RH
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.8rem', padding: '4px 8px' }}>
                  <div className="flex-row-center" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: 6 }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Fire Status</span>
                    <span style={{ fontWeight: 600, color: selectedRecord.fireDetected ? 'var(--color-critical)' : 'var(--color-success)' }}>
                      {selectedRecord.fireDetected ? '🔥 FLAME DETECTED' : 'CLEAR'}
                    </span>
                  </div>
                  <div className="flex-row-center" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: 6 }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Smoke Status</span>
                    <span style={{ fontWeight: 600, color: selectedRecord.smokeDetected ? 'var(--color-critical)' : 'var(--color-success)' }}>
                      {selectedRecord.smokeDetected ? '💨 SMOKE DETECTED' : 'CLEAR'}
                    </span>
                  </div>
                  <div className="flex-row-center">
                    <span style={{ color: 'var(--color-text-muted)' }}>AI Risk Evaluation</span>
                    <span className={`status-badge ${selectedRecord.riskLevel === 'high' ? 'critical' : selectedRecord.riskLevel === 'medium' ? 'warning' : 'normal'}`}>
                      {selectedRecord.riskLevel.toUpperCase()} RISK
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                  <button className="btn btn-secondary" onClick={() => setSelectedRecord(null)}>
                    Close Preview
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
};
export default Logs;
