import { ChangeDetectionStrategy, Component, computed, inject, resource } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api } from '../../api/api';
import { agentsList } from '../../api/fn/agents/agents-list';
import { sitesList } from '../../api/fn/sites/sites-list';
import { Session } from '../../core/auth/session';
import { RevealOnScroll } from '../../shared/motion';
import { PageHeader } from '../../shared/ui/page-header';

/** Start-up checklist (EF-04: sites → schedules → agents → kiosks, operational in under a day). */
@Component({
  selector: 'pq-dashboard-page',
  imports: [RouterLink, PageHeader, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header title="Tableau de bord" [eyebrow]="session.company()?.legal_name ?? ''" />
    <section class="pq-card setup">
      <h2>Démarrage</h2>
      <ol>
        @for (step of steps(); track step.label; let i = $index) {
          <li pqRevealOnScroll [revealIndex]="i" [class.done]="step.done">
            <span class="num pq-mono">{{ step.done ? '✓' : i + 1 }}</span>
            <a [routerLink]="step.link">{{ step.label }}</a>
          </li>
        }
      </ol>
    </section>
  `,
  styles: `
    h2 {
      margin: 0 0 12px;
      font: 600 1.1rem var(--pq-font-display);
    }
    ol {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 10px;
    }
    li {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .num {
      display: grid;
      place-items: center;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: var(--pq-surface-2);
    }
    li.done .num {
      background: var(--pq-success);
      color: #0e0f1a;
    }
    a {
      color: var(--pq-text);
    }
  `,
})
export class DashboardPage {
  private readonly api = inject(Api);
  protected readonly session = inject(Session);
  private readonly sites = resource({ loader: () => this.api.invoke(sitesList, { limit: 1 }) });
  private readonly agents = resource({ loader: () => this.api.invoke(agentsList, { limit: 1 }) });

  protected readonly steps = computed(() => [
    {
      label: 'Créer les sites et leur rayon de géorepérage',
      link: '/app/sites',
      done: (this.sites.value()?.count ?? 0) > 0,
    },
    {
      label: 'Importer les agents depuis Excel',
      link: '/app/agents/import',
      done: (this.agents.value()?.count ?? 0) > 0,
    },
    { label: 'Définir l’organigramme', link: '/app/organisation', done: false },
    { label: 'Créer les comptes RH et managers', link: '/app/utilisateurs', done: false },
  ]);
}
