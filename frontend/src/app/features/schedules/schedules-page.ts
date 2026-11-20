import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { holidaysCreate } from '../../api/fn/holidays/holidays-create';
import { holidaysDestroy } from '../../api/fn/holidays/holidays-destroy';
import { holidaysList } from '../../api/fn/holidays/holidays-list';
import { schedulesCreate } from '../../api/fn/schedules/schedules-create';
import { schedulesList } from '../../api/fn/schedules/schedules-list';
import { schedulesPartialUpdate } from '../../api/fn/schedules/schedules-partial-update';
import type { Holiday } from '../../api/models/holiday';
import type { Schedule } from '../../api/models/schedule';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll } from '../../shared/motion';
import { Drawer } from '../../shared/ui/drawer';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

const DAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
const MONTHS = [
  'janv.',
  'févr.',
  'mars',
  'avr.',
  'mai',
  'juin',
  'juil.',
  'août',
  'sept.',
  'oct.',
  'nov.',
  'déc.',
];

interface Draft {
  id?: string;
  name: string;
  weekdays: number[];
  start_time: string;
  end_time: string;
  break_minutes: number;
  late_tolerance_min: number;
  early_tolerance_min: number;
}

/** Schedules with tolerances (EF-12, EF-13) and the public holidays calendar (EF-15). */
@Component({
  selector: 'pq-schedules-page',
  imports: [DatePipe, FormsModule, PageHeader, Drawer, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './schedules-page.html',
  styleUrl: './schedules-page.css',
})
export class SchedulesPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  private readonly session = inject(Session);
  protected readonly canEdit = computed(() => this.session.hasRole('company_admin', 'hr'));
  protected readonly days = DAYS;
  protected readonly months = MONTHS;

  protected readonly schedules = resource({
    loader: () => this.api.invoke(schedulesList, { limit: 100 }),
  });
  protected readonly year = signal(new Date().getFullYear());
  protected readonly holidays = resource({
    params: () => this.year(),
    loader: ({ params }) => this.api.invoke(holidaysList, { year: params, limit: 200 }),
  });
  /** Holidays grouped by month for the calendar view. */
  protected readonly byMonth = computed(() => {
    const groups: Holiday[][] = MONTHS.map(() => []);
    for (const h of this.holidays.value()?.results ?? [])
      groups[new Date(h.date).getMonth()]?.push(h);
    return groups;
  });

  protected readonly draft = signal<Draft | null>(null);
  protected newHoliday = { date: '', label: '' };

  protected edit(s?: Schedule): void {
    this.draft.set(
      s
        ? {
            id: s.id,
            name: s.name,
            weekdays: [...(s.weekdays ?? [])],
            start_time: s.start_time?.slice(0, 5) ?? '07:30',
            end_time: s.end_time?.slice(0, 5) ?? '16:30',
            break_minutes: s.break_minutes ?? 60,
            late_tolerance_min: s.late_tolerance_min ?? 10,
            early_tolerance_min: s.early_tolerance_min ?? 10,
          }
        : {
            name: '',
            weekdays: [0, 1, 2, 3, 4],
            start_time: '07:30',
            end_time: '16:30',
            break_minutes: 60,
            late_tolerance_min: 10,
            early_tolerance_min: 10,
          },
    );
  }

  protected toggleDay(day: number): void {
    this.draft.update((d) =>
      d
        ? {
            ...d,
            weekdays: d.weekdays.includes(day)
              ? d.weekdays.filter((x) => x !== day)
              : [...d.weekdays, day].sort(),
          }
        : d,
    );
  }

  protected patch(patch: Partial<Draft>): void {
    this.draft.update((d) => (d ? { ...d, ...patch } : d));
  }

  protected async save(): Promise<void> {
    const d = this.draft();
    if (!d) return;
    const { id, ...body } = d;
    try {
      if (id) await this.api.invoke(schedulesPartialUpdate, { id, body });
      else await this.api.invoke(schedulesCreate, { body });
      this.toast.success('Horaire enregistré.');
      this.draft.set(null);
      this.schedules.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }

  protected async addHoliday(): Promise<void> {
    try {
      await this.api.invoke(holidaysCreate, {
        body: { date: this.newHoliday.date, label: this.newHoliday.label },
      });
      this.newHoliday = { date: '', label: '' };
      this.holidays.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }

  protected async removeHoliday(h: Holiday): Promise<void> {
    try {
      await this.api.invoke(holidaysDestroy, { id: h.id });
      this.holidays.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }

  protected night(s: Schedule): boolean {
    return !!s.is_night;
  }
}
