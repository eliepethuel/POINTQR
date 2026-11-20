import { DestroyRef, Injectable, inject, signal } from '@angular/core';

import { Session } from '../auth/session';

export interface LiveEvent {
  readonly event:
    'hello' | 'checkin.accepted' | 'checkin.refused' | 'kiosk.status' | 'request.created';
  readonly payload: Record<string, unknown>;
}

/**
 * WebSocket to /ws/dashboard/ (JWT in the query string, scoped by the server to the company or
 * the manager's teams). Reconnects with exponential backoff.
 */
@Injectable({ providedIn: 'root' })
export class DashboardSocket {
  private readonly session = inject(Session);
  private socket: WebSocket | null = null;
  private retry = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private listeners = new Set<(e: LiveEvent) => void>();
  readonly connected = signal(false);

  constructor() {
    inject(DestroyRef).onDestroy(() => this.close());
  }

  subscribe(listener: (e: LiveEvent) => void): () => void {
    this.listeners.add(listener);
    if (!this.socket) this.open();
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) this.close();
    };
  }

  private open(): void {
    const token = this.session.token();
    if (!token) return;
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(
      `${scheme}://${location.host}/ws/dashboard/?token=${encodeURIComponent(token)}`,
    );
    this.socket = socket;
    socket.onopen = () => {
      this.retry = 0;
      this.connected.set(true);
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(String(message.data)) as LiveEvent;
        this.listeners.forEach((l) => l(event));
      } catch {
        /* ignore malformed frames */
      }
    };
    socket.onclose = () => {
      this.connected.set(false);
      this.socket = null;
      if (this.listeners.size === 0) return;
      // The access token may have expired: refresh it before reconnecting.
      const delay = Math.min(30_000, 1000 * 2 ** this.retry++);
      this.timer = setTimeout(() => void this.session.refresh().then(() => this.open()), delay);
    };
  }

  private close(): void {
    clearTimeout(this.timer);
    this.socket?.close();
    this.socket = null;
    this.connected.set(false);
  }
}
