import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  inject,
  input,
  viewChild,
} from '@angular/core';

import { MotionService } from './motion-service';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
}

/** Small confetti burst from the centre (canvas, ~800 ms), played once on success. */
@Component({
  selector: 'pq-particle-burst',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<canvas #canvas aria-hidden="true"></canvas>`,
  styles: `
    :host {
      position: absolute;
      inset: -40%;
      pointer-events: none;
    }
    canvas {
      width: 100%;
      height: 100%;
    }
  `,
})
export class ParticleBurst {
  readonly count = input(42);
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly motion = inject(MotionService);

  constructor() {
    let frame = 0;
    inject(DestroyRef).onDestroy(() => cancelAnimationFrame(frame));
    afterNextRender(() => {
      if (this.motion.reduced()) return;
      const canvas = this.canvas().nativeElement;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = canvas.clientWidth * ratio;
      canvas.height = canvas.clientHeight * ratio;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const colors = ['#3DDC97', '#D4FF3A', '#7C5CFF', '#F4F4F6'];
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const particles: Particle[] = Array.from({ length: this.count() }, (_, i) => {
        const angle = (i / this.count()) * Math.PI * 2 + Math.random() * 0.4;
        const speed = (4 + Math.random() * 6) * ratio;
        return {
          x: cx,
          y: cy,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          size: (3 + Math.random() * 4) * ratio,
          color: colors[i % colors.length] ?? '#3DDC97',
        };
      });
      const start = performance.now();
      const step = (now: number) => {
        const t = (now - start) / 800;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.globalAlpha = Math.max(0, 1 - t);
        for (const p of particles) {
          p.x += p.vx;
          p.y += p.vy;
          p.vy += 0.18 * ratio; // gravity
          p.vx *= 0.97;
          ctx.fillStyle = p.color;
          ctx.fillRect(p.x, p.y, p.size, p.size);
        }
        if (t < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    });
  }
}
