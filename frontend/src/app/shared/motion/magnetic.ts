import { DestroyRef, Directive, ElementRef, afterNextRender, inject, input } from '@angular/core';

import { MotionService } from './motion-service';

/**
 * Button that is gently attracted by the cursor (fine pointers only).
 * Writes the individual `translate` property (batched in requestAnimationFrame) so it composes with
 * other transform-based effects such as [pqRevealOnScroll]; the transition lives in `.pq-magnetic`.
 */
@Directive({ selector: '[pqMagnetic]', host: { class: 'pq-magnetic' } })
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

      const move = (event: PointerEvent) => {
        if (this.motion.reduced()) return;
        const rect = el.getBoundingClientRect();
        const dx = (event.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
        const dy = (event.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
        const strength = this.magneticStrength();
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          el.style.translate = `${dx * strength}px ${dy * strength}px`;
        });
      };
      const reset = () => {
        cancelAnimationFrame(frame);
        el.style.translate = '';
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
