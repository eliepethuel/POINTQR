"""Business rules RG-01 to RG-15 as pure functions (no database, no clock).

A ``WorkDay`` is always *computed* from the accepted check-ins of one agent for one work date,
so it can be recomputed at any time (CDC section 10). All datetimes here are timezone-aware and
expressed in the company's timezone.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum

#: Grace after the planned end before a missing exit makes the day incomplete (RG-05).
NIGHT_SHIFT_CUTOFF = time(12, 0)
OVERTIME_THRESHOLD_DEFAULT = 30
DUPLICATE_WINDOW = timedelta(minutes=2)


class DayStatus(StrEnum):
    PENDING = "pending"  # the working day is not over yet
    PRESENT = "present"
    LATE = "late"
    LATE_JUSTIFIED = "late_justified"
    ABSENT = "absent"
    ABSENT_JUSTIFIED = "absent_justified"
    INCOMPLETE = "incomplete"
    HOLIDAY = "holiday"
    OFF = "off"


@dataclass(frozen=True, slots=True)
class DaySchedule:
    """Planned day for one agent. ``works`` is False on non-working days."""

    works: bool
    start: datetime | None = None
    end: datetime | None = None
    break_minutes: int = 0
    late_tolerance_min: int = 10
    early_tolerance_min: int = 10
    overtime_threshold_min: int = OVERTIME_THRESHOLD_DEFAULT

    @property
    def planned_minutes(self) -> int:
        if not (self.works and self.start and self.end):
            return 0
        return max(0, int((self.end - self.start).total_seconds() // 60) - self.break_minutes)


@dataclass(frozen=True, slots=True)
class Punch:
    """An accepted check-in as seen by the rules."""

    at: datetime
    direction: str  # in | out | break_out | break_in
    id: str = ""
    corrects: str | None = None


@dataclass(frozen=True, slots=True)
class Justifications:
    late: bool = False
    absence: bool = False
    overtime_validated: bool = False


@dataclass(slots=True)
class WorkDayResult:
    status: DayStatus
    first_in: datetime | None = None
    last_out: datetime | None = None
    late_minutes: int = 0
    early_leave_minutes: int = 0
    worked_minutes: int = 0
    overtime_minutes: int = 0
    overtime_validated: bool = False
    incomplete: bool = False
    notes: list[str] = field(default_factory=list)


# --- RG-15: which work date a punch belongs to ---------------------------------------------------


def work_date_for(moment: datetime, *, night_shift: bool) -> date:
    """A night shift (e.g. 20:00 → 06:00) belongs to the date it started (RG-15)."""
    if night_shift and moment.time() < NIGHT_SHIFT_CUTOFF:
        return (moment - timedelta(days=1)).date()
    return moment.date()


# --- RG-07: direction ------------------------------------------------------------------------------


def next_direction(accepted_today: Sequence[Punch]) -> str:
    """First punch of the day is an entry, then exit, alternately (RG-07)."""
    regular = [p for p in accepted_today if p.direction in ("in", "out")]
    return "in" if len(regular) % 2 == 0 else "out"


# --- RG-06: double scan ----------------------------------------------------------------------------


def is_duplicate(previous: datetime | None, current: datetime) -> bool:
    return previous is not None and abs(current - previous) < DUPLICATE_WINDOW


# --- RG-02 / RG-03 ---------------------------------------------------------------------------------


def late_minutes(schedule: DaySchedule, first_in: datetime) -> int:
    """Late if after start + tolerance; minutes count from the planned start (RG-02).

    Example: planned 07:30, tolerance 10 min, check-in 07:52 → 22 minutes.
    """
    if not (schedule.works and schedule.start):
        return 0
    if first_in <= schedule.start + timedelta(minutes=schedule.late_tolerance_min):
        return 0
    return int((first_in - schedule.start).total_seconds() // 60)


def early_leave_minutes(schedule: DaySchedule, last_out: datetime) -> int:
    """Early leave if the last exit is before end − tolerance (RG-03)."""
    if not (schedule.works and schedule.end):
        return 0
    if last_out >= schedule.end - timedelta(minutes=schedule.early_tolerance_min):
        return 0
    return int((schedule.end - last_out).total_seconds() // 60)


# --- RG-12: corrections replace what they correct, without deleting it ---------------------------


def effective_punches(punches: Iterable[Punch]) -> list[Punch]:
    items = list(punches)
    corrected = {p.corrects for p in items if p.corrects}
    return sorted((p for p in items if p.id not in corrected), key=lambda p: p.at)


# --- Worked time -----------------------------------------------------------------------------------


def _pairs(punches: Sequence[Punch], start: str, end: str) -> tuple[int, bool]:
    """Total minutes of start→end pairs and whether one ``start`` stayed open."""
    total, opened = 0, None
    for p in punches:
        if p.direction == start and opened is None:
            opened = p.at
        elif p.direction == end and opened is not None:
            total += int((p.at - opened).total_seconds() // 60)
            opened = None
    return total, opened is not None


def worked_minutes(schedule: DaySchedule, punches: Sequence[Punch]) -> tuple[int, bool]:
    presence, open_entry = _pairs(punches, "in", "out")
    recorded_breaks, _ = _pairs(punches, "break_out", "break_in")
    if recorded_breaks:
        presence -= recorded_breaks
    elif schedule.break_minutes and presence > schedule.break_minutes * 2:
        presence -= schedule.break_minutes  # the planned break is assumed taken
    return max(0, presence), open_entry


# --- The day ----------------------------------------------------------------------------------------


def compute_day(
    schedule: DaySchedule,
    punches: Iterable[Punch],
    *,
    now: datetime,
    holiday: bool = False,
    justifications: Justifications = Justifications(),
) -> WorkDayResult:
    items = effective_punches(punches)
    entries = [p.at for p in items if p.direction == "in"]
    exits = [p.at for p in items if p.direction == "out"]
    first_in = entries[0] if entries else None
    last_out = exits[-1] if exits else None
    worked, open_entry = worked_minutes(schedule, items)
    day_over = schedule.end is None or now >= schedule.end
    result = WorkDayResult(
        DayStatus.PRESENT, first_in=first_in, last_out=last_out, worked_minutes=worked
    )

    # RG-09: public holiday or non-working day — no lateness, no absence; presence is overtime.
    if holiday or not schedule.works:
        result.status = DayStatus.HOLIDAY if holiday else DayStatus.OFF
        result.overtime_minutes = worked if worked >= schedule.overtime_threshold_min else 0
        result.overtime_validated = (
            justifications.overtime_validated and result.overtime_minutes > 0
        )
        if result.overtime_minutes:
            result.notes.append(
                "Présence un jour non travaillé : heures supplémentaires à valider."
            )
        return result

    # RG-04: absence is only established once the working day is over.
    if first_in is None:
        if not day_over:
            result.status = DayStatus.PENDING
        else:
            result.status = (
                DayStatus.ABSENT_JUSTIFIED if justifications.absence else DayStatus.ABSENT
            )
        return result

    result.late_minutes = late_minutes(schedule, first_in)
    if last_out is not None and not open_entry:
        result.early_leave_minutes = early_leave_minutes(schedule, last_out)

    # RG-05: an entry without exit at the end of the day (midnight / end of night shift).
    cutoff = (schedule.end or first_in) + timedelta(hours=1)
    if open_entry and now >= cutoff:
        result.incomplete = True
        result.status = DayStatus.INCOMPLETE
        result.notes.append("Oubli de pointage de sortie.")
    elif result.late_minutes:
        result.status = DayStatus.LATE_JUSTIFIED if justifications.late else DayStatus.LATE
    elif open_entry and not day_over:
        result.status = DayStatus.PENDING if first_in is None else DayStatus.PRESENT

    # RG-10: overtime beyond the planned time, from the threshold, counted once validated.
    extra = worked - schedule.planned_minutes
    if not result.incomplete and extra >= schedule.overtime_threshold_min:
        result.overtime_minutes = extra
        result.overtime_validated = justifications.overtime_validated
    return result


# --- Confirmation message for the agent (EF-20) ---------------------------------------------------


def arrival_message(
    schedule: DaySchedule | None, moment: datetime, direction: str
) -> tuple[str, int]:
    """Short status shown right after a check-in: (« À l'heure » | « Retard de X min », minutes)."""
    if direction != "in" or schedule is None or not schedule.works:
        return ("Sortie enregistrée" if direction == "out" else "Pointage enregistré"), 0
    minutes = late_minutes(schedule, moment)
    if minutes:
        return f"Retard de {minutes} min", minutes
    return "À l'heure", 0


def day_schedule_from(
    *,
    day: date,
    weekdays: Sequence[int],
    start: time,
    end: time,
    tz: object,
    break_minutes: int = 0,
    late_tolerance_min: int = 10,
    early_tolerance_min: int = 10,
    overtime_threshold_min: int = OVERTIME_THRESHOLD_DEFAULT,
) -> DaySchedule:
    """Build the planned day; a shift ending before it starts finishes the next day (RG-15)."""
    if day.weekday() not in weekdays:
        return DaySchedule(works=False, overtime_threshold_min=overtime_threshold_min)
    start_dt = datetime.combine(day, start, tzinfo=tz)  # type: ignore[arg-type]
    end_day = day + timedelta(days=1) if end <= start else day
    end_dt = datetime.combine(end_day, end, tzinfo=tz)  # type: ignore[arg-type]
    return DaySchedule(
        works=True,
        start=start_dt,
        end=end_dt,
        break_minutes=break_minutes,
        late_tolerance_min=late_tolerance_min,
        early_tolerance_min=early_tolerance_min,
        overtime_threshold_min=overtime_threshold_min,
    )
