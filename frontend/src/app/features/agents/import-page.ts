import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api } from '../../api/api';
import { agentsImport } from '../../api/fn/agents/agents-import';
import { agentsImportTemplate } from '../../api/fn/agents/agents-import-template';
import type { ImportReport } from '../../api/models/import-report';
import { asProblem, problemMessage } from '../../core/http/problem';
import { CountUp } from '../../shared/motion';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

/** Excel/CSV import (EF-08): breathing drop zone, liquid progress, line-by-line error report. */
@Component({
  selector: 'pq-import-page',
  imports: [RouterLink, PageHeader, CountUp],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-page.html',
  styleUrl: './import-page.css',
})
export class ImportPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);

  protected readonly dragging = signal(false);
  protected readonly file = signal<File | null>(null);
  protected readonly progress = signal(0);
  protected readonly busy = signal(false);
  protected readonly report = signal<ImportReport | null>(null);

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.pick(file);
  }

  protected onPick(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) this.pick(file);
  }

  protected pick(file: File): void {
    this.file.set(file);
    this.report.set(null);
    void this.send(true);
  }

  /** Dry run first (validation only), then the real import once the report is clean. */
  protected async send(dryRun: boolean): Promise<void> {
    const file = this.file();
    if (!file || this.busy()) return;
    this.busy.set(true);
    this.progress.set(0);
    try {
      // The liquid fills to 35 % while uploading, then to 100 % once the server has validated.
      requestAnimationFrame(() => this.progress.set(35));
      this.report.set(await this.api.invoke(agentsImport, { body: { file, dry_run: dryRun } }));
      this.progress.set(100);
      if (!dryRun) this.toast.success('Import terminé.');
    } catch (err) {
      const problem = asProblem(err);
      const body = (err as { error?: ImportReport }).error;
      if (body && Array.isArray(body.line_errors)) this.report.set(body);
      else this.toast.error(problem?.detail ?? problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }

  protected async downloadTemplate(): Promise<void> {
    const res = await this.api.invoke$Response(agentsImportTemplate);
    const blob = res.body instanceof Blob ? res.body : new Blob([res.body as BlobPart]);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'modele-import-agents.xlsx';
    a.click();
    URL.revokeObjectURL(url);
  }
}
