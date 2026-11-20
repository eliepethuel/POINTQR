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

/** Plays a Lottie animation from /public (lottie-web is loaded lazily, SVG renderer). */
@Component({
  selector: 'pq-lottie',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="lottie" aria-hidden="true"></div>`,
  styles: `
    .lottie {
      width: 100%;
      height: 100%;
    }
  `,
})
export class LottiePlayer {
  readonly src = input.required<string>();
  readonly loop = input(false);

  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private readonly motion = inject(MotionService);

  constructor() {
    const destroyRef = inject(DestroyRef);
    let destroy: (() => void) | undefined;
    let destroyed = false;
    destroyRef.onDestroy(() => {
      destroyed = true;
      destroy?.();
    });
    afterNextRender(async () => {
      const lottie = (await import('lottie-web')).default;
      if (destroyed) return;
      const animation = lottie.loadAnimation({
        container: this.host().nativeElement,
        renderer: 'svg',
        loop: this.loop(),
        autoplay: !this.motion.reduced(),
        path: this.src(),
      });
      if (this.motion.reduced()) {
        animation.addEventListener('DOMLoaded', () =>
          animation.goToAndStop(animation.totalFrames - 1, true),
        );
      }
      destroy = () => animation.destroy();
    });
  }
}
