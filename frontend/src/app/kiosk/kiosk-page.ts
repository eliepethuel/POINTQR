import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  afterNextRender,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { WINDOW_SECONDS } from '../core/crypto/qr-token';
import { problemMessage } from '../core/http/problem';
import { ThemeService } from '../core/theme/theme';
import { OtpInput } from '../features/auth/otp-input';
import { QrScanner } from '../shared/scan/qr-scanner';
import { CountdownRing } from './countdown-ring';
import { KioskSession } from './kiosk-session';
import { QrCanvas } from './qr-canvas';

interface Flash {
  readonly id: number;
  readonly kind: 'ok' | 'ko' | 'queued';
  readonly title: string;
  readonly detail: string;
}

/**
 * Kiosk mode (`/kiosk`): full-screen dynamic QR renewed every 30 s, giant server-synced clock,
 * badge/personal-QR scanning by the camera, offline queue (CDC §5, EF-17, EF-22, R5).
 */
@Component({
  selector: 'pq-kiosk-page',
  imports: [FormsModule, OtpInput, QrCanvas, CountdownRing, QrScanner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './kiosk-page.html',
  styleUrl: './kiosk-page.css',
  host: { '(document:keydown)': 'blockNavigation($event)' },
})
export class KioskPage {
  protected readonly session = inject(KioskSession);
  private readonly theme = inject(ThemeService);

  protected readonly token = signal<string | null>(null);
  protected readonly nowMs = signal(Date.now());
  protected readonly scanning = signal(false);
  protected readonly flash = signal<Flash | null>(null);
  protected readonly pairError = signal<string | null>(null);
  protected readonly pairing = signal(false);
  protected companyCode = '';
  private flashId = 0;
  private wakeLock: { release(): Promise<void> } | null = null;

  protected readonly remaining = computed(() => {
    const ms = this.nowMs() % (WINDOW_SECONDS * 1000);
    return Math.ceil((WINDOW_SECONDS * 1000 - ms) / 1000);
  });
  /** Clock in the company's timezone (IANA name, e.g. Africa/Abidjan). */
  protected readonly clock = computed(() =>
    new Intl.DateTimeFormat('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: this.session.config()?.company.timezone || 'Africa/Abidjan',
    }).format(this.nowMs()),
  );
  protected readonly fraction = computed(
    () => 1 - (this.nowMs() % (WINDOW_SECONDS * 1000)) / (WINDOW_SECONDS * 1000),
  );

  constructor() {
    const destroyRef = inject(DestroyRef);
    let timer: ReturnType<typeof setInterval> | undefined;
    let lastWindow = -1;
    const tick = () => {
      const now = this.session.now();
      this.nowMs.set(now);
      const window = Math.floor(now / 1000 / WINDOW_SECONDS);
      if (window !== lastWindow && this.session.paired()) {
        lastWindow = window;
        void this.session.currentToken().then((t) => this.token.set(t));
      }
    };
    afterNextRender(() => {
      void this.session.load();
      // 10 updates per second are enough for a smooth ring on entry-level tablets.
      timer = setInterval(tick, 100);
      void this.keepAwake();
    });
    effect(() => {
      const company = this.session.config()?.company;
      this.theme.applyBranding(company?.primary_color, company?.highlight_color);
      if (this.session.paired()) lastWindow = -1; // force a fresh token after pairing
    });
    destroyRef.onDestroy(() => {
      clearInterval(timer);
      void this.wakeLock?.release();
    });
  }

  protected async pair(code: string): Promise<void> {
    this.pairing.set(true);
    this.pairError.set(null);
    try {
      await this.session.pair(this.companyCode, code);
      void this.fullscreen();
    } catch (err) {
      this.pairError.set(problemMessage(err, 'Appairage impossible.'));
    } finally {
      this.pairing.set(false);
    }
  }

  protected async onScan(token: string): Promise<void> {
    try {
      const outcome = await this.session.scan(token);
      if (outcome === 'queued') {
        this.show(
          'queued',
          'Pointage enregistré hors-ligne',
          'Il sera envoyé au retour du réseau.',
        );
      } else if (outcome.result === 'accepted') {
        this.show('ok', outcome.agent_name ?? 'Pointage accepté', outcome.message);
      } else {
        this.show('ko', 'Pointage refusé', outcome.message);
      }
    } catch (err) {
      this.show('ko', 'Pointage refusé', problemMessage(err));
    }
  }

  protected fullscreen(): Promise<void> {
    const el = document.documentElement;
    return document.fullscreenElement || !el.requestFullscreen
      ? Promise.resolve()
      : el.requestFullscreen().catch(() => undefined);
  }

  /** The tablet is locked on this screen: no back navigation, no reload shortcut. */
  protected blockNavigation(event: KeyboardEvent): void {
    if (
      (event.altKey && event.key === 'ArrowLeft') ||
      event.key === 'F5' ||
      (event.ctrlKey && event.key === 'r')
    ) {
      event.preventDefault();
    }
  }

  private show(kind: Flash['kind'], title: string, detail: string): void {
    const flash = { id: ++this.flashId, kind, title, detail };
    this.flash.set(flash);
    navigator.vibrate?.(kind === 'ok' ? 60 : [80, 60, 80]);
    setTimeout(() => {
      if (this.flash()?.id === flash.id) this.flash.set(null);
    }, 2600);
  }

  /** Screen Wake Lock: the tablet never goes to sleep while showing the QR. */
  private async keepAwake(): Promise<void> {
    const nav = navigator as Navigator & {
      wakeLock?: { request(type: 'screen'): Promise<{ release(): Promise<void> }> };
    };
    try {
      this.wakeLock = (await nav.wakeLock?.request('screen')) ?? null;
      document.addEventListener(
        'visibilitychange',
        () => {
          if (document.visibilityState === 'visible') void this.keepAwake();
        },
        { once: true },
      );
    } catch {
      /* not supported or refused: the tablet settings must disable sleep */
    }
  }
}
