/**
 * GSAP is loaded lazily so it never weighs on the initial bundle.
 * Each loader registers its plugin once and returns the configured `gsap` instance.
 */
type Gsap = typeof import('gsap').gsap;

let core: Promise<Gsap> | undefined;
let splitText:
  Promise<{ gsap: Gsap; SplitText: typeof import('gsap/SplitText').SplitText }> | undefined;
let scrollTrigger:
  | Promise<{ gsap: Gsap; ScrollTrigger: typeof import('gsap/ScrollTrigger').ScrollTrigger }>
  | undefined;
let flip: Promise<{ gsap: Gsap; Flip: typeof import('gsap/Flip').Flip }> | undefined;

export function loadGsap(): Promise<Gsap> {
  core ??= import('gsap').then((m) => m.gsap);
  return core;
}

export function loadSplitText() {
  splitText ??= Promise.all([loadGsap(), import('gsap/SplitText')]).then(([gsap, m]) => {
    gsap.registerPlugin(m.SplitText);
    return { gsap, SplitText: m.SplitText };
  });
  return splitText;
}

export function loadScrollTrigger() {
  scrollTrigger ??= Promise.all([loadGsap(), import('gsap/ScrollTrigger')]).then(([gsap, m]) => {
    gsap.registerPlugin(m.ScrollTrigger);
    return { gsap, ScrollTrigger: m.ScrollTrigger };
  });
  return scrollTrigger;
}

export function loadFlip() {
  flip ??= Promise.all([loadGsap(), import('gsap/Flip')]).then(([gsap, m]) => {
    gsap.registerPlugin(m.Flip);
    return { gsap, Flip: m.Flip };
  });
  return flip;
}
