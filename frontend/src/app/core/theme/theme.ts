import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal } from '@angular/core';

import { MotionService } from '../../shared/motion/motion-service';

export type ThemeMode = 'dark' | 'light';
const STORAGE_KEY = 'pq.theme';
const HEX = /^#[0-9a-f]{6}$/i;

/** Dark/light theme with a circular reveal from the clicked control, and company branding (EF-43). */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly motion = inject(MotionService);
  readonly mode = signal<ThemeMode>(this.read());

  constructor() {
    effect(() => {
      const root = this.document.documentElement;
      root.dataset['theme'] = this.mode();
      this.document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute('content', this.mode() === 'dark' ? '#0E0F1A' : '#F6F6FB');
    });
  }

  toggle(origin?: { x: number; y: number }): void {
    const next: ThemeMode = this.mode() === 'dark' ? 'light' : 'dark';
    const apply = () => {
      this.mode.set(next);
      this.document.documentElement.dataset['theme'] = next;
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* not persisted */
      }
    };
    const doc = this.document as Document & {
      startViewTransition?: (cb: () => void) => { ready: Promise<void> };
    };
    if (!doc.startViewTransition || this.motion.reduced() || !origin) {
      apply();
      return;
    }
    const { x, y } = origin;
    const view = this.document.defaultView;
    const radius = Math.hypot(
      Math.max(x, (view?.innerWidth ?? 0) - x),
      Math.max(y, (view?.innerHeight ?? 0) - y),
    );
    const transition = doc.startViewTransition(apply);
    transition.ready.then(() => {
      this.document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        {
          duration: 600,
          easing: 'cubic-bezier(0.16, 1, 0.3, 1)',
          pseudoElement: '::view-transition-new(root)',
        },
      );
    });
  }

  /** Applies the company's colours to the design tokens; invalid values are ignored. */
  applyBranding(primary?: string | null, highlight?: string | null): void {
    const style = this.document.documentElement.style;
    if (primary && HEX.test(primary)) style.setProperty('--pq-accent', primary);
    else style.removeProperty('--pq-accent');
    if (highlight && HEX.test(highlight)) style.setProperty('--pq-highlight', highlight);
    else style.removeProperty('--pq-highlight');
  }

  private read(): ThemeMode {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') return stored;
    } catch {
      /* default below */
    }
    return 'dark';
  }
}
