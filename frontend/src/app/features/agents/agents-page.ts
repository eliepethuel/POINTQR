import { ScrollingModule } from '@angular/cdk/scrolling';
import { DatePipe } from '@angular/common';
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
import { agentsInvite } from '../../api/fn/agents/agents-invite';
import { agentsInviteAll } from '../../api/fn/agents/agents-invite-all';
import { agentsList } from '../../api/fn/agents/agents-list';
import { agentsPartialUpdate } from '../../api/fn/agents/agents-partial-update';
import { agentsRotateBadge } from '../../api/fn/agents/agents-rotate-badge';
import { orgUnitsList } from '../../api/fn/org-units/org-units-list';
import { sitesList } from '../../api/fn/sites/sites-list';
import type { Agent } from '../../api/models/agent';
import type { AgentRequest } from '../../api/models/agent-request';
import type { Invitation } from '../../api/models/invitation';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { QrCanvas } from '../../kiosk/qr-canvas';
import { RevealOnScroll, Shimmer } from '../../shared/motion';
import { Drawer } from '../../shared/ui/drawer';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

type Draft = Partial<AgentRequest> & { id?: string };

@Component({
  selector: 'pq-agents-page',
  imports: [
    DatePipe,
    FormsModule,
    QrCanvas,
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
  /** Last invitation made from the open agent panel (link shown as a QR, EF-09). */
  protected readonly invitation = linkedSignal<Invitation | null>(() => {
    this.selected();
    return null;
  });
  protected readonly inviting = signal(false);
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

  /** Combined state of the app access: account (EF-09) then phone binding (RG-13). */
  protected access(agent: Agent): 'bound' | 'active' | 'invited' | 'none' {
    if (agent.account === 'active') return agent.has_device ? 'bound' : 'active';
    return agent.account === 'invited' ? 'invited' : 'none';
  }

  protected accessLabel(agent: Agent): string {
    return {
      bound: 'Compte activé, téléphone lié.',
      active: 'Compte activé : le téléphone sera lié à la première connexion.',
      invited: "Invitation envoyée : l'agent doit choisir son mot de passe depuis le lien.",
      none: "Pas encore d'accès : invitez l'agent (e-mail ou QR à scanner).",
    }[this.access(agent)];
  }

  protected async invite(agent: Agent): Promise<void> {
    this.inviting.set(true);
    try {
      const inv = await this.api.invoke(agentsInvite, { id: agent.id });
      // Update the agent first: the invitation panel resets when the selection changes.
      this.selected.set({ ...agent, account: 'invited' });
      this.invitation.set(inv);
      this.toast.success(
        inv.sent_to ? `Invitation envoyée à ${inv.sent_to}.` : 'Lien d’activation prêt.',
      );
      this.agents.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.inviting.set(false);
    }
  }

  protected async inviteAll(): Promise<void> {
    this.inviting.set(true);
    try {
      const r = await this.api.invoke(agentsInviteAll);
      this.toast.success(
        r.invited
          ? `${r.invited} agent(s) invité(s) : ${r.emailed} par e-mail, ${r.without_email} sans e-mail (lien à remettre depuis leur fiche).`
          : 'Tous les agents actifs ont déjà un accès ou une invitation en cours.',
      );
      this.agents.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.inviting.set(false);
    }
  }

  protected async copy(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      this.toast.success('Lien copié.');
    } catch {
      this.toast.error('Copie impossible : sélectionnez le lien à la main.');
    }
  }

  protected patchDraft(patch: Partial<Draft>): void {
    this.draft.update((d) => (d ? { ...d, ...patch } : d));
  }

  protected trackById(_: number, agent: Agent): string {
    return agent.id;
  }
}
