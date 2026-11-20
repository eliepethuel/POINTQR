import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Illustrated empty state: an animated QR-like glyph (CSS only) and a message. */
@Component({
  selector: 'pq-empty-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="empty pq-pop-in">
      <div class="glyph" aria-hidden="true">
        @for (cell of cells; track $index) {
          <span [style.animation-delay.ms]="cell * 90" [class.on]="cell % 3 !== 1"></span>
        }
      </div>
      <p class="title">{{ title() }}</p>
      @if (message()) {
        <p class="message">{{ message() }}</p>
      }
      <ng-content />
    </div>
  `,
  styles: `
    .empty {
      display: grid;
      justify-items: center;
      gap: 8px;
      padding: 48px 16px;
      text-align: center;
    }
    .glyph {
      display: grid;
      grid-template-columns: repeat(3, 14px);
      gap: 5px;
      margin-bottom: 12px;
    }
    .glyph span {
      width: 14px;
      height: 14px;
      border-radius: 3px;
      background: var(--pq-surface-2);
    }
    .glyph span.on {
      background: var(--pq-accent);
      animation: blink 2.4s ease-in-out infinite;
    }
    @keyframes blink {
      50% {
        opacity: 0.25;
        transform: scale(0.8);
      }
    }
    .title {
      margin: 0;
      font: 600 1.05rem var(--pq-font-display);
    }
    .message {
      margin: 0;
      color: var(--pq-text-muted);
      max-width: 420px;
    }
    @media (prefers-reduced-motion: reduce) {
      .glyph span.on {
        animation: none;
      }
    }
  `,
})
export class EmptyState {
  readonly title = input.required<string>();
  readonly message = input('');
  protected readonly cells = [0, 1, 2, 3, 4, 5, 6, 7, 8];
}
