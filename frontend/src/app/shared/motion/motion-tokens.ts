/** Motion tokens — keep in sync with the CSS variables in styles/tokens.css. */
export const DURATION = {
  instant: 100,
  fast: 200,
  base: 320,
  slow: 600,
  hero: 1200,
} as const;

export type DurationToken = keyof typeof DURATION;

/** GSAP easing names matching the CSS cubic-bezier tokens. */
export const EASE = {
  outExpo: 'expo.out',
  outBack: 'back.out(1.4)',
  inOutQuart: 'power4.inOut',
  spring: 'elastic.out(1, 0.6)',
} as const;

export type EaseToken = keyof typeof EASE;

/** Default delay between siblings in staggered entrances (ms). */
export const STAGGER_MS = 60;

/** JS equivalent of the CSS out-expo curve, for requestAnimationFrame-driven tweens. */
export function easeOutExpo(t: number): number {
  return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
}
