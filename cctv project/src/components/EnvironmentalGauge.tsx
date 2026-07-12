import React from 'react';
import { motion } from 'framer-motion';

interface EnvironmentalGaugeProps {
  value: number;
  type: 'temperature' | 'humidity';
  title: string;
  status: 'normal' | 'warning' | 'critical';
  min: number;
  max: number;
  unit: string;
}

export const EnvironmentalGauge: React.FC<EnvironmentalGaugeProps> = ({
  value,
  type,
  title,
  status,
  min,
  max,
  unit
}) => {
  // SVG Circle calculations
  const radius = 64;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius; // ~402.12
  
  // Calculate percentage of value within limits
  const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  // Map value to dash offset (leave 25% of the circle empty at the bottom for aesthetic gauge arch)
  const angleScale = 0.75; // 270 degree arch
  const activeLength = circumference * angleScale;
  const strokeDashoffset = circumference - (percentage / 100) * activeLength;

  const getStatusColor = () => {
    if (status === 'critical') return 'var(--color-critical)';
    if (status === 'warning') return 'var(--color-warning)';
    return type === 'temperature' ? '#f59e0b' : 'var(--color-primary)';
  };

  const getGlowShadow = () => {
    if (status === 'critical') return 'rgba(239, 68, 68, 0.3)';
    if (status === 'warning') return 'rgba(245, 158, 11, 0.3)';
    return type === 'temperature' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(37, 99, 235, 0.2)';
  };

  const color = getStatusColor();
  const shadow = getGlowShadow();

  return (
    <motion.div
      className="glass-panel"
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      style={{
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        textAlign: 'center',
        position: 'relative',
        minHeight: 220
      }}
    >
      <span style={{ 
        fontSize: '0.8rem', 
        fontWeight: 700, 
        color: 'var(--color-text-muted)', 
        textTransform: 'uppercase', 
        letterSpacing: '0.05em' 
      }}>
        {title}
      </span>

      {/* Gauge SVG Container */}
      <div style={{ position: 'relative', width: 160, height: 160 }}>
        <svg 
          width="160" 
          height="160" 
          viewBox="0 0 160 160" 
          style={{ transform: 'rotate(135deg)', transformOrigin: '50% 50%' }}
        >
          {/* Gray Background Track */}
          <circle
            cx="80"
            cy="80"
            r={radius}
            fill="transparent"
            stroke="rgba(255,255,255,0.03)"
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={circumference - activeLength}
            strokeLinecap="round"
          />

          {/* Animated Value Arc Track */}
          <circle
            cx="80"
            cy="80"
            r={radius}
            fill="transparent"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{
              transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.3s ease',
              filter: `drop-shadow(0 0 6px ${shadow})`
            }}
          />
        </svg>

        {/* Floating Core Readout */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2
        }}>
          <h2 style={{ 
            fontSize: '1.85rem', 
            fontWeight: 800, 
            color: 'var(--color-text-main)', 
            letterSpacing: '-0.02em',
            fontFamily: 'var(--font-mono)'
          }}>
            {value.toFixed(1)}
          </h2>
          <span style={{ 
            fontSize: '0.8rem', 
            fontWeight: 700, 
            color: color, 
            textTransform: 'uppercase',
            letterSpacing: '0.05em'
          }}>
            {unit}
          </span>
        </div>
      </div>

      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-dark)', fontWeight: 600 }}>
        LIMITS: {min}{unit} - {max}{unit}
      </div>
    </motion.div>
  );
};
