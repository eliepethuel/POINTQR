import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { SplitTextDirective } from '../motion/split-text';

@Component({
  selector: 'pq-page-header',
  imports: [SplitTextDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="head">
      <div>
        @if (eyebrow()) {
          <p class="eyebrow">{{ eyebrow() }}</p>
        }
        <h1 pqSplitText splitBy="words">{{ title() }}</h1>
        @if (subtitle()) {
          <p class="subtitle">{{ subtitle() }}</p>
        }
      </div>
      <div class="actions"><ng-content /></div>
    </header>
  `,
  styles: `
    .head {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: flex-end;
      justify-content: space-between;
      margin-bottom: 24px;
    }
    .eyebrow {
      margin: 0 0 6px;
      font: 500 0.75rem var(--pq-font-mono);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--pq-highlight);
    }
    h1 {
      margin: 0;
      font: 700 clamp(1.6rem, 3vw, 2.2rem) / 1.1 var(--pq-font-display);
      letter-spacing: -0.02em;
      overflow: hidden;
    }
    .subtitle {
      margin: 6px 0 0;
      color: var(--pq-text-muted);
    }
    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
  `,
})
export class PageHeader {
  readonly title = input.required<string>();
  readonly eyebrow = input('');
  readonly subtitle = input('');
}
