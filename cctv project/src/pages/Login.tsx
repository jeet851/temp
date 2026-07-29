import React, { useState } from 'react';
import { Shield, Eye, EyeOff, Lock, Mail, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { authService } from '../services/authService';

interface LoginProps {
  onLogin: () => void;
}

export const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [email, setEmail] = useState('sysadmin@visionguard.net');
  const [password, setPassword] = useState('••••••••••••');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email || !password) {
      setError('Please fill in all security fields.');
      return;
    }

    setIsLoading(true);

    try {
      const cleanPassword = password === '••••••••••••' ? 'VisionGuard2026!' : password;
      await authService.login(email, cleanPassword);
      setIsLoading(false);
      onLogin();
    } catch (err: any) {
      setIsLoading(false);
      setError(err.message || 'Authentication handshake failed.');
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      width: '100%',
      backgroundColor: 'var(--bg-primary)',
      backgroundImage: `radial-gradient(circle at 50% 50%, rgba(37, 99, 235, 0.12), transparent 50%)`,
      padding: 16
    }}>
      {/* Decorative grid pattern in background */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundImage: `radial-gradient(rgba(255,255,255,0.015) 1px, transparent 0)`,
        backgroundSize: '24px 24px',
        pointerEvents: 'none',
        zIndex: 0
      }} />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: 420,
          padding: '40px 32px',
          zIndex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 28,
          borderColor: 'rgba(255, 255, 255, 0.06)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)'
        }}
      >
        {/* Brand Logo Header */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center' }}>
          <div style={{
            background: 'linear-gradient(135deg, var(--color-primary), #1d4ed8)',
            padding: 14,
            borderRadius: '12px',
            boxShadow: '0 8px 24px rgba(37, 99, 235, 0.3)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Shield size={32} color="#fff" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>VisionGuard</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
              Enterprise AI Environmental Monitoring Portal
            </p>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {error && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                backgroundColor: 'var(--color-critical-glow)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                padding: '10px 14px',
                borderRadius: 'var(--border-radius-sm)',
                color: 'var(--color-critical)',
                fontSize: '0.8rem',
                fontWeight: 600
              }}
            >
              {error}
            </motion.div>
          )}

          {/* Email field */}
          <div className="form-group">
            <label className="form-label" htmlFor="email-input">Security Email</label>
            <div style={{ position: 'relative' }}>
              <Mail 
                size={16} 
                color="var(--color-text-dark)" 
                style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)' }} 
              />
              <input
                id="email-input"
                type="email"
                className="form-input"
                placeholder="sysadmin@visionguard.net"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ width: '100%', paddingLeft: 42 }}
                disabled={isLoading}
              />
            </div>
          </div>

          {/* Password field */}
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label className="form-label" htmlFor="password-input">Portal Token / Password</label>
              <a href="#forgot" style={{ fontSize: '0.75rem', color: 'var(--color-primary)', textDecoration: 'none', fontWeight: 600 }}>
                Reset Access?
              </a>
            </div>
            <div style={{ position: 'relative' }}>
              <Lock 
                size={16} 
                color="var(--color-text-dark)" 
                style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)' }} 
              />
              <input
                id="password-input"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ width: '100%', paddingLeft: 42, paddingRight: 40 }}
                disabled={isLoading}
              />
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowPassword(!showPassword)}
                style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', padding: 4 }}
                disabled={isLoading}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Remember Me */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              id="remember-me"
              style={{
                accentColor: 'var(--color-primary)',
                width: 16,
                height: 16,
                borderRadius: 4,
                cursor: 'pointer'
              }}
              defaultChecked
            />
            <label 
              htmlFor="remember-me" 
              style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', cursor: 'pointer', userSelect: 'none' }}
            >
              Authorize workstation for 30 days
            </label>
          </div>

          {/* Action Trigger */}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isLoading}
            style={{ width: '100%', height: 44, fontSize: '0.95rem', position: 'relative', overflow: 'hidden' }}
          >
            {isLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Loader2 size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                <span>Authenticating Handshake...</span>
              </span>
            ) : (
              <span>Establish Secure Session</span>
            )}
          </button>
        </form>

        {/* Style block for spin animations */}
        <style dangerouslySetInnerHTML={{__html: `
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          .spin {
            animation: spin 1s linear infinite;
          }
        `}} />

        {/* Portal footer */}
        <div style={{ textAlign: 'center', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: 16 }}>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-dark)' }}>
            VisionGuard Enterprise Compliance v2.4.0-Build7<br />
            IP Sec Audit Active: 127.0.0.1
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;

