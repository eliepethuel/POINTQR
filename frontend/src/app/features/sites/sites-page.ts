import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { sitesCreate } from '../../api/fn/sites/sites-create';
import { sitesList } from '../../api/fn/sites/sites-list';
import { sitesPartialUpdate } from '../../api/fn/sites/sites-partial-update';
import type { Site } from '../../api/models/site';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll } from '../../shared/motion';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';
import { type MapSite, SiteMap } from './site-map';

interface SiteDraft {
  id?: string;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  radius_m: number;
  wifi: string;
}

@Component({
  selector: 'pq-sites-page',
  imports: [FormsModule, PageHeader, EmptyState, SiteMap, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './sites-page.html',
  styleUrl: './sites-page.css',
})
export class SitesPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  private readonly session = inject(Session);
  protected readonly canEdit = computed(() => this.session.hasRole('company_admin'));

  protected readonly sites = resource({ loader: () => this.api.invoke(sitesList, { limit: 200 }) });
  protected readonly draft = signal<SiteDraft | null>(null);
  protected readonly saving = signal(false);

  protected readonly mapSites = computed<readonly MapSite[]>(() => {
    const list = (this.sites.value()?.results ?? []).map((s) => ({
      id: s.id,
      name: s.name,
      latitude: +s.latitude,
      longitude: +s.longitude,
      radius_m: s.radius_m ?? 150,
    }));
    const d = this.draft();
    if (!d) return list;
    const preview = {
      id: d.id ?? 'nouveau',
      name: d.name || 'Nouveau site',
      latitude: d.latitude,
      longitude: d.longitude,
      radius_m: d.radius_m,
    };
    return [...list.filter((s) => s.id !== preview.id), preview];
  });
  protected readonly selectedId = computed(() =>
    this.draft() ? (this.draft()?.id ?? 'nouveau') : null,
  );

  protected startCreate(): void {
    this.draft.set({
      name: '',
      address: '',
      latitude: 5.3197,
      longitude: -4.0164,
      radius_m: 150,
      wifi: '',
    });
  }

  protected startEdit(site: Site): void {
    this.draft.set({
      id: site.id,
      name: site.name,
      address: site.address ?? '',
      latitude: +site.latitude,
      longitude: +site.longitude,
      radius_m: site.radius_m ?? 150,
      wifi: (site.allowed_wifi as string[] | undefined)?.join(', ') ?? '',
    });
  }

  protected patch(patch: Partial<SiteDraft>): void {
    this.draft.update((d) => (d ? { ...d, ...patch } : d));
  }

  protected onPicked(point: { latitude: number; longitude: number }): void {
    if (this.draft()) this.patch(point);
  }

  protected async save(): Promise<void> {
    const d = this.draft();
    if (!d || this.saving()) return;
    this.saving.set(true);
    const body = {
      name: d.name,
      address: d.address,
      latitude: d.latitude.toFixed(6),
      longitude: d.longitude.toFixed(6),
      radius_m: d.radius_m,
      allowed_wifi: d.wifi
        .split(',')
        .map((w) => w.trim())
        .filter(Boolean),
    };
    try {
      if (d.id) await this.api.invoke(sitesPartialUpdate, { id: d.id, body });
      else await this.api.invoke(sitesCreate, { body });
      this.toast.success('Site enregistré.');
      this.draft.set(null);
      this.sites.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.saving.set(false);
    }
  }
}
