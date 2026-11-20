import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  viewChild,
} from '@angular/core';
import type { ECharts, EChartsCoreOption } from 'echarts/core';

import { MotionService } from '../motion/motion-service';

/** Minimal ECharts wrapper: lazy-loaded, drawn with its built-in entrance animation, resizes. */
@Component({
  selector: 'pq-echart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="chart" role="img" [attr.aria-label]="label()"></div>`,
  styles: `
    .chart {
      width: 100%;
      height: 100%;
      min-height: 220px;
    }
  `,
})
export class EChart {
  readonly options = input.required<EChartsCoreOption>();
  readonly label = input('Graphique');
  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private readonly motion = inject(MotionService);
  private chart: ECharts | null = null;

  constructor() {
    const destroyRef = inject(DestroyRef);
    let observer: ResizeObserver | undefined;
    afterNextRender(async () => {
      const [core, charts, components, renderers] = await Promise.all([
        import('echarts/core'),
        import('echarts/charts'),
        import('echarts/components'),
        import('echarts/renderers'),
      ]);
      core.use([
        charts.BarChart,
        charts.LineChart,
        components.GridComponent,
        components.TooltipComponent,
        renderers.SVGRenderer,
      ]);
      this.chart = core.init(this.host().nativeElement, undefined, { renderer: 'svg' });
      this.render();
      observer = new ResizeObserver(() => this.chart?.resize());
      observer.observe(this.host().nativeElement);
    });
    effect(() => {
      this.options();
      this.render();
    });
    destroyRef.onDestroy(() => {
      observer?.disconnect();
      this.chart?.dispose();
    });
  }

  private render(): void {
    if (!this.chart) return;
    this.chart.setOption(
      {
        animation: !this.motion.reduced(),
        animationDuration: 900,
        animationEasing: 'cubicOut',
        ...this.options(),
      },
      true,
    );
  }
}
