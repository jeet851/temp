import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { 
  Bell, 
  Server, 
  AlertTriangle,
  CheckCircle,
  Clock
} from 'lucide-react';
import type { Room, Alert } from '../types';
import { motion, AnimatePresence } from 'framer-motion';

interface NavbarProps {
  selectedRoom: Room;
  activeAlerts: Alert[];
  onAcknowledgeAlert: (alertId: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ 
  selectedRoom, 
  activeAlerts,
  onAcknowledgeAlert
}) => {
  const location = useLocation();
  const [showNotifications, setShowNotifications] = useState(false);

  const getPageTitle = () => {
    const path = location.pathname.substring(1);
    if (!path) return 'Login';
    if (path === 'live') return 'Live Video Monitor';
    if (path === 'logs') return 'Environmental History';
    return path.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  const systemStatus = activeAlerts.some(a => a.severity === 'critical') 
    ? 'critical' 
    : activeAlerts.some(a => a.severity === 'warning') 
      ? 'warning' 
      : 'normal';

  const statusLabel = systemStatus === 'critical' 
    ? 'CRITICAL ALERT' 
    : systemStatus === 'warning' 
      ? 'WARNING STATE' 
      : 'SYSTEM SECURE';

  const statusColorClass = systemStatus === 'critical'
    ? 'critical'
    : systemStatus === 'warning'
      ? 'warning'
      : 'normal';

  return (
    <header style={{
      height: 'var(--navbar-height)',
      background: 'var(--bg-navbar)',
      backdropFilter: 'blur(10px)',
      borderBottom: '1px solid var(--border-color)',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: 0,
      zIndex: 80,
      width: '100%'
    }}>
      {/* Title Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{getPageTitle()}</span>
          </h1>
        </div>
      </div>

      {/* Utility Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        
        {/* System Health Status Badge */}
        <div 
          className={`status-badge ${statusColorClass}`}
          style={{
            fontSize: '0.75rem',
            padding: '6px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 6
          }}
        >
          <span className={`status-indicator pulse ${statusColorClass}`} />
          <span>{statusLabel}</span>
        </div>

        {/* Room Context Indicator */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 8, 
          padding: '6px 12px',
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--border-radius-md)',
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--color-text-main)'
        }}>
          <Server size={14} color="var(--color-primary)" />
          <span>{selectedRoom.name}</span>
        </div>

        {/* Notifications Icon & Drawer */}
        <div style={{ position: 'relative' }}>
          <button 
            className="icon-button"
            onClick={() => setShowNotifications(!showNotifications)}
            style={{ 
              position: 'relative',
              background: showNotifications ? 'rgba(255,255,255,0.05)' : 'transparent',
              padding: 8,
              borderRadius: '50%'
            }}
          >
            <Bell size={20} />
            {activeAlerts.length > 0 && (
              <span style={{
                position: 'absolute',
                top: 2,
                right: 2,
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: 'var(--color-critical)',
                boxShadow: '0 0 6px var(--color-critical)'
              }} />
            )}
          </button>

          <AnimatePresence>
            {showNotifications && (
              <>
                <div 
                  style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 98 }} 
                  onClick={() => setShowNotifications(false)} 
                />
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="glass-panel"
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: '120%',
                    width: 320,
                    zIndex: 99,
                    backgroundColor: 'var(--bg-card-solid)',
                    padding: 0,
                    overflow: 'hidden'
                  }}
                >
                  <div style={{ 
                    padding: '16px', 
                    borderBottom: '1px solid var(--border-color)', 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center' 
                  }}>
                    <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Active System Alerts</span>
                    <span className="status-badge critical" style={{ fontSize: '0.65rem' }}>
                      {activeAlerts.length} Active
                    </span>
                  </div>

                  <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                    {activeAlerts.length === 0 ? (
                      <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--color-text-dark)' }}>
                        <CheckCircle size={24} style={{ margin: '0 auto 8px', display: 'block', color: 'var(--color-success)' }} />
                        <span style={{ fontSize: '0.85rem' }}>All thresholds within limits</span>
                      </div>
                    ) : (
                      activeAlerts.map(alert => (
                        <div 
                          key={alert.id}
                          style={{
                            padding: '12px 16px',
                            borderBottom: '1px solid var(--border-color)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 6
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ 
                              color: alert.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)',
                              fontSize: '0.8rem',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4
                            }}>
                              <AlertTriangle size={12} />
                              {alert.type.toUpperCase()} LIMIT
                            </span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--color-text-dark)', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <Clock size={10} />
                              {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                            Value: <strong style={{ color: 'var(--color-text-main)' }}>{alert.value}{alert.type === 'temperature' ? '°C' : '%RH'}</strong> (Threshold: {alert.threshold}{alert.type === 'temperature' ? '°C' : '%RH'})
                          </p>
                          <button
                            onClick={() => onAcknowledgeAlert(alert.id)}
                            style={{
                              alignSelf: 'flex-end',
                              background: 'rgba(255, 255, 255, 0.05)',
                              border: '1px solid var(--border-color)',
                              borderRadius: '4px',
                              padding: '2px 8px',
                              fontSize: '0.7rem',
                              color: 'var(--color-text-main)',
                              cursor: 'pointer',
                              fontWeight: 600,
                            }}
                            className="ack-button"
                          >
                            Acknowledge
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
};
