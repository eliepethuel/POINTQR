import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import type { IScannerControls } from '@zxing/browser';

import { tokenKind } from '../../core/crypto/qr-token';

/**
 * Camera QR scanner (ZXing, loaded lazily). Only PointQR tokens are emitted, and the same
 * value is not emitted twice within ``cooldownMs``.
 */
@Component({
  selector: 'pq-qr-scanner',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="viewfinder" [class.compact]="compact()">
      <video #video muted playsinline aria-label="Aperçu de la caméra"></video>
      <span class="corner tl"></span><span class="corner tr"></span> <span class="corner bl"></span
      ><span class="corner br"></span>
      <span class="laser" aria-hidden="true"></span>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
    </div>
  `,
  styles: `
    .viewfinder {
      position: relative;
      width: 100%;
      aspect-ratio: 1;
      overflow: hidden;
      border-radius: 24px;
      background: #000;
    }
    video {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .corner {
      position: absolute;
      width: 18%;
      height: 18%;
      border: 4px solid var(--pq-highlight);
      animation: corner-pulse 1.8s var(--pq-ease-in-out-quart) infinite;
    }
    .tl {
      top: 8%;
      left: 8%;
      border-right: 0;
      border-bottom: 0;
      border-radius: 14px 0 0 0;
    }
    .tr {
      top: 8%;
      right: 8%;
      border-left: 0;
      border-bottom: 0;
      border-radius: 0 14px 0 0;
    }
    .bl {
      bottom: 8%;
      left: 8%;
      border-right: 0;
      border-top: 0;
      border-radius: 0 0 0 14px;
    }
    .br {
      bottom: 8%;
      right: 8%;
      border-left: 0;
      border-top: 0;
      border-radius: 0 0 14px 0;
    }
    @keyframes corner-pulse {
      50% {
        transform: scale(0.92);
        opacity: 0.7;
      }
    }
    .laser {
      position: absolute;
      left: 10%;
      right: 10%;
      top: 10%;
      height: 2px;
      background: linear-gradient(90deg, transparent, var(--pq-danger), transparent);
      box-shadow: 0 0 14px 2px rgb(255 107 74 / 0.7);
      animation: laser 2.2s ease-in-out infinite alternate;
    }
    @keyframes laser {
      to {
        transform: translateY(calc(min(80vw, 420px) * 0.78));
      }
    }
    .compact .laser {
      animation-duration: 1.6s;
    }
    .error {
      position: absolute;
      inset: auto 12px 12px;
      margin: 0;
      padding: 10px;
      border-radius: 10px;
      background: rgb(0 0 0 / 0.7);
      color: #fff;
      font-size: 0.875rem;
      text-align: center;
    }
    @media (prefers-reduced-motion: reduce) {
      .laser,
      .corner {
        animation: none;
      }
    }
  `,
})
export class QrScanner {
  readonly cooldownMs = input(3000);
  readonly compact = input(false);
  readonly scanned = output<string>();
  protected readonly error = signal<string | null>(null);

  private readonly video = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private controls: IScannerControls | null = null;
  private last = { value: '', at: 0 };

  constructor() {
    const destroyRef = inject(DestroyRef);
    let destroyed = false;
    destroyRef.onDestroy(() => {
      destroyed = true;
      this.controls?.stop();
    });
    afterNextRender(async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        this.error.set('Caméra indisponible sur cet appareil.');
        return;
      }
      try {
        const { BrowserQRCodeReader } = await import('@zxing/browser');
        if (destroyed) return;
        const reader = new BrowserQRCodeReader(undefined, { delayBetweenScanAttempts: 150 });
        this.controls = await reader.decodeFromConstraints(
          { video: { facingMode: 'environment' } },
          this.video().nativeElement,
          (result) => {
            if (result) this.emit(result.getText());
          },
        );
        if (destroyed) this.controls.stop();
      } catch {
        this.error.set('Accès à la caméra refusé : autorisez-le dans le navigateur.');
      }
    });
  }

  private emit(text: string): void {
    if (!tokenKind(text)) return;
    const now = Date.now();
    if (text === this.last.value && now - this.last.at < this.cooldownMs()) return;
    this.last = { value: text, at: now };
    this.scanned.emit(text);
  }
}
