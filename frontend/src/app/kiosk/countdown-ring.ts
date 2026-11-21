import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * 30-second countdown drawn as a rounded square around the kiosk QR card; turns coral in the
 * last 5 seconds. It stays outside the card so it never touches the QR quiet zone (a circle
 * crossed the card corners and hindered scanning).
 */
@Component({
  selector: 'pq-countdown-ring',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <rect class="track" x="4" y="4" width="92" height="92" rx="9" pathLength="100" />
      <rect
        class="bar"
        [class.ending]="remaining() <= 5"
        x="4"
        y="4"
        width="92"
        height="92"
        rx="9"
        pathLength="100"
        stroke-dasharray="100"
        [attr.stroke-dashoffset]="100 * (1 - fraction())"
      />
    </svg>
    <span class="seconds pq-mono" aria-live="off">{{ remaining() }} s</span>
  `,
  styles: `
    :host {
      position: absolute;
      inset: -6%;
      pointer-events: none;
    }
    svg {
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    rect {
      fill: none;
      stroke-width: 1.6;
    }
    .track {
      stroke: rgb(255 255 255 / 0.12);
    }
    .bar {
      stroke: var(--pq-highlight);
      stroke-linecap: round;
      transition:
        stroke 300ms,
        stroke-dashoffset 100ms linear;
    }
    .bar.ending {
      stroke: var(--pq-danger);
    }
    .seconds {
      position: absolute;
      left: 50%;
      bottom: -9%;
      translate: -50% 0;
      font-size: clamp(0.9rem, 1.6vw, 1.2rem);
      color: var(--pq-text-muted);
    }
  `,
})
export class CountdownRing {
  /** 1 → 0 over the 30-second window. */
  readonly fraction = input.required<number>();
  readonly remaining = input.required<number>();
}
