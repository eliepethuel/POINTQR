import { DestroyRef, Directive, ElementRef, afterNextRender, inject, input } from '@angular/core';

import { STAGGER_MS } from './motion-tokens';

/**
 * Fades and lifts the host in when it enters the viewport.
 * Pure CSS transition (see styles/effects.css) driven by an IntersectionObserver: no GSAP needed.
 *
 * <div pqRevealOnScroll [revealIndex]="i"></div>
 */
@Directive({
  selector: '[pqRevealOnScroll]',
  host: { 'data-reveal': 'hidden' },
})
export class RevealOnScroll {
  /** Position in a list, used to cascade siblings. */
  readonly revealIndex = input(0);
  /** Extra delay in ms. */
  readonly revealDelay = input(0);
  /** Reveal once (default) or every time the element re-enters. */
  readonly revealOnce = input(true);

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  constructor() {
    const destroyRef = inject(DestroyRef);
    afterNextRender(() => {
      const el = this.host.nativeElement;
      el.style.setProperty(
        '--pq-reveal-delay',
        `${this.revealDelay() + this.revealIndex() * STAGGER_MS}ms`,
      );

      if (typeof IntersectionObserver === 'undefined') {
        el.dataset['reveal'] = 'visible';
        return;
      }
      const observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              el.dataset['reveal'] = 'visible';
              if (this.revealOnce()) observer.disconnect();
            } else if (!this.revealOnce()) {
              el.dataset['reveal'] = 'hidden';
            }
          }
        },
        { rootMargin: '0px 0px -10% 0px', threshold: 0.12 },
      );
      observer.observe(el);
      destroyRef.onDestroy(() => observer.disconnect());
    });
  }
}
