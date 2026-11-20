import { Directive, booleanAttribute, input } from '@angular/core';

/**
 * Skeleton placeholder while data loads: `<p [pqShimmer]="loading()">…</p>`.
 * Announces the busy state to assistive technologies.
 */
@Directive({
  selector: '[pqShimmer]',
  host: {
    '[class.pq-shimmer]': 'pqShimmer()',
    '[attr.aria-busy]': 'pqShimmer() || null',
  },
})
export class Shimmer {
  readonly pqShimmer = input(true, { transform: booleanAttribute });
}
