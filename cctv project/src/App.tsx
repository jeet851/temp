import React, { useState, useEffect, lazy, Suspense } from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { DashboardLayout } from './layouts/DashboardLayout';
import { authService } from './services/authService';

// Lazy load route components for code splitting & fast initial page loads
const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const LiveMonitor = lazy(() => import('./pages/LiveMonitor'));
const Logs = lazy(() => import('./pages/Logs'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Reports = lazy(() => import('./pages/Reports'));
const Settings = lazy(() => import('./pages/Settings'));


const PageLoader: React.FC = () => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '60vh',
    gap: '16px',
    color: '#38bdf8',
    fontFamily: 'monospace'
  }}>
    <div style={{
      width: '32px',
      height: '32px',
      border: '3px solid rgba(56, 189, 248, 0.2)',
      borderTopColor: '#38bdf8',
      borderRadius: '50%',
      animation: 'spin 0.8s linear infinite'
    }} />
    <span style={{ fontSize: '0.85rem', letterSpacing: '0.05em' }}>Loading module...</span>
  </div>
);

export const App: React.FC = () => {
  // Session authentication state (Operator authorization check)
  const [isAuthenticated, setIsAuthenticated] = useState(authService.isAuthenticated());

  useEffect(() => {
    const handleLogoutEvent = () => {
      setIsAuthenticated(false);
    };
    window.addEventListener('vg_logout', handleLogoutEvent);

    // Eagerly prefetch all route chunks in background so clicking sidebar links is 100% instant
    if (isAuthenticated) {
      const prefetchRoutes = () => {
        import('./pages/Dashboard');
        import('./pages/LiveMonitor');
        import('./pages/Logs');
        import('./pages/Alerts');
        import('./pages/Reports');
        import('./pages/Settings');
      };
      if ('requestIdleCallback' in window) {
        (window as any).requestIdleCallback(prefetchRoutes);
      } else {
        setTimeout(prefetchRoutes, 150);
      }
    }

    return () => {
      window.removeEventListener('vg_logout', handleLogoutEvent);
    };
  }, [isAuthenticated]);


  return (
    <Router>
      <Routes>
        {/* Public Entrance Portal */}
        <Route 
          path="/login" 
          element={
            !isAuthenticated ? (
              <Suspense fallback={<PageLoader />}>
                <Login onLogin={() => setIsAuthenticated(true)} />
              </Suspense>
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

        {/* Root path redirection */}
        <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />

        {/* Standard route redirections fallback */}
        <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </Router>
  );

};

export default App;

