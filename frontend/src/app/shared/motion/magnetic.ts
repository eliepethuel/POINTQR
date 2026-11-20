import { DestroyRef, Directive, ElementRef, afterNextRender, inject, input } from '@angular/core';

import { MotionService } from './motion-service';

/**
 * Button that is gently attracted by the cursor (fine pointers only).
 * Animates `transform` only, batched in requestAnimationFrame.
 */
@Directive({ selector: '[pqMagnetic]' })
export class Magnetic {
  /** Maximum displacement in px. */
  readonly magneticStrength = input(10);

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly motion = inject(MotionService);

  constructor() {
    const destroyRef = inject(DestroyRef);
    afterNextRender(() => {
      const el = this.host.nativeElement;
      if (!window.matchMedia('(pointer: fine)').matches) return;

      let frame = 0;
      el.style.transition = 'transform var(--pq-dur-base) var(--pq-ease-out-back)';

      const move = (event: PointerEvent) => {
        if (this.motion.reduced()) return;
        const rect = el.getBoundingClientRect();
        const dx = (event.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
        const dy = (event.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
        const strength = this.magneticStrength();
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          el.style.transform = `translate3d(${dx * strength}px, ${dy * strength}px, 0)`;
        });
      };
      const reset = () => {
        cancelAnimationFrame(frame);
        el.style.transform = '';
      };

      el.addEventListener('pointermove', move);
      el.addEventListener('pointerleave', reset);
      destroyRef.onDestroy(() => {
        cancelAnimationFrame(frame);
        el.removeEventListener('pointermove', move);
        el.removeEventListener('pointerleave', reset);
      });
    });
  }
}
