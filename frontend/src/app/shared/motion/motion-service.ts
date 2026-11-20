import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';

import { DURATION, type DurationToken } from './motion-tokens';

const STORAGE_KEY = 'pq.motion';
export type MotionPreference = 'system' | 'reduced' | 'full';

/**
 * Single source of truth for animation intensity.
 * Honors `prefers-reduced-motion` and the user's « Réduire les animations » switch.
 */
@Injectable({ providedIn: 'root' })
export class MotionService {
  private readonly document = inject(DOCUMENT);
  private readonly media = this.document.defaultView?.matchMedia?.(
    '(prefers-reduced-motion: reduce)',
  );

  private readonly systemReduced = signal(this.media?.matches ?? false);
  readonly preference = signal<MotionPreference>(this.readPreference());

  /** True when animations must be replaced by simple fades. */
  readonly reduced = computed(() => {
    const pref = this.preference();
    return pref === 'reduced' || (pref === 'system' && this.systemReduced());
  });

  constructor() {
    const listener = (event: MediaQueryListEvent) => this.systemReduced.set(event.matches);
    this.media?.addEventListener('change', listener);
    inject(DestroyRef).onDestroy(() => this.media?.removeEventListener('change', listener));

    effect(() => {
      const root = this.document.documentElement;
      if (this.reduced()) root.setAttribute('data-motion', 'reduced');
      else root.removeAttribute('data-motion');
    });
  }

  setPreference(value: MotionPreference): void {
    this.preference.set(value);
    try {
      this.document.defaultView?.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Storage unavailable (private mode): the preference simply lasts for this session.
    }
  }

  /** Duration in ms, collapsed to 0 when motion is reduced. */
  duration(token: DurationToken): number {
    return this.reduced() ? 0 : DURATION[token];
  }

  private readPreference(): MotionPreference {
    try {
      const stored = this.document.defaultView?.localStorage.getItem(STORAGE_KEY);
      return stored === 'reduced' || stored === 'full' ? stored : 'system';
    } catch {
      return 'system';
    }
  }
}
