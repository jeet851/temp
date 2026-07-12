import React, { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { 
  Camera, 
  AlertTriangle, 
  Bell, 
  Database, 
  Save, 
  Sliders
} from 'lucide-react';
import type { LayoutContextType } from '../types';

export const Settings: React.FC = () => {
  const { selectedRoom, cameras, thresholds, setThresholds } = useOutletContext<LayoutContextType>();
  
  const [activeTab, setActiveTab] = useState<'general' | 'camera' | 'thresholds' | 'notifications' | 'database'>('general');
  
  // Settings Form States
  const [roomName, setRoomName] = useState(selectedRoom.name);
  const [roomLocation, setRoomLocation] = useState(selectedRoom.location);
  const [timezone, setTimezone] = useState('GMT+05:30 (India Standard Time)');
  
  const activeCamera = cameras.find(c => c.roomId === selectedRoom.id) || cameras[0];
  const [cameraName, setCameraName] = useState(activeCamera?.name || '');
  const [rtspUrl, setRtspUrl] = useState(activeCamera?.rtspUrl || '');
  const [ocrInterval, setOcrInterval] = useState(5); // seconds
  
  const [tempWarn, setTempWarn] = useState(thresholds.tempWarning);
  const [tempCrit, setTempCrit] = useState(thresholds.tempCritical);
  const [humWarn, setHumWarn] = useState(thresholds.humWarning);
  const [humCrit, setHumCrit] = useState(thresholds.humCritical);

  const [emailAlerts, setEmailAlerts] = useState('sysops-alerts@visionguard.net');
  const [telegramToken, setTelegramToken] = useState('578912443:AAHk-9gR312pA...');
  const [telegramChatId, setTelegramChatId] = useState('-100154291884');
  const [notifyOnWarning, setNotifyOnWarning] = useState(true);
  const [notifyOnCritical, setNotifyOnCritical] = useState(true);

  const [retentionDays, setRetentionDays] = useState(90);
  const [dbHost, setDbHost] = useState('10.240.10.12');
  const [dbPort, setDbPort] = useState(5432);

  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Commit thresholds back to Central State (propagates settingsService)
    setThresholds({
      tempWarning: Number(tempWarn),
      tempCritical: Number(tempCrit),
      humWarning: Number(humWarn),
      humCritical: Number(humCrit)
    });

    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  const navItems = [
    { id: 'general', label: 'General Configuration', icon: Sliders },
    { id: 'camera', label: 'RTSP Camera Gateway', icon: Camera },
    { id: 'thresholds', label: 'Alarm Thresholds', icon: AlertTriangle },
    { id: 'notifications', label: 'Notification Hooks', icon: Bell },
    { id: 'database', label: 'Backup & Database', icon: Database },
  ];

  return (
    <div className="two-col-layout" style={{ gridTemplateColumns: '1fr 3fr' }}>
      
      {/* Settings Navigation Tabs */}
      <div className="glass-panel" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 6, height: 'fit-content' }}>
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id as any)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 14px',
              border: 'none',
              borderRadius: 'var(--border-radius-md)',
              textAlign: 'left',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: activeTab === item.id ? 600 : 500,
              backgroundColor: activeTab === item.id ? 'rgba(37,99,235,0.15)' : 'transparent',
              color: activeTab === item.id ? 'var(--color-text-main)' : 'var(--color-text-muted)',
              transition: 'all 0.15s ease'
            }}
          >
            <item.icon size={16} color={activeTab === item.id ? 'var(--color-primary)' : 'var(--color-text-dark)'} />
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      {/* Settings Body Form */}
      <div className="glass-panel" style={{ padding: 24 }}>
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          
          {saveSuccess && (
            <div style={{
              backgroundColor: 'var(--color-success-glow)',
              border: '1px solid rgba(34, 197, 94, 0.3)',
              color: 'var(--color-success)',
              padding: '10px 14px',
              borderRadius: 'var(--border-radius-sm)',
              fontSize: '0.8rem',
              fontWeight: 600
            }}>
              Compliance settings updated successfully. Alarm parameters re-synced.
            </div>
          )}

          {/* TAB 1: GENERAL */}
          {activeTab === 'general' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 4 }}>General Site Specifications</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Identify monitor room zones and local timestamp systems.</p>
              </div>

              <div className="form-group">
                <label className="form-label">Zone Room Name</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Physical Location Details</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={roomLocation}
                  onChange={(e) => setRoomLocation(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Local Zone Timezone</label>
                <select 
                  className="form-input form-select"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                >
                  <option>GMT+05:30 (India Standard Time)</option>
                  <option>GMT-05:00 (Eastern Standard Time)</option>
                  <option>GMT+00:00 (Coordinated Universal Time)</option>
                </select>
              </div>
            </div>
          )}

          {/* TAB 2: CAMERA GATEWAY */}
          {activeTab === 'camera' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 4 }}>RTSP Stream Gateway Configuration</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Set RTSP source addresses and trigger OCR crop scan loops.</p>
              </div>

              <div className="form-group">
                <label className="form-label">Linked CCTV Camera Reference</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={cameraName}
                  onChange={(e) => setCameraName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">RTSP Network Address URL</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">OCR Frame Capture Interval (seconds)</label>
                <input 
                  type="number" 
                  className="form-input" 
                  value={ocrInterval}
                  onChange={(e) => setOcrInterval(Number(e.target.value))}
                  min={2}
                  max={60}
                />
              </div>
            </div>
          )}

          {/* TAB 3: THRESHOLDS */}
          {activeTab === 'thresholds' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 4 }}>Alarm & Critical Boundaries</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Define parameters to dispatch warning indicators and trigger system alerts.</p>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 16
              }}>
                <div className="form-group">
                  <label className="form-label">Temperature Warning Threshold (°C)</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    value={tempWarn}
                    onChange={(e) => setTempWarn(Number(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Temperature Critical Threshold (°C)</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    value={tempCrit}
                    onChange={(e) => setTempCrit(Number(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Humidity Warning Threshold (%RH)</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    value={humWarn}
                    onChange={(e) => setHumWarn(Number(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Humidity Critical Threshold (%RH)</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    value={humCrit}
                    onChange={(e) => setHumCrit(Number(e.target.value))}
                  />
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: NOTIFICATIONS */}
          {activeTab === 'notifications' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 4 }}>Alert Relay Notification Hooks</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Forward events directly to administrator channels.</p>
              </div>

              <div className="form-group">
                <label className="form-label">SMTP Forward Address</label>
                <input 
                  type="email" 
                  className="form-input" 
                  value={emailAlerts}
                  onChange={(e) => setEmailAlerts(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Telegram Bot Token Credentials</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={telegramToken}
                  onChange={(e) => setTelegramToken(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Telegram Chat ID Destination</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={telegramChatId}
                  onChange={(e) => setTelegramChatId(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 14 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    checked={notifyOnWarning} 
                    onChange={() => setNotifyOnWarning(!notifyOnWarning)}
                    style={{ accentColor: 'var(--color-primary)' }} 
                  />
                  <span>Dispatch hooks on Warning levels</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    checked={notifyOnCritical} 
                    onChange={() => setNotifyOnCritical(!notifyOnCritical)}
                    style={{ accentColor: 'var(--color-primary)' }} 
                  />
                  <span>Dispatch hooks on Critical thresholds (High Priority)</span>
                </label>
              </div>
            </div>
          )}

          {/* TAB 5: DATABASE */}
          {activeTab === 'database' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 4 }}>PostgreSQL Storage & Backups</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Configure host coordinates and log data cleanup periods.</p>
              </div>

              <div className="form-group">
                <label className="form-label">Record Retention Interval (Days)</label>
                <input 
                  type="number" 
                  className="form-input" 
                  value={retentionDays}
                  onChange={(e) => setRetentionDays(Number(e.target.value))}
                />
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: '3fr 1fr',
                gap: 16
              }}>
                <div className="form-group">
                  <label className="form-label">Database Host IP Address</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={dbHost}
                    onChange={(e) => setDbHost(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Port</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    value={dbPort}
                    onChange={(e) => setDbPort(Number(e.target.value))}
                  />
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: 16 }}>
            <button type="submit" className="btn btn-primary" style={{ padding: '10px 24px' }}>
              <Save size={16} />
              <span>Commit System Config</span>
            </button>
          </div>

        </form>
      </div>

    </div>
  );
};
export default Settings;
