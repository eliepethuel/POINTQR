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
import { orgUnitsCreate } from '../../api/fn/org-units/org-units-create';
import { orgUnitsTree } from '../../api/fn/org-units/org-units-tree';
import type { OrgUnitKindEnum as KindEnum } from '../../api/models/org-unit-kind-enum';
import type { OrgTreeNode } from '../../api/models/org-tree-node';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';
import { OrgTree } from './org-tree';

@Component({
  selector: 'pq-org-page',
  imports: [FormsModule, PageHeader, EmptyState, OrgTree],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Organigramme"
      eyebrow="Organisation"
      subtitle="Directions, services et équipes."
    >
      @if (canEdit()) {
        <button type="button" class="pq-btn pq-btn-primary" (click)="adding.set(true)">
          Nouvelle unité
        </button>
      }
    </pq-page-header>

    @if (adding()) {
      <form class="pq-card form pq-pop-in" (ngSubmit)="create()">
        <label class="pq-field"
          ><span class="pq-label">Nom</span>
          <input class="pq-input" name="name" required [(ngModel)]="name"
        /></label>
        <label class="pq-field"
          ><span class="pq-label">Type</span>
          <select class="pq-select" name="kind" [(ngModel)]="kind">
            <option value="direction">Direction</option>
            <option value="service">Service</option>
            <option value="team">Équipe</option>
          </select></label
        >
        <label class="pq-field"
          ><span class="pq-label">Rattachée à</span>
          <select class="pq-select" name="parent" [(ngModel)]="parent">
            <option [ngValue]="null">— (racine)</option>
            @for (unit of flat(); track unit.id) {
              <option [ngValue]="unit.id">{{ unit.label }}</option>
            }
          </select></label
        >
        <div class="actions">
          <button type="submit" class="pq-btn pq-btn-primary" [disabled]="!name">Créer</button>
          <button type="button" class="pq-btn pq-btn-ghost" (click)="adding.set(false)">
            Annuler
          </button>
        </div>
      </form>
    }

    <section class="pq-card">
      @if (tree.value(); as roots) {
        @if (roots.length) {
          <pq-org-tree [nodes]="roots" />
        } @else {
          <pq-empty-state
            title="Organigramme vide"
            message="Créez la direction générale puis ses services."
          />
        }
      }
    </section>
  `,
  styles: `
    .form {
      display: grid;
      gap: 12px;
      margin-bottom: 16px;
      max-width: 520px;
    }
    .actions {
      display: flex;
      gap: 8px;
    }
  `,
})
export class OrgPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  private readonly session = inject(Session);
  protected readonly canEdit = computed(() => this.session.hasRole('company_admin'));
  protected readonly tree = resource({ loader: () => this.api.invoke(orgUnitsTree) });
  protected readonly adding = signal(false);
  protected name = '';
  protected kind: KindEnum = 'service';
  protected parent: string | null = null;

  protected readonly flat = computed(() => {
    const out: { id: string; label: string }[] = [];
    const walk = (nodes: readonly OrgTreeNode[], depth: number) => {
      for (const n of nodes) {
        out.push({ id: n.id, label: `${'— '.repeat(depth)}${n.name}` });
        walk((n.children ?? []) as unknown as OrgTreeNode[], depth + 1);
      }
    };
    walk(this.tree.value() ?? [], 0);
    return out;
  });

  protected async create(): Promise<void> {
    try {
      await this.api.invoke(orgUnitsCreate, {
        body: { name: this.name, kind: this.kind, parent: this.parent },
      });
      this.toast.success('Unité créée.');
      this.name = '';
      this.adding.set(false);
      this.tree.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }
}
