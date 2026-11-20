import { ChangeDetectionStrategy, Component, Injectable, inject, signal } from '@angular/core';

export type ToastKind = 'success' | 'error' | 'info';
export interface Toast {
  readonly id: number;
  readonly kind: ToastKind;
  readonly message: string;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  private next = 1;
  readonly toasts = signal<readonly Toast[]>([]);

  show(message: string, kind: ToastKind = 'info', durationMs = 4200): void {
    const toast: Toast = { id: this.next++, kind, message };
    this.toasts.update((list) => [...list.slice(-3), toast]);
    setTimeout(() => this.dismiss(toast.id), durationMs);
  }

  success(message: string): void {
    this.show(message, 'success');
  }

  error(message: string): void {
    this.show(message, 'error', 6000);
  }

  dismiss(id: number): void {
    this.toasts.update((list) => list.filter((t) => t.id !== id));
  }
}

/** Toasts spring in from the bottom right; announced politely to screen readers. */
@Component({
  selector: 'pq-toaster',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="toaster" aria-live="polite" aria-atomic="false">
      @for (toast of toasts.toasts(); track toast.id) {
        <div class="toast" [attr.data-kind]="toast.kind" role="status">
          <span class="dot" aria-hidden="true"></span>
          <p>{{ toast.message }}</p>
          <button
            type="button"
            class="close"
            (click)="toasts.dismiss(toast.id)"
            aria-label="Fermer"
          >
            ×
          </button>
        </div>
      }
    </div>
  `,
  styles: `
    .toaster {
      position: fixed;
      right: 16px;
      bottom: 16px;
      z-index: 1000;
      display: grid;
      gap: 10px;
      width: min(380px, calc(100vw - 32px));
    }
    .toast {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 14px;
      background: var(--pq-glass);
      backdrop-filter: blur(16px);
      border: 1px solid var(--pq-border);
      box-shadow: var(--pq-shadow);
      animation: toast-in 520ms var(--pq-ease-spring) both;
    }
    p {
      margin: 0;
      flex: 1;
      font-size: 0.875rem;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--pq-accent);
      flex: none;
    }
    [data-kind='success'] .dot {
      background: var(--pq-success);
    }
    [data-kind='error'] .dot {
      background: var(--pq-danger);
    }
    .close {
      background: none;
      border: 0;
      color: var(--pq-text-muted);
      font-size: 1.2rem;
      cursor: pointer;
    }
    @keyframes toast-in {
      from {
        opacity: 0;
        transform: translateY(24px) scale(0.96);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .toast {
        animation: none;
      }
    }
  `,
})
export class Toaster {
  protected readonly toasts = inject(ToastService);
}
