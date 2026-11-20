import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { kiosksList } from '../../api/fn/kiosks/kiosks-list';
import { kiosksPairingCode } from '../../api/fn/kiosks/kiosks-pairing-code';
import { kiosksRevoke } from '../../api/fn/kiosks/kiosks-revoke';
import { kiosksRotateKey } from '../../api/fn/kiosks/kiosks-rotate-key';
import { sitesList } from '../../api/fn/sites/sites-list';
import type { Kiosk } from '../../api/models/kiosk';
import type { PairingCode } from '../../api/models/pairing-code';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll } from '../../shared/motion';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

/** Kiosks: pairing by code, online status, revocation and key rotation (EF-42). */
@Component({
  selector: 'pq-kiosks-page',
  imports: [DatePipe, FormsModule, PageHeader, EmptyState, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Bornes"
      eyebrow="Administration"
      subtitle="Tablettes fixées à l'entrée des sites."
    >
      @if (canEdit()) {
        <button type="button" class="pq-btn pq-btn-primary" (click)="adding.set(true)">
          Nouvelle borne
        </button>
      }
    </pq-page-header>

    @if (adding()) {
      <form class="pq-card form pq-pop-in" (ngSubmit)="createCode()">
        <div class="pq-grid-2">
          <label class="pq-field"
            ><span class="pq-label">Site</span>
            <select class="pq-select" name="site" [(ngModel)]="siteId" required>
              @for (site of sites.value()?.results ?? []; track site.id) {
                <option [value]="site.id">{{ site.name }}</option>
              }
            </select></label
          >
          <label class="pq-field"
            ><span class="pq-label">Nom de la borne</span>
            <input
              class="pq-input"
              name="name"
              [(ngModel)]="name"
              required
              placeholder="Entrée principale"
          /></label>
        </div>
        <button type="submit" class="pq-btn pq-btn-primary" [disabled]="!siteId || !name">
          Générer le code
        </button>
        @if (code(); as c) {
          <div class="code pq-pop-in">
            <p class="muted">
              Sur la tablette, ouvrez <code class="pq-mono">/kiosk</code> et saisissez :
            </p>
            <p class="digits pq-mono" aria-label="Code d'appairage">{{ c.code }}</p>
            <p class="muted">
              Code entreprise <strong class="pq-mono">{{ session.company()?.code }}</strong> ·
              valable jusqu'à {{ c.expires_at | date: 'HH:mm' }}
            </p>
          </div>
        }
      </form>
    }

    <section class="grid">
      @for (kiosk of kiosks.value()?.results ?? []; track kiosk.id; let i = $index) {
        <article class="pq-card kiosk" pqRevealOnScroll [revealIndex]="i">
          <header>
            <span
              class="status"
              [class.on]="kiosk.online"
              [class.revoked]="kiosk.status === 'revoked'"
              aria-hidden="true"
            ></span>
            <h3>{{ kiosk.name }}</h3>
          </header>
          <p class="muted">{{ kiosk.site_name }}</p>
          <p class="muted small">
            @if (kiosk.status === 'revoked') {
              Révoquée
            } @else if (kiosk.online) {
              En ligne
            } @else {
              Hors ligne depuis {{ kiosk.last_seen_at | date: 'dd/MM HH:mm' }}
            }
            · clé v{{ kiosk.key_version }}
            @if (kiosk.pending_offline) {
              · <strong>{{ kiosk.pending_offline }}</strong> en attente
            }
          </p>
          @if (canEdit() && kiosk.status !== 'revoked') {
            <div class="actions">
              <button type="button" class="pq-btn pq-btn-sm" (click)="rotate(kiosk)">
                Régénérer la clé
              </button>
              <button type="button" class="pq-btn pq-btn-sm pq-btn-danger" (click)="revoke(kiosk)">
                Révoquer
              </button>
            </div>
          }
        </article>
      } @empty {
        <pq-empty-state
          title="Aucune borne"
          message="Générez un code d'appairage puis saisissez-le sur la tablette."
        />
      }
    </section>
  `,
  styles: `
    .form {
      display: grid;
      gap: 14px;
      margin-bottom: 20px;
      max-width: 720px;
    }
    .code {
      text-align: center;
      padding: 16px;
      border-radius: 16px;
      background: var(--pq-surface-2);
    }
    .digits {
      margin: 6px 0;
      font-size: 3rem;
      letter-spacing: 0.3em;
      color: var(--pq-highlight);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
    }
    .kiosk header {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    h3 {
      margin: 0;
      font: 600 1rem var(--pq-font-display);
    }
    .status {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--pq-text-muted);
    }
    .status.on {
      background: var(--pq-success);
    }
    .status.revoked {
      background: var(--pq-danger);
    }
    .muted {
      color: var(--pq-text-muted);
      margin: 6px 0 0;
    }
    .small {
      font-size: 0.8125rem;
    }
    .actions {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }
  `,
})
export class KiosksPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  protected readonly session = inject(Session);
  protected readonly canEdit = computed(() => this.session.hasRole('company_admin'));
  protected readonly kiosks = resource({
    loader: () => this.api.invoke(kiosksList, { limit: 100 }),
  });
  protected readonly sites = resource({ loader: () => this.api.invoke(sitesList, { limit: 100 }) });
  protected readonly adding = signal(false);
  protected readonly code = signal<PairingCode | null>(null);
  protected siteId = '';
  protected name = '';
  constructor() {
    const poll = setInterval(() => this.kiosks.reload(), 20_000);
    inject(DestroyRef).onDestroy(() => clearInterval(poll));
  }

  protected async createCode(): Promise<void> {
    try {
      this.code.set(
        await this.api.invoke(kiosksPairingCode, { body: { site: this.siteId, name: this.name } }),
      );
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }

  protected async rotate(kiosk: Kiosk): Promise<void> {
    await this.run(
      this.api.invoke(kiosksRotateKey, { id: kiosk.id }),
      'Nouvelle clé : la borne la récupère automatiquement.',
    );
  }

  protected async revoke(kiosk: Kiosk): Promise<void> {
    if (!confirm(`Révoquer « ${kiosk.name} » ? Ses QR codes seront refusés immédiatement.`)) return;
    await this.run(this.api.invoke(kiosksRevoke, { id: kiosk.id }), 'Borne révoquée.');
  }

  private async run(action: Promise<unknown>, message: string): Promise<void> {
    try {
      await action;
      this.toast.success(message);
      this.kiosks.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }
}
