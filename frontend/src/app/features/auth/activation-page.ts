import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { Api } from '../../api/api';
import { authActivationCheck } from '../../api/fn/auth/auth-activation-check';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';

/**
 * EF-09: the agent opens the link of their invitation (e-mail or QR shown by HR), chooses a
 * password and lands in the agent app, where the phone is bound at the first check-in.
 */
@Component({
  selector: 'pq-activation-page',
  imports: [FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './login-page.css',
  template: `
    <main class="login pq-grain">
      <div class="pq-aurora" aria-hidden="true"></div>
      <section class="card pq-glass pq-pop-in" aria-labelledby="activation-title">
        <a class="brand" href="/">Point<span>QR</span></a>
        @if (info.isLoading()) {
          <p class="lead">Vérification du lien…</p>
        } @else if (info.error() || !hasLink) {
          <h1 id="activation-title">Lien inutilisable</h1>
          <p class="pq-error-text" role="alert">{{ linkError() }}</p>
          <a class="pq-btn" routerLink="/connexion">Aller à la connexion</a>
        } @else if (info.value(); as i) {
          <h1 id="activation-title">Bonjour {{ i.first_name }}</h1>
          <p class="lead">
            Choisissez votre mot de passe pour activer votre accès à PointQR chez
            {{ i.company }}.
          </p>
          <p class="lead">
            Votre identifiant : <strong class="pq-mono">{{ i.username }}</strong>
          </p>
          <form class="form" (ngSubmit)="submit()" #form="ngForm">
            <label class="pq-field">
              <span class="pq-label">Mot de passe</span>
              <input
                class="pq-input glow"
                type="password"
                name="password"
                [(ngModel)]="password"
                autocomplete="new-password"
                minlength="10"
                required
              />
            </label>
            <label class="pq-field">
              <span class="pq-label">Confirmez le mot de passe</span>
              <input
                class="pq-input glow"
                type="password"
                name="confirm"
                [(ngModel)]="confirm"
                autocomplete="new-password"
                required
              />
            </label>
            <p class="lead">10 caractères au moins, pas uniquement des chiffres.</p>
            @if (error(); as message) {
              <p class="pq-error-text" role="alert">{{ message }}</p>
            }
            <button
              class="pq-btn pq-btn-highlight submit"
              type="submit"
              [disabled]="busy() || !form.valid"
            >
              {{ busy() ? 'Activation…' : 'Activer mon accès' }}
            </button>
          </form>
        }
      </section>
    </main>
  `,
})
export class ActivationPage {
  private readonly api = inject(Api);
  private readonly session = inject(Session);
  private readonly router = inject(Router);
  private readonly query = inject(ActivatedRoute).snapshot.queryParamMap;

  private readonly company = this.query.get('entreprise') ?? '';
  private readonly token = this.query.get('jeton') ?? '';
  protected readonly hasLink = Boolean(this.company && this.token);
  protected password = '';
  protected confirm = '';
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly info = resource({
    loader: () =>
      this.hasLink
        ? this.api.invoke(authActivationCheck, { entreprise: this.company, jeton: this.token })
        : Promise.reject(new Error('missing')),
  });
  protected readonly linkError = computed(() =>
    this.hasLink
      ? problemMessage(this.info.error(), 'Ce lien est invalide ou expiré.')
      : 'Ce lien est incomplet : ouvrez celui reçu par e-mail ou scannez le QR du service RH.',
  );

  protected async submit(): Promise<void> {
    if (this.password !== this.confirm) {
      this.error.set('Les deux mots de passe ne correspondent pas.');
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      const signedIn = await this.session.activate(this.company, this.token, this.password);
      await this.router.navigateByUrl(signedIn ? '/agent' : '/connexion');
    } catch (err) {
      this.error.set(problemMessage(err, 'Activation impossible.'));
    } finally {
      this.busy.set(false);
    }
  }
}
