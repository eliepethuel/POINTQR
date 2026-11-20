import { A11yModule } from '@angular/cdk/a11y';
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

/** Side panel that springs in from the right; traps focus and closes on Escape or backdrop. */
@Component({
  selector: 'pq-drawer',
  imports: [A11yModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(document:keydown.escape)': 'open() && closed.emit()' },
  template: `
    @if (open()) {
      <div class="backdrop" (click)="closed.emit()" aria-hidden="true"></div>
      <aside
        class="panel"
        role="dialog"
        aria-modal="true"
        [attr.aria-label]="title()"
        cdkTrapFocus
        [cdkTrapFocusAutoCapture]="true"
      >
        <header>
          <h2>{{ title() }}</h2>
          <button
            type="button"
            class="pq-btn pq-btn-ghost pq-btn-icon"
            (click)="closed.emit()"
            aria-label="Fermer"
          >
            ×
          </button>
        </header>
        <div class="body"><ng-content /></div>
      </aside>
    }
  `,
  styles: `
    .backdrop {
      position: fixed;
      inset: 0;
      z-index: 900;
      background: rgb(0 0 0 / 0.45);
      animation: fade 240ms ease both;
    }
    .panel {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      z-index: 901;
      width: min(520px, 100vw);
      display: flex;
      flex-direction: column;
      background: var(--pq-surface);
      border-left: 1px solid var(--pq-border);
      box-shadow: var(--pq-shadow);
      animation: slide 560ms var(--pq-ease-spring) both;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 20px;
      border-bottom: 1px solid var(--pq-border);
    }
    h2 {
      margin: 0;
      font: 600 1.15rem var(--pq-font-display);
    }
    .body {
      padding: 20px;
      overflow: auto;
      flex: 1;
    }
    @keyframes slide {
      from {
        transform: translateX(100%);
      }
    }
    @keyframes fade {
      from {
        opacity: 0;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .panel,
      .backdrop {
        animation: none;
      }
    }
  `,
})
export class Drawer {
  readonly open = input(false);
  readonly title = input('');
  readonly closed = output();
}
