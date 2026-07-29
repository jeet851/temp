import { apiClient } from './apiClient';
import { USE_MOCK } from '../config';

export interface UserProfile {
  id: string;
  fullName: string;
  username: string;
  email: string;
  role: string;
  status: string;
}

const MOCK_USER: UserProfile = {
  id: 'usr-001',
  fullName: 'System Administrator (Demo)',
  username: 'sysadmin',
  email: 'sysadmin@visionguard.net',
  role: 'admin',
  status: 'active',
};

export const authService = {
  async login(email: string, password: string): Promise<UserProfile> {
    if (USE_MOCK) {
      await new Promise(resolve => setTimeout(resolve, 800));
      if (email === 'sysadmin@visionguard.net' && password === 'VisionGuard2026!') {
        localStorage.setItem('vg_session_token', 'mock-token-visionguard-2026');
        localStorage.setItem('vg_user', JSON.stringify(MOCK_USER));
        return MOCK_USER;
      }
      throw new Error('Invalid credentials. Use sysadmin@visionguard.net / VisionGuard2026!');
    }

    const res = await apiClient.post<{ data: { accessToken: string } }>('/auth/login', {
      email,
      password,
    });
    
    const token = res.data.accessToken;
    localStorage.setItem('vg_session_token', token);
    
    return this.getCurrentUser();
  },

  async logout(): Promise<void> {
    if (USE_MOCK) {
      localStorage.removeItem('vg_session_token');
      localStorage.removeItem('vg_user');
      window.dispatchEvent(new Event('vg_logout'));
      window.location.hash = '#/login';
      return;
    }

    try {
      await apiClient.post('/auth/logout');
    } catch (e) {
      console.warn('Network logout failed, clearing session locally.', e);
    } finally {
      localStorage.removeItem('vg_session_token');
      window.dispatchEvent(new Event('vg_logout'));
      window.location.hash = '#/login';
    }
  },

  async getCurrentUser(): Promise<UserProfile> {
    if (USE_MOCK) {
      const stored = localStorage.getItem('vg_user');
      if (stored) return JSON.parse(stored);
      return MOCK_USER;
    }

    const res = await apiClient.get<{ data: UserProfile }>('/auth/me');
    return res.data;
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('vg_session_token');
  }
};
