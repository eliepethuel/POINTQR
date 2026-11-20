import { ChangeDetectionStrategy, Component, input } from '@angular/core';

const RADIUS = 46;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Circular 30-second countdown around the kiosk QR; turns coral in the last 5 seconds. */
@Component({
  selector: 'pq-countdown-ring',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <circle class="track" cx="50" cy="50" [attr.r]="radius" />
      <circle
        class="bar"
        [class.ending]="remaining() <= 5"
        cx="50"
        cy="50"
        [attr.r]="radius"
        [attr.stroke-dasharray]="circumference"
        [attr.stroke-dashoffset]="circumference * (1 - fraction())"
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
      transform: rotate(-90deg);
    }
    circle {
      fill: none;
      stroke-width: 2.2;
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
      right: 4%;
      bottom: 2%;
      font-size: clamp(0.9rem, 1.6vw, 1.2rem);
      color: var(--pq-text-muted);
    }
  `,
})
export class CountdownRing {
  /** 1 → 0 over the 30-second window. */
  readonly fraction = input.required<number>();
  readonly remaining = input.required<number>();
  protected readonly radius = RADIUS;
  protected readonly circumference = CIRCUMFERENCE;
}
