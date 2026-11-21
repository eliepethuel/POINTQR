import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  signal,
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
 *
 * The canvas is sized to its slot so that every module is a whole number of device pixels:
 * scaling a fixed bitmap by CSS gave modules of uneven width, which camera decoders (ZXing)
 * failed to read from a tablet screen.
 */
@Component({
  selector: 'pq-qr-canvas',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<canvas #canvas [attr.aria-label]="label()" role="img"></canvas>`,
  styles: `
    /* The rounded white frame is the host: the canvas stays square, so the corners of the
       quiet zone are never clipped (rounded canvas corners defeated camera decoders). */
    :host {
      display: grid;
      place-items: center;
      aspect-ratio: 1;
      padding: 10px;
      border-radius: 18px;
      background: #fff;
    }
    canvas {
      display: block;
      max-width: 100%;
      height: auto;
      image-rendering: pixelated;
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
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  /** Width of the slot in CSS pixels (0 until measured: the pixelSize input is used). */
  private readonly slot = signal(0);
  private previous: Matrix | null = null;
  private frame = 0;

  constructor() {
    effect(() => this.draw(this.value()));
    effect(() => {
      // A new slot size repaints the current code at the new module size, without animation.
      if (this.slot() && this.previous) this.paint(this.previous, null, 1, null);
    });
    const destroyRef = inject(DestroyRef);
    destroyRef.onDestroy(() => cancelAnimationFrame(this.frame));
    afterNextRender(() => {
      if (typeof ResizeObserver === 'undefined') return;
      const observer = new ResizeObserver(([entry]) =>
        this.slot.set(Math.floor(entry?.contentRect.width ?? 0)),
      );
      observer.observe(this.host.nativeElement);
      destroyRef.onDestroy(() => observer.disconnect());
    });
  }

  /** Device pixels per module: as large as the slot allows, never fractional. */
  private modulePixels(modules: number): { px: number; dpr: number } {
    const dpr = window.devicePixelRatio || 1;
    const width = this.slot();
    if (!width) return { px: this.pixelSize(), dpr: 0 };
    return { px: Math.max(1, Math.floor((width * dpr) / modules)), dpr };
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
    const { px, dpr } = this.modulePixels(next.size + quiet * 2);
    const side = (next.size + quiet * 2) * px;
    if (canvas.width !== side) {
      canvas.width = side;
      canvas.height = side;
    }
    // Displayed at exactly side / dpr CSS pixels, so one module = px device pixels.
    canvas.style.width = dpr ? `${side / dpr}px` : '';
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
