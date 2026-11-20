import { ScrollingModule } from '@angular/cdk/scrolling';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  linkedSignal,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { Api } from '../../api/api';
import { agentsCreate } from '../../api/fn/agents/agents-create';
import { agentsDevices } from '../../api/fn/agents/agents-devices';
import { agentsList } from '../../api/fn/agents/agents-list';
import { agentsPartialUpdate } from '../../api/fn/agents/agents-partial-update';
import { agentsRotateBadge } from '../../api/fn/agents/agents-rotate-badge';
import { orgUnitsList } from '../../api/fn/org-units/org-units-list';
import { sitesList } from '../../api/fn/sites/sites-list';
import type { Agent } from '../../api/models/agent';
import type { AgentRequest } from '../../api/models/agent-request';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll, Shimmer } from '../../shared/motion';
import { Drawer } from '../../shared/ui/drawer';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

type Draft = Partial<AgentRequest> & { id?: string };

@Component({
  selector: 'pq-agents-page',
  imports: [
    FormsModule,
    RouterLink,
    ScrollingModule,
    PageHeader,
    Drawer,
    EmptyState,
    RevealOnScroll,
    Shimmer,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agents-page.html',
  styleUrl: './agents-page.css',
})
export class AgentsPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  protected readonly session = inject(Session);

  protected readonly search = signal('');
  private readonly debounced = signal('');
  private debounceTimer: ReturnType<typeof setTimeout> | undefined;

  protected readonly agents = resource({
    params: () => ({ search: this.debounced() }),
    loader: ({ params }) =>
      this.api.invoke(agentsList, { limit: 500, search: params.search || undefined }),
  });
  protected readonly sites = resource({ loader: () => this.api.invoke(sitesList, { limit: 500 }) });
  protected readonly units = resource({
    loader: () => this.api.invoke(orgUnitsList, { limit: 500 }),
  });

  protected readonly rows = computed<readonly Agent[]>(() => this.agents.value()?.results ?? []);
  protected readonly total = computed(() => this.agents.value()?.count ?? 0);
  protected readonly canEdit = computed(() => this.session.hasRole('company_admin', 'hr'));

  protected readonly selected = signal<Agent | null>(null);
  protected readonly devices = resource({
    params: () => this.selected()?.id,
    loader: ({ params }) => this.api.invoke(agentsDevices, { id: params }),
  });

  protected readonly draft = linkedSignal<Draft | null>(() => null);
  protected readonly saving = signal(false);

  protected onSearch(value: string): void {
    this.search.set(value);
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.debounced.set(value.trim()), 250);
  }

  protected open(agent: Agent): void {
    this.selected.set(agent);
  }

  protected edit(agent?: Agent): void {
    this.selected.set(null);
    this.draft.set(
      agent
        ? {
            id: agent.id,
            employee_number: agent.employee_number,
            last_name: agent.last_name,
            first_names: agent.first_names,
            job_title: agent.job_title ?? '',
            phone: agent.phone ?? '',
            email: agent.email ?? '',
            site: agent.site ?? null,
            org_unit: agent.org_unit ?? null,
          }
        : {
            employee_number: '',
            last_name: '',
            first_names: '',
            job_title: '',
            site: null,
            org_unit: null,
          },
    );
  }

  protected async save(): Promise<void> {
    const draft = this.draft();
    if (!draft || this.saving()) return;
    this.saving.set(true);
    try {
      const { id, ...body } = draft;
      if (id) await this.api.invoke(agentsPartialUpdate, { id, body });
      else await this.api.invoke(agentsCreate, { body: body as AgentRequest });
      this.toast.success(id ? 'Agent mis à jour.' : 'Agent créé.');
      this.draft.set(null);
      this.agents.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.saving.set(false);
    }
  }

  protected async rotateBadge(agent: Agent): Promise<void> {
    try {
      const updated = await this.api.invoke(agentsRotateBadge, { id: agent.id });
      this.selected.set(updated);
      this.toast.success("Nouveau badge généré : l'ancien n'est plus valable.");
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }

  protected patchDraft(patch: Partial<Draft>): void {
    this.draft.update((d) => (d ? { ...d, ...patch } : d));
  }

  protected trackById(_: number, agent: Agent): string {
    return agent.id;
  }
}
