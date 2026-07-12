import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Tv, 
  Database, 
  AlertTriangle, 
  FileSpreadsheet, 
  Settings, 
  LogOut,
  Shield
} from 'lucide-react';
interface SidebarProps {
  isOpen?: boolean;
  setIsOpen?: (isOpen: boolean) => void;
  onLogout: () => void;
  activeAlertCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({ onLogout, activeAlertCount }) => {
  const navigate = useNavigate();

  const menuItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Live Monitor', path: '/live', icon: Tv },
    { name: 'Environmental Logs', path: '/logs', icon: Database },
    { 
      name: 'Alerts', 
      path: '/alerts', 
      icon: AlertTriangle,
      badge: activeAlertCount > 0 ? activeAlertCount : undefined,
      badgeColor: 'var(--color-critical)'
    },
    { name: 'Reports', path: '/reports', icon: FileSpreadsheet },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  const handleLogoutClick = () => {
    onLogout();
    navigate('/login');
  };

  return (
    <aside
      className="glass-panel"
      style={{
        position: 'fixed',
        top: 0,
        bottom: 0,
        left: 0,
        zIndex: 100,
        width: 'var(--sidebar-width)',
        backgroundColor: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-color)',
        borderRadius: 0,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '24px 16px',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
        {/* Logo / Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingLeft: 8 }}>
          <div style={{ 
            background: 'linear-gradient(135deg, var(--color-primary), #3b82f6)',
            borderRadius: '8px', 
            padding: '8px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)'
          }}>
            <Shield size={20} color="#fff" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(to right, #fff, #94a3b8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>VisionGuard</h2>
            <span style={{ fontSize: '0.65rem', color: 'var(--color-primary)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>Environmental EMS</span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {menuItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: 'var(--border-radius-md)',
                color: isActive ? 'var(--color-text-main)' : 'var(--color-text-muted)',
                textDecoration: 'none',
                fontSize: '0.95rem',
                fontWeight: isActive ? 600 : 500,
                backgroundColor: isActive ? 'rgba(37, 99, 235, 0.15)' : 'transparent',
                borderLeft: isActive ? '3px solid var(--color-primary)' : '3px solid transparent',
                transition: 'all 0.2s ease',
                cursor: 'pointer'
              })}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <item.icon size={18} />
                <span>{item.name}</span>
              </div>
              {item.badge !== undefined && (
                <span style={{
                  backgroundColor: item.badgeColor || 'var(--color-primary)',
                  color: 'white',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  boxShadow: '0 0 10px rgba(239, 68, 68, 0.4)'
                }}>
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* User Footer / Logout */}
      <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, paddingLeft: 8 }}>
          <div style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: 'var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: '0.9rem',
            color: 'var(--color-primary)',
            border: '1px solid var(--color-primary)'
          }}>
            OP
          </div>
          <div>
            <p style={{ fontSize: '0.85rem', fontWeight: 600 }}>Operator-01</p>
            <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>sysadmin@visionguard.net</p>
          </div>
        </div>

        <button 
          onClick={handleLogoutClick}
          className="btn btn-secondary" 
          style={{ 
            width: '100%', 
            justifyContent: 'flex-start',
            padding: '10px 14px',
            backgroundColor: 'rgba(239, 68, 68, 0.05)',
            borderColor: 'rgba(239, 68, 68, 0.1)',
            color: 'var(--color-critical)'
          }}
        >
          <LogOut size={16} />
          <span>Logout System</span>
        </button>
      </div>
    </aside>
  );
};
