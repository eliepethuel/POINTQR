import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  inject,
  resource,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import type { EChartsCoreOption } from 'echarts/core';

import { Api } from '../../api/api';
import { dashboardToday } from '../../api/fn/dashboard/dashboard-today';
import type { Recent } from '../../api/models/recent';
import { Session } from '../../core/auth/session';
import { DashboardSocket, type LiveEvent } from '../../core/realtime/dashboard-socket';
import { EChart } from '../../shared/charts/echart';
import { CountUp, loadFlip, MotionService, RevealOnScroll, Spotlight } from '../../shared/motion';
import { PageHeader } from '../../shared/ui/page-header';
import { type MapSite, SiteMap } from '../sites/site-map';

interface FeedItem extends Recent {
  readonly fresh?: boolean;
}

const REFUSAL_LABELS: Record<string, string> = {
  TOKEN_EXPIRED: 'QR expiré',
  TOKEN_REPLAYED: 'QR rejoué',
  TOKEN_INVALID: 'QR invalide',
  OUT_OF_ZONE: 'Hors zone',
  DEVICE_MISMATCH: 'Appareil non autorisé',
  DEVICE_NOT_BOUND: 'Téléphone non activé',
  MOCK_LOCATION: 'Position simulée',
  WIFI_NOT_ALLOWED: 'Wi-Fi non autorisé',
  BADGE_REVOKED: 'Badge remplacé',
  KIOSK_REVOKED: 'Borne révoquée',
  DUPLICATE: 'Doublon',
};

/** Real-time dashboard (EF-25): bento grid, live feed, arrivals, services ranking, sites map. */
@Component({
  selector: 'pq-dashboard-page',
  imports: [DatePipe, RouterLink, PageHeader, CountUp, RevealOnScroll, Spotlight, EChart, SiteMap],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard-page.html',
  styleUrl: './dashboard-page.css',
})
export class DashboardPage {
  private readonly api = inject(Api);
  private readonly motion = inject(MotionService);
  protected readonly session = inject(Session);
  protected readonly socket = inject(DashboardSocket);
  protected readonly refusalLabels = REFUSAL_LABELS;

  protected readonly data = resource({ loader: () => this.api.invoke(dashboardToday) });
  protected readonly feed = signal<readonly FeedItem[]>([]);
  private readonly feedList = viewChild<ElementRef<HTMLElement>>('feedList');
  private reloadTimer: ReturnType<typeof setTimeout> | undefined;

  protected readonly kpis = computed(() => this.data.value()?.kpis);
  protected readonly punctuality = computed(() => {
    const k = this.kpis();
    // Nobody arrived yet (or a day off): there is nothing to measure, not « 100 % ».
    return k && k.present ? `${Math.round(((k.present - k.late) / k.present) * 100)} %` : '—';
  });

  protected readonly mapSites = computed<readonly MapSite[]>(() =>
    (this.data.value()?.sites ?? []).map((s) => ({
      id: s.id,
      name: `${s.name} · ${s.present} présents`,
      latitude: s.latitude,
      longitude: s.longitude,
      radius_m: s.radius_m,
    })),
  );

  protected readonly arrivalsChart = computed<EChartsCoreOption>(() => {
    const hours = this.data.value()?.arrivals_by_hour ?? [];
    return {
      grid: { left: 32, right: 8, top: 16, bottom: 24 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: hours.map((h) => `${h.hour} h`),
        axisLine: { lineStyle: { color: '#9A9CB0' } },
      },
      yAxis: {
        type: 'value',
        minInterval: 1, // a number of people: no 0.2 / 0.4 ticks
        splitLine: { lineStyle: { color: 'rgba(154,156,176,0.15)' } },
        axisLabel: { color: '#9A9CB0' },
      },
      series: [
        {
          type: 'bar',
          data: hours.map((h) => h.count),
          itemStyle: { color: '#7C5CFF', borderRadius: [6, 6, 0, 0] },
        },
      ],
    };
  });

  protected readonly unitsChart = computed<EChartsCoreOption>(() => {
    const units = [...(this.data.value()?.units ?? [])].slice(0, 8).reverse();
    return {
      grid: { left: 140, right: 40, top: 8, bottom: 16 },
      tooltip: { trigger: 'item', formatter: '{b} : {c} %' },
      xAxis: { type: 'value', max: 100, show: false },
      yAxis: {
        type: 'category',
        data: units.map((u) => u.name),
        axisLabel: { color: '#9A9CB0', width: 130, overflow: 'truncate' },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'bar',
          data: units.map((u) => u.punctuality),
          label: { show: true, position: 'right', formatter: '{c} %', color: '#F4F4F6' },
          itemStyle: { color: '#3DDC97', borderRadius: 6 },
          barWidth: 14,
        },
      ],
    };
  });

  constructor() {
    const off = this.socket.subscribe((event) => this.onEvent(event));
    inject(DestroyRef).onDestroy(() => {
      off();
      clearTimeout(this.reloadTimer);
    });
  }

  protected feedItems(): readonly FeedItem[] {
    return this.feed().length ? this.feed() : (this.data.value()?.recent ?? []);
  }

  private onEvent(event: LiveEvent): void {
    if (event.event !== 'checkin.accepted' && event.event !== 'checkin.refused') return;
    const p = event.payload;
    const item: FeedItem = {
      id: String(p['id']),
      agent_name: String(p['agent_name'] ?? 'Inconnu'),
      site: (p['site'] as string | null) ?? null,
      direction: String(p['direction'] ?? ''),
      mode: String(p['mode'] ?? ''),
      at: String(p['at']),
      result: String(p['result']),
      refusal_code: String(p['refusal_code'] ?? ''),
      fresh: true,
    };
    void this.animateFeed(() =>
      this.feed.set([item, ...this.feedItems().map((i) => ({ ...i, fresh: false }))].slice(0, 25)),
    );
    // KPIs are recomputed server side; batch reloads when check-ins pour in at 07:30.
    clearTimeout(this.reloadTimer);
    this.reloadTimer = setTimeout(() => this.data.reload(), 2500);
  }

  /** New check-ins slide in at the top while the others move down (GSAP Flip). */
  private async animateFeed(update: () => void): Promise<void> {
    const list = this.feedList()?.nativeElement;
    if (!list || this.motion.reduced()) {
      update();
      return;
    }
    const { Flip } = await loadFlip();
    const state = Flip.getState(list.children);
    update();
    requestAnimationFrame(() => Flip.from(state, { duration: 0.5, ease: 'expo.out' }));
  }
}
