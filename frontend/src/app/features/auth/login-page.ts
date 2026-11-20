import { ChangeDetectionStrategy, Component, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import QRCode from 'qrcode';

import { type LoginStep, Session, homeFor } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { Magnetic } from '../../shared/motion';
import { OtpInput } from './otp-input';

@Component({
  selector: 'pq-login-page',
  imports: [FormsModule, OtpInput, Magnetic],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login-page.html',
  styleUrl: './login-page.css',
})
export class LoginPage {
  private readonly session = inject(Session);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly otp = viewChild(OtpInput);

  protected companyCode = this.session.rememberedCompanyCode();
  protected username = '';
  protected password = '';

  protected readonly step = signal<LoginStep | null>(null);
  protected readonly qrDataUrl = signal<string | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly shake = signal(false);

  protected async submit(): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      const step = await this.session.login(this.companyCode, this.username, this.password);
      if (step.kind === 'authenticated') {
        await this.goHome();
        return;
      }
      if (step.kind === 'mfa_setup') {
        this.qrDataUrl.set(
          await QRCode.toDataURL(step.otpauthUrl, {
            margin: 1,
            width: 220,
            color: { dark: '#0E0F1A', light: '#FFFFFF' },
          }),
        );
      }
      this.step.set(step);
    } catch (err) {
      this.fail(problemMessage(err, 'Connexion impossible.'));
    } finally {
      this.busy.set(false);
    }
  }

  protected async verify(code: string): Promise<void> {
    const step = this.step();
    if (!step || step.kind === 'authenticated' || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.session.verifyMfa(step.mfaToken, code);
      await this.goHome();
    } catch (err) {
      this.fail(problemMessage(err, 'Code incorrect.'));
      this.otp()?.reset();
    } finally {
      this.busy.set(false);
    }
  }

  protected back(): void {
    this.step.set(null);
    this.qrDataUrl.set(null);
    this.error.set(null);
  }

  private fail(message: string): void {
    this.error.set(message);
    this.shake.set(false);
    requestAnimationFrame(() => this.shake.set(true));
    setTimeout(() => this.shake.set(false), 500);
  }

  private async goHome(): Promise<void> {
    const next = this.route.snapshot.queryParamMap.get('suite');
    await this.router.navigateByUrl(next && next.startsWith('/') ? next : homeFor(this.session));
  }
}
