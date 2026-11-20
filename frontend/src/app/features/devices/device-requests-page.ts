import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, resource } from '@angular/core';

import { Api } from '../../api/api';
import { deviceRequestsApprove } from '../../api/fn/device-requests/device-requests-approve';
import { deviceRequestsList } from '../../api/fn/device-requests/device-requests-list';
import { deviceRequestsReject } from '../../api/fn/device-requests/device-requests-reject';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll } from '../../shared/motion';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

/** Phone change requests to approve or reject (EF-10, RG-13). */
@Component({
  selector: 'pq-device-requests-page',
  imports: [DatePipe, PageHeader, EmptyState, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Changements de téléphone"
      eyebrow="Administration"
      subtitle="Un seul téléphone par agent : tout changement passe par le service RH."
    />
    <section class="pq-card">
      @for (req of requests.value()?.results ?? []; track req.id; let i = $index) {
        <article class="item" pqRevealOnScroll [revealIndex]="i">
          <div>
            <strong>{{ req.agent_name }}</strong>
            <p class="muted">
              {{ req.model || 'Téléphone' }} {{ req.os }} · demandé le
              {{ req.created_at | date: 'dd/MM/yyyy HH:mm' }}
            </p>
          </div>
          @if (req.status === 'pending') {
            <div class="actions">
              <button
                type="button"
                class="pq-btn pq-btn-primary pq-btn-sm"
                (click)="decide(req.id, true)"
              >
                Valider
              </button>
              <button
                type="button"
                class="pq-btn pq-btn-danger pq-btn-sm"
                (click)="decide(req.id, false)"
              >
                Refuser
              </button>
            </div>
          } @else {
            <span
              class="pq-badge"
              [class.pq-badge-success]="req.status === 'approved'"
              [class.pq-badge-danger]="req.status === 'rejected'"
            >
              {{ req.status === 'approved' ? 'validée' : 'refusée' }}
            </span>
          }
        </article>
      } @empty {
        <pq-empty-state
          title="Aucune demande"
          message="Les demandes apparaissent quand un agent se connecte depuis un nouveau téléphone."
        />
      }
    </section>
  `,
  styles: `
    .item {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 14px 4px;
      border-bottom: 1px solid var(--pq-border);
    }
    .muted {
      margin: 4px 0 0;
      color: var(--pq-text-muted);
      font-size: 0.875rem;
    }
    .actions {
      display: flex;
      gap: 8px;
    }
  `,
})
export class DeviceRequestsPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  protected readonly requests = resource({
    loader: () => this.api.invoke(deviceRequestsList, { limit: 200 }),
  });

  protected async decide(id: string, approve: boolean): Promise<void> {
    try {
      await this.api.invoke(approve ? deviceRequestsApprove : deviceRequestsReject, { id });
      this.toast.success(approve ? 'Nouveau téléphone lié.' : 'Demande refusée.');
      this.requests.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }
}
