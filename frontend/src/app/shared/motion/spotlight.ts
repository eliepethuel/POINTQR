import { DestroyRef, Directive, ElementRef, afterNextRender, inject } from '@angular/core';

/**
 * Halo that follows the cursor inside the host (see `.pq-spotlight` in styles/effects.css).
 * Only CSS custom properties are written; the gradient itself is painted by CSS.
 */
@Directive({
  selector: '[pqSpotlight]',
  host: { class: 'pq-spotlight' },
})
export class Spotlight {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  constructor() {
    const destroyRef = inject(DestroyRef);
    afterNextRender(() => {
      const el = this.host.nativeElement;
      let frame = 0;
      const move = (event: PointerEvent) => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          const rect = el.getBoundingClientRect();
          el.style.setProperty('--pq-mx', `${event.clientX - rect.left}px`);
          el.style.setProperty('--pq-my', `${event.clientY - rect.top}px`);
          el.style.setProperty('--pq-spot-opacity', '1');
        });
      };
      const leave = () => el.style.setProperty('--pq-spot-opacity', '0');
      el.addEventListener('pointermove', move);
      el.addEventListener('pointerleave', leave);
      destroyRef.onDestroy(() => {
        cancelAnimationFrame(frame);
        el.removeEventListener('pointermove', move);
        el.removeEventListener('pointerleave', leave);
      });
    });
  }
}
