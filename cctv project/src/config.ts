export const USE_MOCK = false;

/**
 * Dynamically resolves the API base URL depending on deployment environment.
 */
export function getApiBaseUrl(): string {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  if (typeof window !== 'undefined' && (window.location.port === '5173' || window.location.port === '3000' || window.location.port === '4173')) {
    return 'http://localhost:8000/api/v1';
  }
  return '/api/v1';
}

/**
 * Dynamically resolves the WebSocket URL for live telemetry feeds.
 */
export function getWsUrl(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  if (typeof window !== 'undefined') {
    if (window.location.port === '5173' || window.location.port === '3000' || window.location.port === '4173') {
      return 'ws://localhost:8000/api/v1/ws';
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/api/v1/ws`;
  }
  return 'ws://localhost:8000/api/v1/ws';
}

/**
 * Dynamically resolves the backend host origin for static media asset requests.
 */
export function getBackendOrigin(): string {
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL;
  }
  if (typeof window !== 'undefined' && (window.location.port === '5173' || window.location.port === '3000' || window.location.port === '4173')) {
    return 'http://localhost:8000';
  }
  return typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';
}

