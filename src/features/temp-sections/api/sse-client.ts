/**
 * Server-Sent Events client for temp sections
 */

import { TempSectionsSSEEvent } from '../../../types/temp-sections';

export interface SSEClientOptions {
  url: string;
  onMessage: (event: TempSectionsSSEEvent) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export class TempSectionsSSEClient {
  private eventSource: EventSource | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private isConnected = false;
  private options: SSEClientOptions;

  constructor(options: SSEClientOptions) {
    this.options = {
      reconnectInterval: 5000,
      maxReconnectAttempts: 10,
      ...options
    };
  }

  connect(): void {
    if (this.eventSource) {
      this.disconnect();
    }

    try {
      this.eventSource = new EventSource(this.options.url);
      
      this.eventSource.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.options.onOpen?.();
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.options.onMessage(data);
        } catch (error) {
          console.error('Error parsing SSE message:', error);
        }
      };

      this.eventSource.onerror = (error) => {
        this.isConnected = false;
        this.options.onError?.(error);
        this.handleReconnect();
      };

    } catch (error) {
      console.error('Error creating SSE connection:', error);
      this.handleReconnect();
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.isConnected = false;
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts!) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`);
      this.connect();
    }, this.options.reconnectInterval);
  }

  getConnectionStatus(): boolean {
    return this.isConnected;
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }
}
