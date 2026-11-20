import { ChangeDetectionStrategy, Component, inject, resource, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { usersCreate } from '../../api/fn/users/users-create';
import { usersList } from '../../api/fn/users/users-list';
import { usersPartialUpdate } from '../../api/fn/users/users-partial-update';
import type { RoleEnum } from '../../api/models/role-enum';
import type { User } from '../../api/models/user';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll } from '../../shared/motion';
import { Drawer } from '../../shared/ui/drawer';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

export const ROLE_LABELS: Record<RoleEnum, string> = {
  company_admin: 'Administrateur',
  hr: 'RH',
  manager: 'Manager',
  agent: 'Agent',
  auditor: 'Auditeur',
};

/** Accounts and roles (EF-40). Accounts are deactivated, never deleted. */
@Component({
  selector: 'pq-users-page',
  imports: [FormsModule, PageHeader, Drawer, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Utilisateurs"
      eyebrow="Administration"
      subtitle="Comptes et rôles (cumulables)."
    >
      <button type="button" class="pq-btn pq-btn-primary" (click)="openNew()">
        Nouveau compte
      </button>
    </pq-page-header>
    <section class="pq-card">
      <table class="pq-table">
        <thead>
          <tr>
            <th>Identifiant</th>
            <th>Nom</th>
            <th>Rôles</th>
            <th>État</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (user of users.value()?.results ?? []; track user.id; let i = $index) {
            <tr pqRevealOnScroll [revealIndex]="i">
              <td class="pq-mono">{{ user.username }}</td>
              <td>{{ user.display_name || '—' }}</td>
              <td>
                @for (role of user.roles; track role) {
                  <span class="pq-badge pq-badge-accent">{{ labels[role] }}</span>
                }
              </td>
              <td>
                <span class="pq-badge" [class.pq-badge-success]="user.is_active">{{
                  user.is_active ? 'actif' : 'désactivé'
                }}</span>
              </td>
              <td>
                <button type="button" class="pq-btn pq-btn-sm" (click)="edit(user)">
                  Modifier
                </button>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </section>

    <pq-drawer
      [open]="open()"
      [title]="editingId() ? 'Modifier le compte' : 'Nouveau compte'"
      (closed)="open.set(false)"
    >
      <form class="form" (ngSubmit)="save()">
        <label class="pq-field"
          ><span class="pq-label">Identifiant</span>
          <input
            class="pq-input"
            name="username"
            [(ngModel)]="username"
            [disabled]="!!editingId()"
            required
        /></label>
        <label class="pq-field"
          ><span class="pq-label">Nom affiché</span>
          <input class="pq-input" name="display_name" [(ngModel)]="displayName"
        /></label>
        <label class="pq-field"
          ><span class="pq-label">{{
            editingId() ? 'Nouveau mot de passe (optionnel)' : 'Mot de passe'
          }}</span>
          <input
            class="pq-input"
            type="password"
            name="password"
            [(ngModel)]="password"
            minlength="10"
            autocomplete="new-password"
        /></label>
        <fieldset class="roles">
          <legend class="pq-label">Rôles</legend>
          @for (role of allRoles; track role) {
            <label
              ><input
                type="checkbox"
                [checked]="roles().includes(role)"
                (change)="toggleRole(role)"
              />
              {{ labels[role] }}</label
            >
          }
        </fieldset>
        @if (editingId()) {
          <label><input type="checkbox" name="active" [(ngModel)]="active" /> Compte actif</label>
        }
        <button type="submit" class="pq-btn pq-btn-primary" [disabled]="roles().length === 0">
          Enregistrer
        </button>
      </form>
    </pq-drawer>
  `,
  styles: `
    .form {
      display: grid;
      gap: 14px;
    }
    .roles {
      display: grid;
      gap: 8px;
      border: 0;
      padding: 0;
      margin: 0;
    }
    td .pq-badge {
      margin-right: 4px;
    }
  `,
})
export class UsersPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  protected readonly labels = ROLE_LABELS;
  protected readonly allRoles = Object.keys(ROLE_LABELS) as RoleEnum[];
  protected readonly users = resource({ loader: () => this.api.invoke(usersList, { limit: 500 }) });

  protected readonly open = signal(false);
  protected readonly editingId = signal<string | null>(null);
  protected readonly roles = signal<RoleEnum[]>(['agent']);
  protected username = '';
  protected displayName = '';
  protected password = '';
  protected active = true;

  protected openNew(): void {
    this.editingId.set(null);
    this.username = this.displayName = this.password = '';
    this.roles.set(['agent']);
    this.open.set(true);
  }

  protected edit(user: User): void {
    this.editingId.set(user.id);
    this.username = user.username;
    this.displayName = user.display_name ?? '';
    this.password = '';
    this.active = user.is_active ?? true;
    this.roles.set([...user.roles]);
    this.open.set(true);
  }

  protected toggleRole(role: RoleEnum): void {
    this.roles.update((list) =>
      list.includes(role) ? list.filter((r) => r !== role) : [...list, role],
    );
  }

  protected async save(): Promise<void> {
    const id = this.editingId();
    try {
      if (id) {
        await this.api.invoke(usersPartialUpdate, {
          id,
          body: {
            display_name: this.displayName,
            roles: this.roles(),
            is_active: this.active,
            ...(this.password ? { password: this.password } : {}),
          },
        });
      } else {
        await this.api.invoke(usersCreate, {
          body: {
            username: this.username,
            display_name: this.displayName,
            password: this.password,
            roles: this.roles(),
          },
        });
      }
      this.toast.success('Compte enregistré.');
      this.open.set(false);
      this.users.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }
}
