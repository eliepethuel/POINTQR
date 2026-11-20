import { DestroyRef, Directive, ElementRef, afterNextRender, inject, input } from '@angular/core';

import { loadSplitText } from './gsap-loader';
import { DURATION, EASE } from './motion-tokens';
import { MotionService } from './motion-service';

/**
 * Reveals a heading letter by letter (or word by word) with GSAP SplitText.
 * The original text stays in the accessibility tree (SplitText adds aria-label).
 *
 * <h1 pqSplitText splitBy="chars">Le pointage qui ne ment pas.</h1>
 */
@Directive({ selector: '[pqSplitText]' })
export class SplitTextDirective {
  readonly splitBy = input<'chars' | 'words' | 'lines'>('chars');
  readonly splitDelay = input(0);

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly motion = inject(MotionService);

  constructor() {
    const destroyRef = inject(DestroyRef);
    let revert: (() => void) | undefined;
    let destroyed = false;
    destroyRef.onDestroy(() => {
      destroyed = true;
      revert?.();
    });

    afterNextRender(() => {
      if (this.motion.reduced()) return;
      const el = this.host.nativeElement;
      el.style.visibility = 'hidden';

      loadSplitText()
        .then(({ gsap, SplitText }) => {
          if (destroyed) return;
          const ctx = gsap.context(() => {
            const split = SplitText.create(el, { type: this.splitBy(), aria: 'auto' });
            const targets = split[this.splitBy()];
            gsap.set(el, { visibility: 'visible' });
            gsap.from(targets, {
              yPercent: 110,
              opacity: 0,
              rotate: 4,
              duration: DURATION.slow / 1000,
              ease: EASE.outExpo,
              stagger: this.splitBy() === 'chars' ? 0.022 : 0.06,
              delay: this.splitDelay() / 1000,
            });
          }, el);
          revert = () => ctx.revert();
        })
        .catch(() => {
          el.style.visibility = 'visible';
        });
    });
  }
}
