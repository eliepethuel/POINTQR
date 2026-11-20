import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  viewChild,
} from '@angular/core';
import QRCode from 'qrcode';

import { MotionService } from '../shared/motion/motion-service';

interface Matrix {
  size: number;
  data: ArrayLike<number>;
}

const DISSOLVE_MS = 650;

/**
 * Draws a QR code on a canvas. When the value changes, modules flip one by one at random
 * moments: the new code "dissolves" in over the previous one (pixel morphing).
 */
@Component({
  selector: 'pq-qr-canvas',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<canvas #canvas [attr.aria-label]="label()" role="img"></canvas>`,
  styles: `
    :host {
      display: block;
    }
    canvas {
      display: block;
      width: 100%;
      height: auto;
      image-rendering: pixelated;
      border-radius: 18px;
      background: #fff;
    }
  `,
})
export class QrCanvas {
  readonly value = input.required<string>();
  readonly label = input('QR code');
  readonly dark = input('#0E0F1A');
  readonly pixelSize = input(12);

  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly motion = inject(MotionService);
  private previous: Matrix | null = null;
  private frame = 0;

  constructor() {
    effect(() => this.draw(this.value()));
    inject(DestroyRef).onDestroy(() => cancelAnimationFrame(this.frame));
  }

  private draw(text: string): void {
    const qr = QRCode.create(text, { errorCorrectionLevel: 'M' });
    const next: Matrix = { size: qr.modules.size, data: qr.modules.data };
    const old = this.previous && this.previous.size === next.size ? this.previous : null;
    this.previous = next;
    cancelAnimationFrame(this.frame);
    if (!old || this.motion.reduced()) {
      this.paint(next, null, 1, null);
      return;
    }
    // Each module gets a random moment within the dissolve to switch from old to new.
    const thresholds = Float32Array.from({ length: next.size * next.size }, () => Math.random());
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / DISSOLVE_MS);
      this.paint(next, old, progress, thresholds);
      if (progress < 1) this.frame = requestAnimationFrame(step);
    };
    this.frame = requestAnimationFrame(step);
  }

  private paint(
    next: Matrix,
    old: Matrix | null,
    progress: number,
    thresholds: Float32Array | null,
  ): void {
    const canvas = this.canvas().nativeElement;
    const quiet = 4;
    const px = this.pixelSize();
    const side = (next.size + quiet * 2) * px;
    if (canvas.width !== side) {
      canvas.width = side;
      canvas.height = side;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, side, side);
    ctx.fillStyle = this.dark();
    for (let y = 0; y < next.size; y++) {
      for (let x = 0; x < next.size; x++) {
        const i = y * next.size + x;
        const flipped = !old || !thresholds || (thresholds[i] ?? 0) < progress;
        const on = flipped ? next.data[i] : old.data[i];
        if (on) ctx.fillRect((x + quiet) * px, (y + quiet) * px, px, px);
      }
    }
  }
}
