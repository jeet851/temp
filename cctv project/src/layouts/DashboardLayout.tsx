import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Navbar } from '../components/Navbar';
import { environmentService } from '../services/environmentService';
import { alertService } from '../services/alertService';
import { cameraService } from '../services/cameraService';
import { settingsService } from '../services/settingsService';
import type { Room, Camera, Alert, Threshold, LayoutContextType } from '../types';
import { AlertTriangle, X } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { authService } from '../services/authService';
import { wsManager } from '../services/wsManager';
import { USE_MOCK } from '../config';



interface Toast {
  id: string;
  alert: Alert;
  roomName: string;
}

export const DashboardLayout: React.FC = () => {
  // Root layout states
  const defaultRoom: Room = { id: 'room-001', name: 'Server Room Alpha', location: 'Building A, Floor 2, Zone C', status: 'normal' };
  const [rooms, setRooms] = useState<Room[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [thresholds, setThresholds] = useState<Threshold>({ tempWarning: 28, tempCritical: 32, humWarning: 65, humCritical: 75 });
  const [selectedRoom, setSelectedRoom] = useState<Room>(defaultRoom);
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Load initial data asynchronously and initialize WebSocket connection if using real backend
  useEffect(() => {
    if (!USE_MOCK) {
      wsManager.connect();
    }

    const loadData = async () => {
      try {
        const loadedRooms = await environmentService.getRooms();
        setRooms(loadedRooms);
        const current = loadedRooms.find(r => r.id === selectedRoom.id);
        if (current) {
          setSelectedRoom(current);
        } else if (loadedRooms.length > 0) {
          setSelectedRoom(loadedRooms[0]);
        }

        const loadedCameras = await cameraService.getCameras();
        setCameras(loadedCameras);

        const loadedAlerts = await alertService.getAlerts();
        setAlerts(loadedAlerts);

        const loadedThresholds = await settingsService.getThresholds();
        setThresholds(loadedThresholds);
      } catch (err) {
        console.error('Failed to load initial layout dashboard settings:', err);
      }
    };

    loadData();

    return () => {
      if (!USE_MOCK) {
        wsManager.disconnect();
      }
    };
  }, []);

  // Services listeners
  useEffect(() => {
    // Listen to rooms health updates
    const unsubscribeRooms = environmentService.subscribeToRooms((updatedRooms) => {
      setRooms(updatedRooms);
      // Sync selectedRoom reference
      const current = updatedRooms.find(r => r.id === selectedRoom.id);
      if (current) {
        setSelectedRoom(current);
      }
    });

    // Listen to central alerts logs changes (for active indicators counts)
    const unsubscribeAlerts = alertService.subscribeToAlerts((updatedAlerts) => {
      setAlerts(updatedAlerts);
    });

    // Listen to settings thresholds changes
    const unsubscribeThresholds = settingsService.subscribeToThresholds((updatedThresholds) => {
      setThresholds(updatedThresholds);
    });

    // Listen to new alert dispatches to spawn floating toasts
    const unsubscribeDispatch = alertService.subscribeToAlertDispatch(({ alert, roomName }) => {
      const toastId = `toast-${Date.now()}`;
      setToasts(prev => [...prev, { id: toastId, alert, roomName }]);
      
      // Auto clear after 5s
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== toastId));
      }, 5000);
    });

    return () => {
      unsubscribeRooms();
      unsubscribeAlerts();
      unsubscribeThresholds();
      unsubscribeDispatch();
    };
  }, [selectedRoom.id]);

  // Alert acknowledgements callback
  const handleAcknowledgeAlert = (alertId: string) => {
    alertService.acknowledgeAlert(alertId, 'sysadmin@visionguard.net');
  };

  const handleLogout = () => {
    authService.logout();
  };

  const activeAlertCount = alerts.filter(a => a.status === 'active').length;
  const activeRoomAlerts = alerts.filter(a => a.status === 'active');

  const contextValue: LayoutContextType = {
    selectedRoom,
    setSelectedRoom,
    rooms,
    cameras,
    thresholds,
    setThresholds: (t: Threshold) => {
      settingsService.saveThresholds(t);
      setThresholds(t);
    }
  };

  return (
    <div className="app-container">
      {/* Navigation Sidebar */}
      <Sidebar 
        onLogout={handleLogout}
        activeAlertCount={activeAlertCount}
      />

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        width: 'calc(100% - var(--sidebar-width))',
        minHeight: '100vh'
      }}>
        <Navbar 
          selectedRoom={selectedRoom}
          activeAlerts={activeRoomAlerts}
          onAcknowledgeAlert={handleAcknowledgeAlert}
        />

        {/* Content Outlet Frame */}
        <main className="main-content">
          <Outlet context={contextValue} />
        </main>
      </div>

      {/* Floating Notifications Toasts Panel */}
      <div style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        maxWidth: 340,
        width: '100%'
      }}>
        <AnimatePresence>
          {toasts.map(toast => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="glass-panel"
              style={{
                padding: 16,
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: toast.alert.severity === 'critical' ? 'rgba(239, 68, 68, 0.5)' : 'rgba(245, 158, 11, 0.5)',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12
              }}
            >
              <div style={{ 
                color: toast.alert.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)',
                padding: 4,
                borderRadius: 4,
                background: toast.alert.severity === 'critical' ? 'var(--color-critical-glow)' : 'var(--color-warning-glow)'
              }}>
                <AlertTriangle size={18} />
              </div>
              <div style={{ flexGrow: 1, fontSize: '0.8rem' }}>
                <div style={{ fontWeight: 700, color: toast.alert.severity === 'critical' ? 'var(--color-critical)' : 'var(--color-warning)' }}>
                  {toast.alert.severity.toUpperCase()} ALERT ACTIVE
                </div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, margin: '2px 0 6px' }}>
                  {toast.roomName}
                </div>
                <p style={{ color: 'var(--color-text-muted)' }}>
                  OCR extracted {toast.alert.type}: <strong style={{ color: 'var(--color-text-main)' }}>{toast.alert.value}</strong>
                </p>
              </div>
              <button 
                onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-text-dark)',
                  cursor: 'pointer',
                  padding: 2
                }}
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

    </div>
  );
};
