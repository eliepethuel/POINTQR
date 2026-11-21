import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { Api } from '../../api/api';
import { authActivate } from '../../api/fn/auth/auth-activate';
import { authLogin } from '../../api/fn/auth/auth-login';
import { authLogout } from '../../api/fn/auth/auth-logout';
import { authMfaVerify } from '../../api/fn/auth/auth-mfa-verify';
import { authRefresh } from '../../api/fn/auth/auth-refresh';
import type { AuthResponse } from '../../api/models/auth-response';
import type { Me } from '../../api/models/me';
import type { RoleEnum } from '../../api/models/role-enum';

const COMPANY_CODE_KEY = 'pq.companyCode';

export type Role = RoleEnum;
export type LoginStep =
  | { kind: 'authenticated' }
  | { kind: 'mfa_required'; mfaToken: string }
  | { kind: 'mfa_setup'; mfaToken: string; otpauthUrl: string; secret: string };

/**
 * Session state. The access token lives in memory only (never in storage, ADR on auth);
 * the refresh token is an HttpOnly cookie the browser sends to /api/v1/auth/ only.
 */
@Injectable({ providedIn: 'root' })
export class Session {
  private readonly api = inject(Api);
  private readonly router = inject(Router);

  private readonly accessToken = signal<string | null>(null);
  readonly user = signal<Me | null>(null);
  readonly ready = signal(false);

  readonly isAuthenticated = computed(() => this.user() !== null);
  readonly roles = computed<readonly Role[]>(() => this.user()?.roles ?? []);
  readonly isSuperadmin = computed(() => this.user()?.is_superadmin ?? false);
  readonly company = computed(() => this.user()?.company ?? null);

  private refreshing: Promise<boolean> | null = null;

  token(): string | null {
    return this.accessToken();
  }

  hasRole(...roles: Role[]): boolean {
    const held = this.roles();
    return roles.some((r) => held.includes(r));
  }

  rememberedCompanyCode(): string {
    try {
      return localStorage.getItem(COMPANY_CODE_KEY) ?? '';
    } catch {
      return '';
    }
  }

  async login(companyCode: string, username: string, password: string): Promise<LoginStep> {
    const res = await this.api.invoke(authLogin, {
      body: { company_code: companyCode.trim().toUpperCase(), username, password },
    });
    try {
      localStorage.setItem(COMPANY_CODE_KEY, companyCode.trim().toUpperCase());
    } catch {
      /* storage unavailable: the code is simply not remembered */
    }
    return this.handle(res);
  }

  /**
   * First password of an invited agent (EF-09). Returns false when the account needs the
   * usual sign-in (privileged roles, second factor).
   */
  async activate(companyCode: string, token: string, password: string): Promise<boolean> {
    const code = companyCode.trim().toUpperCase();
    const res = await this.api.invoke(authActivate, {
      body: { company_code: code, token, password },
    });
    try {
      localStorage.setItem(COMPANY_CODE_KEY, code);
    } catch {
      /* storage unavailable: the code is simply not remembered */
    }
    if (res.step !== 'authenticated') return false;
    this.handle(res);
    return true;
  }

  async verifyMfa(mfaToken: string, code: string): Promise<void> {
    const res = await this.api.invoke(authMfaVerify, { body: { mfa_token: mfaToken, code } });
    this.handle(res);
  }

  /** Silent refresh, shared by concurrent callers (single flight). */
  refresh(): Promise<boolean> {
    this.refreshing ??= this.api
      .invoke(authRefresh)
      .then((res) => {
        this.handle(res);
        return true;
      })
      .catch(() => {
        this.clear();
        return false;
      })
      .finally(() => {
        this.refreshing = null;
      });
    return this.refreshing;
  }

  /** Called once at start-up: restores the session from the refresh cookie when present. */
  async restore(): Promise<void> {
    try {
      await this.refresh();
    } finally {
      this.ready.set(true);
    }
  }

  async logout(): Promise<void> {
    try {
      await this.api.invoke(authLogout);
    } catch {
      /* already logged out server side */
    }
    this.clear();
    await this.router.navigateByUrl('/connexion');
  }

  clear(): void {
    this.accessToken.set(null);
    this.user.set(null);
  }

  private handle(res: AuthResponse): LoginStep {
    if (res.step === 'authenticated' && res.access && res.user) {
      this.accessToken.set(res.access);
      this.user.set(res.user);
      return { kind: 'authenticated' };
    }
    if (res.step === 'mfa_setup') {
      return {
        kind: 'mfa_setup',
        mfaToken: res.mfa_token ?? '',
        otpauthUrl: res.otpauth_url ?? '',
        secret: res.secret ?? '',
      };
    }
    return { kind: 'mfa_required', mfaToken: res.mfa_token ?? '' };
  }
}

/** Where a freshly logged-in user lands, according to their roles. */
export function homeFor(session: Session): string {
  if (session.isSuperadmin()) return '/plateforme';
  if (session.hasRole('company_admin', 'hr', 'manager', 'auditor')) return '/app/tableau-de-bord';
  return '/agent';
}
