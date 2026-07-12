import { toCamel } from '../utils/case';

type WSCallback = (data: any) => void;

class WebSocketManager {
  private socket: WebSocket | null = null;
  private listeners: Record<string, WSCallback[]> = {};
  private reconnectInterval: any = null;
  private isConnecting = false;

  public connect(): void {
    if (this.socket || this.isConnecting) return;
    this.isConnecting = true;

    try {
      this.socket = new WebSocket('ws://localhost:8000/api/v1/ws');

      this.socket.onopen = () => {
        this.isConnecting = false;
        console.log('✓ VisionGuard WebSocket connected successfully.');
        if (this.reconnectInterval) {
          clearInterval(this.reconnectInterval);
          this.reconnectInterval = null;
        }
      };

      this.socket.onmessage = (event) => {
        if (event.data === '{"type":"pong"}') return;
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;
          if (type && this.listeners[type]) {
            const camelData = toCamel(data);
            this.listeners[type].forEach(cb => cb(camelData));
          }

        } catch (e) {
          console.error('Failed to parse WebSocket message frame:', e);
        }
      };

      this.socket.onclose = () => {
        this.socket = null;
        this.isConnecting = false;
        console.warn('VisionGuard WebSocket disconnected. Retrying in 5 seconds...');
        this.scheduleReconnect();
      };

      this.socket.onerror = (error) => {
        console.error('WebSocket connection error:', error);
      };
    } catch (e) {
      this.isConnecting = false;
      console.error('WebSocket initialization failed:', e);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectInterval) return;
    this.reconnectInterval = setInterval(() => {
      this.connect();
    }, 5000);
  }

  public disconnect(): void {
    if (this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
      this.reconnectInterval = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  public on(eventType: string, callback: WSCallback): () => void {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = [];
    }
    this.listeners[eventType].push(callback);

    // Auto-connect on subscription if not connected
    if (!this.socket && !this.isConnecting) {
      this.connect();
    }

    return () => {
      if (this.listeners[eventType]) {
        this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback);
      }
    };
  }
}

export const wsManager = new WebSocketManager();
