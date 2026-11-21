import { DatePipe } from '@angular/common';
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
import { requestsCancel } from '../../api/fn/requests/requests-cancel';
import { requestsCreate$FormData as requestsCreateFormData } from '../../api/fn/requests/requests-create-form-data';
import { requestsDecide } from '../../api/fn/requests/requests-decide';
import { requestsList } from '../../api/fn/requests/requests-list';
import type { Request } from '../../api/models/request';
import type { RequestCategoryEnum } from '../../api/models/request-category-enum';
import type { RequestKindEnum } from '../../api/models/request-kind-enum';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll } from '../../shared/motion';
import { Drawer } from '../../shared/ui/drawer';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

const STATUS: Record<string, string> = {
  pending_manager: 'Chez le manager',
  pending_hr: 'Chez le RH',
  approved: 'Validée',
  rejected: 'Refusée',
  cancelled: 'Annulée',
};
const CATEGORY: Record<string, string> = {
  late: 'Retard',
  absence: 'Absence',
  early_leave: 'Départ anticipé',
  missing_checkin: 'Oubli de pointage',
  wrong_checkin: 'Pointage erroné',
  overtime: 'Heures supplémentaires',
};

interface Draft {
  kind: RequestKindEnum;
  category: RequestCategoryEnum;
  target_date: string;
  reason: string;
  requested_direction: 'in' | 'out';
  requested_time: string;
  file: File | null;
}

/** Justifications and corrections with the manager → HR circuit (EF-29 to EF-31). */
@Component({
  selector: 'pq-requests-page',
  imports: [DatePipe, FormsModule, PageHeader, Drawer, EmptyState, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './requests-page.html',
  styleUrl: './requests-page.css',
})
export class RequestsPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  protected readonly session = inject(Session);
  protected readonly statusLabels = STATUS;
  protected readonly categoryLabels = CATEGORY;
  protected readonly categories = Object.keys(CATEGORY) as RequestCategoryEnum[];

  protected readonly filter = signal<'pending' | ''>('pending');
  protected readonly list = resource({
    params: () => this.filter(),
    loader: ({ params }) =>
      this.api.invoke(requestsList, { status: params || undefined, limit: 200 }),
  });
  protected readonly isAgent = computed(() => !!this.session.user()?.agent_id);
  protected readonly draft = signal<Draft | null>(null);
  protected readonly dragging = signal(false);
  protected readonly busy = signal(false);
  protected comment = '';

  protected openNew(): void {
    this.draft.set({
      kind: 'justification',
      category: 'late',
      target_date: new Date().toISOString().slice(0, 10),
      reason: '',
      requested_direction: 'out',
      requested_time: '',
      file: null,
    });
  }

  protected patch(patch: Partial<Draft>): void {
    this.draft.update((d) => (d ? { ...d, ...patch } : d));
  }

  protected onCategory(category: RequestCategoryEnum): void {
    const kind: RequestKindEnum =
      category === 'missing_checkin' || category === 'wrong_checkin'
        ? 'correction'
        : category === 'overtime'
          ? 'overtime'
          : 'justification';
    this.patch({ category, kind });
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.patch({ file });
  }

  protected onFile(event: Event): void {
    this.patch({ file: (event.target as HTMLInputElement).files?.[0] ?? null });
  }

  protected async submit(): Promise<void> {
    const d = this.draft();
    if (!d || this.busy()) return;
    this.busy.set(true);
    try {
      const time =
        d.kind === 'correction' && d.requested_time
          ? new Date(`${d.target_date}T${d.requested_time}`).toISOString()
          : undefined;
      await this.api.invoke(requestsCreateFormData, {
        body: {
          kind: d.kind,
          category: d.category,
          target_date: d.target_date,
          reason: d.reason,
          ...(time ? { requested_time: time, requested_direction: d.requested_direction } : {}),
          ...(d.file ? { attachment: d.file } : {}),
        },
      });
      this.toast.success('Demande envoyée.');
      this.draft.set(null);
      this.list.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }

  /** Request being decided (its buttons are disabled meanwhile). */
  protected readonly deciding = signal<string | null>(null);

  protected async decide(req: Request, approve: boolean): Promise<void> {
    if (this.deciding()) return;
    this.deciding.set(req.id);
    try {
      const fresh = await this.api.invoke(requestsDecide, {
        id: req.id,
        body: { approve, comment: this.comment },
      });
      this.comment = '';
      this.toast.success(approve ? 'Demande validée.' : 'Demande refusée.');
      this.replace(fresh);
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.deciding.set(null);
    }
  }

  /**
   * Shows the server's answer at once, then refreshes the list. A load already running (filter
   * changed meanwhile) may have read the request half-way through the decision, and
   * ``reload()`` is ignored while a load runs: without this the card could stay stale.
   */
  private replace(fresh: Request): void {
    this.list.update((page) =>
      page ? { ...page, results: page.results.map((r) => (r.id === fresh.id ? fresh : r)) } : page,
    );
    const refresh = () => {
      if (this.list.isLoading()) setTimeout(refresh, 200);
      else {
        // The fresh copy stays shown until the refreshed list arrives.
        this.list.reload();
      }
    };
    setTimeout(refresh, 0);
  }

  protected async cancel(req: Request): Promise<void> {
    try {
      this.replace(await this.api.invoke(requestsCancel, { id: req.id }));
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }
}
