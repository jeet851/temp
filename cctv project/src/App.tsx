import React, { useState, useEffect } from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { DashboardLayout } from './layouts/DashboardLayout';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { LiveMonitor } from './pages/LiveMonitor';
import { Logs } from './pages/Logs';
import { Alerts } from './pages/Alerts';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';
import { authService } from './services/authService';

export const App: React.FC = () => {
  // Session authentication state (Operator authorization check)
  const [isAuthenticated, setIsAuthenticated] = useState(authService.isAuthenticated());

  useEffect(() => {
    const handleLogoutEvent = () => {
      setIsAuthenticated(false);
    };
    window.addEventListener('vg_logout', handleLogoutEvent);
    return () => {
      window.removeEventListener('vg_logout', handleLogoutEvent);
    };
  }, []);

  return (
    <Router>
      <Routes>
        {/* Public Entrance Portal */}
        <Route 
          path="/login" 
          element={
            !isAuthenticated ? (
              <Login onLogin={() => setIsAuthenticated(true)} />
            ) : (
              <Navigate to="/dashboard" replace />
            )
          } 
        />

        {/* Unified Enterprise Dashboard layouts (Protected Routes) */}
        <Route element={isAuthenticated ? <DashboardLayout /> : <Navigate to="/login" replace />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/live" element={<LiveMonitor />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
        </Route>

        {/* Standard route redirections fallback */}
        <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </Router>
  );
};

export default App;
