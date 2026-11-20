import { DestroyRef, Injectable, computed, inject, resource, signal } from '@angular/core';

import { Api } from '../../api/api';
import { systemHealth } from '../../api/fn/system/system-health';
import type { Health } from '../../api/models/health';

export type ConnectionState = 'loading' | 'online' | 'degraded' | 'offline';

/**
 * Platform status and authoritative server clock (RG-01: the server time is the only one that counts).
 * The local clock is only used to tick between two synchronisations.
 */
@Injectable({ providedIn: 'root' })
export class ServerStatus {
  private readonly api = inject(Api);
  private readonly now = signal(Date.now());

  private readonly health = resource({
    loader: async (): Promise<{ health: Health; offsetMs: number }> => {
      const sentAt = Date.now();
      const health = await this.api.invoke(systemHealth);
      const receivedAt = Date.now();
      // Assume symmetric latency: the server answered halfway through the round trip.
      const offsetMs = health.epoch_ms - (sentAt + receivedAt) / 2;
      return { health, offsetMs };
    },
  });

  readonly state = computed<ConnectionState>(() => {
    if (this.health.isLoading() && !this.health.hasValue()) return 'loading';
    if (this.health.error() || !this.health.hasValue()) return 'offline';
    return this.health.value().health.status === 'ok' ? 'online' : 'degraded';
  });

  readonly version = computed(() =>
    this.health.hasValue() ? this.health.value().health.version : null,
  );

  /** Current server time, ticking every second. Null until the first synchronisation. */
  readonly serverTime = computed<Date | null>(() => {
    if (!this.health.hasValue()) return null;
    return new Date(this.now() + this.health.value().offsetMs);
  });

  constructor() {
    const tick = setInterval(() => this.now.set(Date.now()), 1000);
    inject(DestroyRef).onDestroy(() => clearInterval(tick));
  }

  refresh(): void {
    this.health.reload();
  }
}
