import { A11yModule } from '@angular/cdk/a11y';
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';

import { Session } from '../../core/auth/session';
import { ThemeService } from '../../core/theme/theme';
import type { NavItem } from './nav';

interface Command {
  readonly label: string;
  readonly hint: string;
  readonly run: () => void;
}

/** ⌘K / Ctrl+K palette: jump to any page or run an action, keyboard first. */
@Component({
  selector: 'pq-command-palette',
  imports: [A11yModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(document:keydown)': 'onKey($event)' },
  template: `
    @if (open()) {
      <div class="backdrop" (click)="close()" aria-hidden="true"></div>
      <div
        class="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Palette de commandes"
        cdkTrapFocus
        [cdkTrapFocusAutoCapture]="true"
      >
        <input
          class="search"
          placeholder="Aller à… (agents, rapports, thème)"
          aria-label="Rechercher une commande"
          [value]="query()"
          (input)="query.set($any($event.target).value); active.set(0)"
        />
        <ul role="listbox" aria-label="Commandes">
          @for (cmd of results(); track cmd.label; let i = $index) {
            <li
              role="option"
              [attr.aria-selected]="i === active()"
              [class.active]="i === active()"
              (click)="execute(cmd)"
              (keydown.enter)="execute(cmd)"
              tabindex="-1"
              (mouseenter)="active.set(i)"
              [style.animation-delay.ms]="i * 25"
            >
              <span>{{ cmd.label }}</span><small>{{ cmd.hint }}</small>
            </li>
          } @empty {
            <li class="empty">Aucun résultat</li>
          }
        </ul>
        <p class="keys">
          <kbd>↑</kbd><kbd>↓</kbd> naviguer · <kbd>Entrée</kbd> ouvrir · <kbd>Échap</kbd> fermer
        </p>
      </div>
    }
  `,
  styles: `
    .backdrop {
      position: fixed;
      inset: 0;
      z-index: 1100;
      background: rgb(0 0 0 / 0.5);
      animation: fade 200ms ease both;
    }
    .palette {
      position: fixed;
      z-index: 1101;
      top: 14vh;
      left: 50%;
      width: min(620px, calc(100vw - 32px));
      translate: -50% 0;
      border-radius: 20px;
      background: var(--pq-glass);
      backdrop-filter: blur(22px);
      border: 1px solid var(--pq-border);
      box-shadow: var(--pq-shadow);
      overflow: hidden;
      animation: drop 420ms var(--pq-ease-spring) both;
    }
    .search {
      width: 100%;
      padding: 18px 20px;
      border: 0;
      border-bottom: 1px solid var(--pq-border);
      background: transparent;
      color: var(--pq-text);
      font: 500 1.05rem var(--pq-font-body);
      outline: none;
    }
    ul {
      list-style: none;
      margin: 0;
      padding: 8px;
      max-height: 50vh;
      overflow: auto;
    }
    li {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 11px 12px;
      border-radius: 12px;
      cursor: pointer;
      animation: item 300ms var(--pq-ease-out-expo) both;
    }
    li.active {
      background: rgb(124 92 255 / 0.18);
    }
    small {
      color: var(--pq-text-muted);
    }
    .empty {
      color: var(--pq-text-muted);
      cursor: default;
    }
    .keys {
      margin: 0;
      padding: 10px 16px;
      font-size: 0.75rem;
      color: var(--pq-text-muted);
      border-top: 1px solid var(--pq-border);
    }
    kbd {
      padding: 1px 6px;
      border-radius: 5px;
      background: var(--pq-surface-2);
      font-family: var(--pq-font-mono);
    }
    @keyframes drop {
      from {
        transform: translateY(-16px) scale(0.97);
        opacity: 0;
      }
    }
    @keyframes item {
      from {
        transform: translateY(6px);
        opacity: 0;
      }
    }
    @keyframes fade {
      from {
        opacity: 0;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .palette,
      li,
      .backdrop {
        animation: none;
      }
    }
  `,
})
export class CommandPalette {
  readonly items = input.required<readonly NavItem[]>();
  private readonly router = inject(Router);
  private readonly session = inject(Session);
  private readonly theme = inject(ThemeService);

  protected readonly open = signal(false);
  protected readonly query = signal('');
  protected readonly active = signal(0);

  private readonly commands = computed<Command[]>(() => [
    ...this.items().map((item) => ({
      label: item.label,
      hint: 'Page',
      run: () => void this.router.navigateByUrl(item.path),
    })),
    { label: 'Basculer le thème clair / sombre', hint: 'Action', run: () => this.theme.toggle() },
    {
      label: 'Ouvrir le mode borne',
      hint: 'Action',
      run: () => void this.router.navigateByUrl('/kiosk'),
    },
    { label: 'Se déconnecter', hint: 'Action', run: () => void this.session.logout() },
  ]);

  protected readonly results = computed(() => {
    const q = this.query().trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    const all = this.commands();
    if (!q) return all;
    return all.filter((c) =>
      c.label.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').includes(q),
    );
  });

  toggle(): void {
    this.open.update((v) => !v);
    this.query.set('');
    this.active.set(0);
  }

  protected close(): void {
    this.open.set(false);
  }

  protected execute(cmd: Command): void {
    this.close();
    cmd.run();
  }

  protected onKey(event: KeyboardEvent): void {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      this.toggle();
      return;
    }
    if (!this.open()) return;
    const count = this.results().length;
    if (event.key === 'Escape') this.close();
    else if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.active.set((this.active() + 1) % Math.max(1, count));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.active.set((this.active() - 1 + count) % Math.max(1, count));
    } else if (event.key === 'Enter') {
      const cmd = this.results()[this.active()];
      if (cmd) this.execute(cmd);
    }
  }
}
