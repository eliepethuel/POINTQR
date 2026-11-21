import { DestroyRef, Directive, ElementRef, afterNextRender, inject, input } from '@angular/core';

import { MotionService } from './motion-service';

/** Card that tilts in 3D towards the cursor (fine pointers only, transform only). */
@Directive({ selector: '[pqTilt3d]' })
export class Tilt3d {
  readonly tiltMax = input(8);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly motion = inject(MotionService);

  constructor() {
    const destroyRef = inject(DestroyRef);
    afterNextRender(() => {
      const el = this.host.nativeElement;
      if (!window.matchMedia('(pointer: fine)').matches) return;
      let frame = 0;
      el.style.transition = 'transform var(--pq-dur-base) var(--pq-ease-out-expo)';
      el.style.transformStyle = 'preserve-3d';
      const move = (e: PointerEvent) => {
        if (this.motion.reduced()) return;
        const r = el.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          el.style.transform = `perspective(900px) rotateX(${-y * this.tiltMax()}deg) rotateY(${x * this.tiltMax()}deg)`;
        });
      };
      const leave = () => {
        cancelAnimationFrame(frame);
        el.style.transform = '';
      };
      el.addEventListener('pointermove', move);
      el.addEventListener('pointerleave', leave);
      destroyRef.onDestroy(() => {
        el.removeEventListener('pointermove', move);
        el.removeEventListener('pointerleave', leave);
      });
    });
  }
}
