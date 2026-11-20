import {
  DestroyRef,
  Directive,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
} from '@angular/core';

import { DURATION, easeOutExpo } from './motion-tokens';
import { MotionService } from './motion-service';

/**
 * Animated counter: tweens the host text from its previous value to `pqCountUp`.
 * Starts when visible; jumps straight to the value when motion is reduced.
 *
 * <span [pqCountUp]="present()" [countDecimals]="0" countSuffix=" %"></span>
 */
@Directive({ selector: '[pqCountUp]' })
export class CountUp {
  readonly pqCountUp = input.required<number>();
  readonly countDuration = input<number>(DURATION.hero);
  readonly countDecimals = input(0);
  readonly countPrefix = input('');
  readonly countSuffix = input('');

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly motion = inject(MotionService);
  private current = 0;
  private frame = 0;
  private visible = false;

  constructor() {
    const destroyRef = inject(DestroyRef);

    afterNextRender(() => {
      const el = this.host.nativeElement;
      if (typeof IntersectionObserver === 'undefined') {
        this.visible = true;
        this.animateTo(this.pqCountUp());
        return;
      }
      const observer = new IntersectionObserver(([entry]) => {
        if (entry?.isIntersecting) {
          this.visible = true;
          this.animateTo(this.pqCountUp());
          observer.disconnect();
        }
      });
      observer.observe(el);
      destroyRef.onDestroy(() => observer.disconnect());
    });

    effect(() => {
      const target = this.pqCountUp();
      if (this.visible) this.animateTo(target);
      else this.render(0);
    });

    destroyRef.onDestroy(() => cancelAnimationFrame(this.frame));
  }

  /** Formats a number with the French locale (narrow no-break space thousands separator). */
  format(value: number): string {
    const decimals = this.countDecimals();
    const text = new Intl.NumberFormat('fr-FR', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(value);
    return `${this.countPrefix()}${text}${this.countSuffix()}`;
  }

  private animateTo(target: number): void {
    cancelAnimationFrame(this.frame);
    const from = this.current;
    const duration = this.motion.reduced() ? 0 : this.countDuration();
    if (duration <= 0 || from === target) {
      this.render(target);
      return;
    }
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      this.render(from + (target - from) * easeOutExpo(progress));
      if (progress < 1) this.frame = requestAnimationFrame(step);
    };
    this.frame = requestAnimationFrame(step);
  }

  private render(value: number): void {
    this.current = value;
    this.host.nativeElement.textContent = this.format(value);
  }
}
