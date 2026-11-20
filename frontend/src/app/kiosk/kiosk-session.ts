import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';

import { Api } from '../api/api';
import { kioskCheckin } from '../api/fn/kiosk/kiosk-checkin';
import { kioskCheckinsBatch } from '../api/fn/kiosk/kiosk-checkins-batch';
import { kioskHeartbeat } from '../api/fn/kiosk/kiosk-heartbeat';
import { kioskPair } from '../api/fn/kiosk/kiosk-pair';
import type { CheckInOutcome } from '../api/models/check-in-outcome';
import type { PairResponse } from '../api/models/pair-response';
import { importHmacKey, kioskToken, windowOf } from '../core/crypto/qr-token';
import { idb } from '../core/storage/idb';

export interface KioskConfig {
  companyCode: string;
  kioskId: string;
  kioskName: string;
  token: string;
  keyVersion: number;
  site: PairResponse['site'];
  company: PairResponse['company'];
}

export interface QueuedScan {
  token: string;
  client_uuid: string;
  scanned_at: string;
  offline: true;
}

const HEARTBEAT_MS = 30_000;
const SYNC_MS = 15_000;
const QUEUE_MAX_AGE_MS = 7 * 24 * 3600_000;

/**
 * State of the entrance tablet. The QR is computed locally (no Internet needed); badge scans made
 * while offline are queued in IndexedDB for up to 7 days and uploaded in a batch (EF-22, R5).
 */
@Injectable({ providedIn: 'root' })
export class KioskSession {
  private readonly api = inject(Api);
  private key: CryptoKey | null = null;
  private offsetMs = 0;
  private timers: ReturnType<typeof setInterval>[] = [];

  readonly config = signal<KioskConfig | null>(null);
  readonly online = signal(typeof navigator === 'undefined' ? true : navigator.onLine);
  readonly pending = signal(0);
  readonly revoked = signal(false);
  readonly loaded = signal(false);
  readonly paired = computed(() => this.config() !== null && !this.revoked());

  constructor() {
    const onOnline = () => {
      this.online.set(true);
      void this.sync();
    };
    const onOffline = () => this.online.set(false);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    inject(DestroyRef).onDestroy(() => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      this.stop();
    });
  }

  /** Authorization headers for machine calls (used by the kiosk interceptor). */
  headers(): Record<string, string> {
    const cfg = this.config();
    if (!cfg) return {};
    return { Authorization: `Kiosk ${cfg.token}`, 'X-Company-Code': cfg.companyCode };
  }

  pairingCompanyCode = '';

  async load(): Promise<void> {
    try {
      const cfg = await idb.get<KioskConfig>('config', 'kiosk');
      const key = await idb.get<CryptoKey>('config', 'kioskKey');
      if (cfg && key) {
        this.config.set(cfg);
        this.key = key;
        this.pending.set(await idb.count('queue'));
        this.start();
      }
    } finally {
      this.loaded.set(true);
    }
  }

  async pair(companyCode: string, code: string): Promise<void> {
    this.pairingCompanyCode = companyCode.trim().toUpperCase();
    const res = await this.api.invoke(kioskPair, { body: { code } });
    const key = await importHmacKey(res.secret);
    const cfg: KioskConfig = {
      companyCode: this.pairingCompanyCode,
      kioskId: res.kiosk_id,
      kioskName: res.kiosk_name,
      token: res.token,
      keyVersion: res.key_version,
      site: res.site,
      company: res.company,
    };
    this.offsetMs = res.epoch_ms - Date.now();
    await idb.set('config', 'kiosk', cfg);
    await idb.set('config', 'kioskKey', key);
    this.key = key;
    this.config.set(cfg);
    this.revoked.set(false);
    this.start();
  }

  async unpair(): Promise<void> {
    this.stop();
    await idb.delete('config', 'kiosk');
    await idb.delete('config', 'kioskKey');
    this.key = null;
    this.config.set(null);
  }

  /** Server-synchronised clock (resynchronised on every heartbeat, RG-01). */
  now(): number {
    return Date.now() + this.offsetMs;
  }

  async currentToken(): Promise<string | null> {
    const cfg = this.config();
    if (!cfg || !this.key) return null;
    return kioskToken(this.key, cfg.site.id, cfg.kioskId, windowOf(this.now()));
  }

  /** A badge or personal QR seen by the camera. Falls back to the offline queue. */
  async scan(token: string): Promise<CheckInOutcome | 'queued'> {
    const item: QueuedScan = {
      token,
      client_uuid: crypto.randomUUID(),
      scanned_at: new Date(this.now()).toISOString(),
      offline: true,
    };
    if (this.online()) {
      try {
        return await this.api.invoke(kioskCheckin, {
          body: { token, client_uuid: item.client_uuid },
        });
      } catch (err) {
        if (!(err instanceof HttpErrorResponse) || err.status !== 0) throw err;
        this.online.set(false);
      }
    }
    await idb.set('queue', item.client_uuid, item);
    this.pending.set(await idb.count('queue'));
    return 'queued';
  }

  async sync(): Promise<void> {
    if (!this.paired()) return;
    const items = (await idb.all<QueuedScan>('queue')).filter(
      (i) => this.now() - Date.parse(i.scanned_at) < QUEUE_MAX_AGE_MS,
    );
    if (items.length === 0) {
      await idb.clear('queue');
      this.pending.set(0);
      return;
    }
    try {
      const res = await this.api.invoke(kioskCheckinsBatch, { body: { items } });
      for (const result of res.items) {
        if (result.client_uuid) await idb.delete('queue', result.client_uuid);
      }
      this.online.set(true);
    } catch {
      this.online.set(false);
    }
    this.pending.set(await idb.count('queue'));
  }

  private async heartbeat(): Promise<void> {
    const cfg = this.config();
    if (!cfg) return;
    try {
      const sentAt = Date.now();
      const res = await this.api.invoke(kioskHeartbeat, {
        body: { app_version: 'web-1.0', pending: this.pending(), key_version: cfg.keyVersion },
      });
      this.offsetMs = res.epoch_ms - (sentAt + Date.now()) / 2;
      this.online.set(true);
      if (res.status === 'revoked') {
        this.revoked.set(true);
        return;
      }
      if (res.secret) {
        this.key = await importHmacKey(res.secret);
        const next = { ...cfg, keyVersion: res.key_version };
        await idb.set('config', 'kioskKey', this.key);
        await idb.set('config', 'kiosk', next);
        this.config.set(next);
      }
      if (this.pending() > 0) await this.sync();
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 401) this.revoked.set(true);
      else this.online.set(false);
    }
  }

  private start(): void {
    this.stop();
    void this.heartbeat();
    this.timers = [
      setInterval(() => void this.heartbeat(), HEARTBEAT_MS),
      setInterval(() => void this.sync(), SYNC_MS),
    ];
  }

  private stop(): void {
    this.timers.forEach(clearInterval);
    this.timers = [];
  }
}
