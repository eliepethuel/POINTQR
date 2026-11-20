import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterNextRender,
  computed,
  input,
  output,
  signal,
  viewChildren,
} from '@angular/core';

/** Six boxes that snap together as digits are typed; supports paste and backspace navigation. */
@Component({
  selector: 'pq-otp-input',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="otp"
      [class.complete]="complete()"
      [class.pq-shake]="shake()"
      role="group"
      aria-label="Code à 6 chiffres"
    >
      @for (i of indexes; track i) {
        <input
          #box
          class="box"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          [attr.aria-label]="'Chiffre ' + (i + 1)"
          [value]="digits()[i]"
          (input)="onInput(i, $event)"
          (keydown)="onKey(i, $event)"
          (paste)="onPaste($event)"
          [disabled]="disabled()"
        />
      }
    </div>
  `,
  styles: `
    .otp {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 10px;
      transition: gap var(--pq-dur-slow) var(--pq-ease-out-back);
    }
    .otp.complete {
      gap: 4px;
    }
    .box {
      width: 100%;
      aspect-ratio: 1 / 1.15;
      text-align: center;
      font: 700 1.6rem var(--pq-font-mono);
      border-radius: 12px;
      border: 1px solid var(--pq-border);
      background: var(--pq-surface);
      color: var(--pq-text);
      transition:
        transform var(--pq-dur-base) var(--pq-ease-out-back),
        border-color var(--pq-dur-base);
    }
    .box:focus {
      outline: none;
      border-color: var(--pq-accent);
      transform: translateY(-3px);
      box-shadow: 0 0 0 4px rgb(124 92 255 / 0.22);
    }
    .complete .box {
      border-color: var(--pq-success);
    }
  `,
})
export class OtpInput {
  readonly disabled = input(false);
  readonly shake = input(false);
  readonly completed = output<string>();

  protected readonly indexes = [0, 1, 2, 3, 4, 5];
  protected readonly digits = signal<string[]>(['', '', '', '', '', '']);
  protected readonly complete = computed(() => this.digits().every((d) => d !== ''));
  private readonly boxes = viewChildren<ElementRef<HTMLInputElement>>('box');

  constructor() {
    afterNextRender(() => this.focus(0));
  }

  reset(): void {
    this.digits.set(['', '', '', '', '', '']);
    this.focus(0);
  }

  protected onInput(index: number, event: Event): void {
    const target = event.target as HTMLInputElement;
    const typed = target.value.replace(/\D/g, '');
    // Fast typing, autofill (one-time-code) or keyboards that insert several digits at once:
    // spread them over the following boxes.
    const chars = typed.length > 1 ? typed.slice(-(6 - index)).split('') : [typed];
    target.value = chars[0] ?? '';
    this.digits.update((list) =>
      list.map((d, i) => (i >= index && i < index + chars.length ? (chars[i - index] ?? '') : d)),
    );
    this.emitIfComplete();
    if (typed) this.focus(index + chars.length);
  }

  protected onKey(index: number, event: KeyboardEvent): void {
    if (event.key === 'Backspace' && !this.digits()[index]) {
      this.set(index - 1, '');
      this.focus(index - 1);
    } else if (event.key === 'ArrowLeft') {
      this.focus(index - 1);
    } else if (event.key === 'ArrowRight') {
      this.focus(index + 1);
    }
  }

  protected onPaste(event: ClipboardEvent): void {
    const text = (event.clipboardData?.getData('text') ?? '').replace(/\D/g, '').slice(0, 6);
    if (!text) return;
    event.preventDefault();
    const next = this.indexes.map((i) => text[i] ?? '');
    this.digits.set(next);
    this.emitIfComplete();
    this.focus(Math.min(text.length, 5));
  }

  private set(index: number, digit: string): void {
    if (index < 0 || index > 5) return;
    this.digits.update((list) => list.map((d, i) => (i === index ? digit : d)));
    this.emitIfComplete();
  }

  private emitIfComplete(): void {
    if (this.complete()) this.completed.emit(this.digits().join(''));
  }

  private focus(index: number): void {
    const box = this.boxes()[Math.max(0, Math.min(5, index))];
    box?.nativeElement.focus();
    box?.nativeElement.select();
  }
}
