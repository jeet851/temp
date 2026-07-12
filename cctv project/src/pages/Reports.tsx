import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { 
  FileText, 
  Award, 
  Loader2, 
  FileSpreadsheet, 
  AlertOctagon
} from 'lucide-react';
import { reportService } from '../services/reportService';
import { environmentService } from '../services/environmentService';
import type { LayoutContextType, ReportSummary, EnvironmentalHistory } from '../types';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const Reports: React.FC = () => {
  const { selectedRoom } = useOutletContext<LayoutContextType>();
  const [reportType, setReportType] = useState('daily');
  const [isLoading, setIsLoading] = useState<{[key: string]: boolean}>({
    excel: false,
    csv: false,
    pdf: false
  });

  // Local state for statistics and chart data
  const defaultStats: ReportSummary = {
    avgTemp: 22.0, maxTemp: 22.0, minTemp: 22.0,
    avgHum: 45.0, maxHum: 45.0, minHum: 45.0,
    totalCaptures: 0,
    alertSummary: { total: 0, warnings: 0, criticals: 0 }
  };
  const [stats, setStats] = useState<ReportSummary>(defaultStats);
  const [history, setHistory] = useState<EnvironmentalHistory[]>([]);

  // Reload when room changes
  useEffect(() => {
    const loadReportsData = async () => {
      try {
        const [loadedStats, loadedHistory] = await Promise.all([
          reportService.getAggregates(selectedRoom.id),
          environmentService.getHistory(selectedRoom.id).then(res => res.data)
        ]);
        setStats(loadedStats);
        setHistory(loadedHistory);
      } catch (err) {
        console.error('Failed to load reports statistics data:', err);
      }
    };
    loadReportsData();
  }, [selectedRoom.id, reportType]);

  // Subscribe to live updates in background to recalculate statistics in real-time!
  useEffect(() => {
    const handleUpdate = async () => {
      try {
        const [loadedStats, loadedHistory] = await Promise.all([
          reportService.getAggregates(selectedRoom.id),
          environmentService.getHistory(selectedRoom.id).then(res => res.data)
        ]);
        setStats(loadedStats);
        setHistory(loadedHistory);
      } catch (err) {
        console.error('Failed to update stats in reports subscription:', err);
      }
    };

    const unsubscribe = environmentService.subscribeToHistory(() => {
      handleUpdate();
    });
    return () => unsubscribe();
  }, [selectedRoom.id]);

  const handleDownload = async (format: 'csv' | 'excel' | 'pdf') => {
    setIsLoading(prev => ({ ...prev, [format]: true }));
    try {
      await reportService.downloadReport(selectedRoom.id, selectedRoom.name, reportType, format);
    } finally {
      setIsLoading(prev => ({ ...prev, [format]: false }));
    }
  };

  // Format Recharts data (past 18 history points)
  const chartData = [...history].reverse().slice(-18).map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    Temp: h.temperature,
    Hum: h.humidity
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>REPORT INTERVAL</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {['daily', 'weekly', 'monthly'].map(type => (
            <button
              key={type}
              className={`btn ${reportType === type ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setReportType(type)}
              style={{ padding: '6px 14px', fontSize: '0.8rem', textTransform: 'capitalize' }}
            >
              {type} Report
            </button>
          ))}
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 20
      }}>
        {/* Temperature Stats */}
        <div className="glass-panel" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-warning)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Temperature Range
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, textAlign: 'center' }}>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 700 }}>{stats.minTemp}°C</p>
              <p style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Min</p>
            </div>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-warning)' }}>{stats.maxTemp}°C</p>
              <p style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Max</p>
            </div>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 700 }}>{stats.avgTemp}°C</p>
              <p style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Avg</p>
            </div>
          </div>
        </div>

        {/* Humidity Stats */}
        <div className="glass-panel" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-primary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Humidity Range
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, textAlign: 'center' }}>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 700 }}>{stats.minHum}%</p>
              <p style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Min</p>
            </div>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-primary)' }}>{stats.maxHum}%</p>
              <p style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Max</p>
            </div>
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 700 }}>{stats.avgHum}%</p>
              <p style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Avg</p>
            </div>
          </div>
        </div>

        {/* Total captures */}
        <div className="glass-panel" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ padding: 10, borderRadius: 8, background: 'rgba(37,99,235,0.1)', color: 'var(--color-primary)' }}>
            <Award size={24} />
          </div>
          <div>
            <h4 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{stats.totalCaptures}</h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Total Frames Captured</p>
          </div>
        </div>

        {/* Alarms Triggered */}
        <div className="glass-panel" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ padding: 10, borderRadius: 8, background: 'rgba(239,68,68,0.1)', color: 'var(--color-critical)' }}>
            <AlertOctagon size={24} />
          </div>
          <div>
            <h4 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{stats.alertSummary.total}</h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Alarms Dispatched</p>
          </div>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: 24 }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16 }}>Download Compliance Documentation</h3>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <button 
            className="btn btn-secondary" 
            onClick={() => handleDownload('excel')}
            disabled={isLoading.excel}
            style={{ minWidth: 160 }}
          >
            {isLoading.excel ? <Loader2 size={16} className="spin" /> : <FileSpreadsheet size={16} color="var(--color-success)" />}
            <span>{isLoading.excel ? 'Compiling Excel...' : 'Download Excel'}</span>
          </button>

          <button 
            className="btn btn-secondary" 
            onClick={() => handleDownload('csv')}
            disabled={isLoading.csv}
            style={{ minWidth: 160 }}
          >
            {isLoading.csv ? <Loader2 size={16} className="spin" /> : <FileText size={16} color="var(--color-primary)" />}
            <span>{isLoading.csv ? 'Compiling CSV...' : 'Download CSV'}</span>
          </button>

          <button 
            className="btn btn-secondary" 
            onClick={() => handleDownload('pdf')}
            disabled={isLoading.pdf}
            style={{ minWidth: 160 }}
          >
            {isLoading.pdf ? <Loader2 size={16} className="spin" /> : <FileText size={16} color="var(--color-critical)" />}
            <span>{isLoading.pdf ? 'Rendering PDF...' : 'Download PDF Audit'}</span>
          </button>
        </div>
      </div>

      <div className="chart-grid">
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 20 }}>Temperature Distribution Range</h3>
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--bg-card-solid)', borderColor: 'var(--border-color)', borderRadius: 8, fontSize: 11 }} 
                />
                <Bar dataKey="Temp" fill="var(--color-warning)" radius={[4, 4, 0, 0]} name="Temperature (°C)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: 24 }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 20 }}>Humidity Distribution Range</h3>
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--bg-card-solid)', borderColor: 'var(--border-color)', borderRadius: 8, fontSize: 11 }} 
                />
                <Area type="monotone" dataKey="Hum" stroke="var(--color-primary)" fill="var(--color-primary-glow)" strokeWidth={2} name="Humidity (%RH)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

    </div>
  );
};
export default Reports;
export { BarChart, Bar };
