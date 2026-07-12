import { toCamel, toSnake } from '../utils/case';

const BASE_URL = 'http://localhost:8000/api/v1';


export const apiClient = {
  getHeaders() {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const token = localStorage.getItem('vg_session_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  },

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${BASE_URL}${path}`;
    const isMultipart = options.body instanceof FormData;
    const headers = {
      ...this.getHeaders(),
      ...(options.headers as Record<string, string>),
    };
    
    if (isMultipart) {
      delete headers['Content-Type'];
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('vg_session_token');
        window.dispatchEvent(new Event('vg_logout'));
        if (window.location.hash !== '#/login') {
          window.location.hash = '/login';
        }
      }
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.message || 'API request failed');
    }

    const data = await response.json();
    return toCamel(data) as T;
  },

  get<T>(path: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  },

  post<T>(path: string, body?: any, options: RequestInit = {}): Promise<T> {
    const isMultipart = body instanceof FormData;
    return this.request<T>(path, {
      ...options,
      method: 'POST',
      body: body ? (isMultipart ? body : JSON.stringify(toSnake(body))) : undefined,
    });
  },

  put<T>(path: string, body?: any, options: RequestInit = {}): Promise<T> {
    const isMultipart = body instanceof FormData;
    return this.request<T>(path, {
      ...options,
      method: 'PUT',
      body: body ? (isMultipart ? body : JSON.stringify(toSnake(body))) : undefined,
    });
  },

  patch<T>(path: string, body?: any, options: RequestInit = {}): Promise<T> {
    const isMultipart = body instanceof FormData;
    return this.request<T>(path, {
      ...options,
      method: 'PATCH',
      body: body ? (isMultipart ? body : JSON.stringify(toSnake(body))) : undefined,
    });
  },

  delete<T>(path: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }
};
