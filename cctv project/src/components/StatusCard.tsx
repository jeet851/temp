import React from 'react';
import { type LucideIcon, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { motion } from 'framer-motion';

interface StatusCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  status: 'normal' | 'warning' | 'critical' | 'info';
  trend?: {
    value: string | number;
    direction: 'up' | 'down' | 'neutral';
  };
  description?: string;
  pulse?: boolean;
}

export const StatusCard: React.FC<StatusCardProps> = ({
  title,
  value,
  icon: Icon,
  status,
  trend,
  description,
  pulse = false
}) => {
  const getStatusColors = () => {
    switch (status) {
      case 'critical':
        return {
          glow: 'var(--color-critical-glow)',
          border: 'rgba(239, 68, 68, 0.4)',
          text: 'var(--color-critical)'
        };
      case 'warning':
        return {
          glow: 'var(--color-warning-glow)',
          border: 'rgba(245, 158, 11, 0.4)',
          text: 'var(--color-warning)'
        };
      case 'normal':
        return {
          glow: 'var(--color-success-glow)',
          border: 'rgba(34, 197, 94, 0.3)',
          text: 'var(--color-success)'
        };
      case 'info':
      default:
        return {
          glow: 'var(--color-primary-glow)',
          border: 'rgba(37, 99, 235, 0.3)',
          text: 'var(--color-primary)'
        };
    }
  };

  const colors = getStatusColors();

  return (
    <motion.div
      className="glass-panel"
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      style={{
        padding: '20px',
        position: 'relative',
        overflow: 'hidden',
        border: `1px solid ${colors.border}`,
        boxShadow: `0 8px 32px 0 rgba(0, 0, 0, 0.2), inset 0 0 12px ${colors.glow}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 12
      }}
    >
      {/* Background glow node */}
      <div style={{
        position: 'absolute',
        top: -30,
        right: -30,
        width: 100,
        height: 100,
        borderRadius: '50%',
        background: colors.glow,
        filter: 'blur(20px)',
        zIndex: 0,
        pointerEvents: 'none'
      }} />

      {/* Card Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 1 }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {title}
        </span>
        <div style={{ 
          padding: '8px', 
          borderRadius: '8px', 
          backgroundColor: 'rgba(255,255,255,0.03)', 
          border: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: colors.text
        }}>
          <Icon size={18} />
        </div>
      </div>

      {/* Main KPI Value */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, zIndex: 1 }}>
        <h3 style={{ fontSize: '2rem', fontWeight: 800, fontFamily: 'var(--font-sans)', letterSpacing: '-0.03em' }}>
          {value}
        </h3>
        
        {pulse && (
          <span className={`status-indicator pulse ${status}`} style={{ alignSelf: 'center', marginLeft: 4 }} />
        )}
      </div>

      {/* Footer Trend & Meta */}
      {(trend || description) && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between', 
          borderTop: '1px solid rgba(255, 255, 255, 0.05)', 
          paddingTop: '10px',
          zIndex: 1,
          fontSize: '0.8rem',
          color: 'var(--color-text-muted)'
        }}>
          {trend && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {trend.direction === 'up' && (
                <span style={{ color: 'var(--color-critical)', display: 'flex', alignItems: 'center', fontWeight: 600 }}>
                  <ArrowUpRight size={14} />
                  {trend.value}
                </span>
              )}
              {trend.direction === 'down' && (
                <span style={{ color: 'var(--color-success)', display: 'flex', alignItems: 'center', fontWeight: 600 }}>
                  <ArrowDownRight size={14} />
                  {trend.value}
                </span>
              )}
              {trend.direction === 'neutral' && (
                <span style={{ color: 'var(--color-text-dark)', display: 'flex', alignItems: 'center', fontWeight: 600 }}>
                  <Minus size={14} />
                  {trend.value}
                </span>
              )}
            </div>
          )}

          {description && (
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dark)', fontWeight: 500 }}>
              {description}
            </span>
          )}
        </div>
      )}
    </motion.div>
  );
};
