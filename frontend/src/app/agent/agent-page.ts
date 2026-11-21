import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  resource,
  signal,
} from '@angular/core';

import { Api } from '../api/api';
import { mobileActivate } from '../api/fn/mobile/mobile-activate';
import { mobileCheckin } from '../api/fn/mobile/mobile-checkin';
import { mobilePersonalKey } from '../api/fn/mobile/mobile-personal-key';
import { mobileStatus } from '../api/fn/mobile/mobile-status';
import type { CheckInOutcome } from '../api/models/check-in-outcome';
import { Session } from '../core/auth/session';
import { importHmacKey, personalToken, windowOf, WINDOW_SECONDS } from '../core/crypto/qr-token';
import { deviceId, deviceLabel } from '../core/device/device-id';
import { problemCode, problemMessage } from '../core/http/problem';
import { QrCanvas } from '../kiosk/qr-canvas';
import { LottiePlayer } from '../shared/motion/lottie-player';
import { ParticleBurst } from '../shared/motion/particle-burst';
import { QrScanner } from '../shared/scan/qr-scanner';

type Tab = 'scan' | 'qr' | 'today';

/**
 * Agent PWA (`/agent`): check in in two gestures (ENF-22) — open, scan. The position is read only
 * at that moment (ENF-03); the time shown is the server's (RG-01).
 */
@Component({
  selector: 'pq-agent-page',
  imports: [DatePipe, QrScanner, QrCanvas, LottiePlayer, ParticleBurst],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-page.html',
  styleUrl: './agent-page.css',
})
export class AgentPage {
  private readonly api = inject(Api);
  protected readonly session = inject(Session);
  private readonly device = deviceId();

  protected readonly tab = signal<Tab>('scan');
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<CheckInOutcome | null>(null);
  protected readonly locating = signal(false);
  protected readonly status = resource({
    loader: () => this.api.invoke(mobileStatus, { device_id: this.device }),
  });
  protected readonly bound = computed(() => this.status.value()?.device_bound ?? false);
  protected readonly phoneState = computed(() => this.status.value()?.phone_state ?? 'unbound');
  protected readonly firstName = computed(
    () => this.status.value()?.agent_name.split(' ')[0] ?? '',
  );

  protected readonly personalQr = signal<string | null>(null);
  private personalKey: CryptoKey | null = null;
  private qrTimer: ReturnType<typeof setInterval> | undefined;

  constructor() {
    inject(DestroyRef).onDestroy(() => clearInterval(this.qrTimer));
  }

  protected async activate(): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.invoke(mobileActivate, { body: { device_id: this.device, ...deviceLabel() } });
      this.status.reload();
    } catch (err) {
      // Another phone is linked: the change request now waits for HR, the screen says so.
      if (problemCode(err) === 'device_change_pending') this.status.reload();
      else this.error.set(problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }

  protected async onScan(token: string): Promise<void> {
    if (this.busy() || this.result()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      const position = await this.locate();
      const outcome = await this.api.invoke(mobileCheckin, {
        body: {
          token,
          device_id: this.device,
          latitude: position?.coords.latitude ?? null,
          longitude: position?.coords.longitude ?? null,
          accuracy_m: position ? Math.round(position.coords.accuracy) : null,
        },
      });
      this.result.set(outcome);
      navigator.vibrate?.(outcome.result === 'accepted' ? [40, 40, 90] : [200, 80, 200]);
      this.status.reload();
    } catch (err) {
      this.error.set(problemMessage(err, 'Pointage impossible.'));
      navigator.vibrate?.([200, 80, 200]);
    } finally {
      this.busy.set(false);
    }
  }

  protected dismiss(): void {
    this.result.set(null);
  }

  protected async showTab(tab: Tab): Promise<void> {
    this.tab.set(tab);
    clearInterval(this.qrTimer);
    if (tab !== 'qr') return;
    try {
      if (!this.personalKey) {
        const res = await this.api.invoke(mobilePersonalKey, { device_id: this.device });
        this.personalKey = await importHmacKey(res.key);
      }
      const agentId = this.status.value()?.agent_id;
      const refresh = async () => {
        if (this.personalKey && agentId) {
          this.personalQr.set(await personalToken(this.personalKey, agentId, windowOf(Date.now())));
        }
      };
      await refresh();
      this.qrTimer = setInterval(() => void refresh(), 1000);
    } catch (err) {
      this.error.set(problemMessage(err));
    }
  }

  protected readonly windowSeconds = WINDOW_SECONDS;

  /** Position read once, at check-in time only, never in the background (ENF-03). */
  private locate(): Promise<GeolocationPosition | null> {
    if (!navigator.geolocation) return Promise.resolve(null);
    this.locating.set(true);
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          this.locating.set(false);
          resolve(pos);
        },
        () => {
          this.locating.set(false);
          resolve(null);
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 },
      );
    });
  }
}
