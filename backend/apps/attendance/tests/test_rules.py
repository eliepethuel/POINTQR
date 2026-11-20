"""Pure business rules RG-01 to RG-15 (no database)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from apps.attendance import rules
from apps.attendance.rules import DaySchedule, DayStatus, Justifications, Punch

TZ = ZoneInfo("Africa/Abidjan")
DAY = date(2026, 11, 16)  # Monday


def t(h: int, m: int = 0, day: date = DAY) -> datetime:
    return datetime.combine(day, time(h, m), tzinfo=TZ)


def schedule(start=(7, 30), end=(16, 30), **kw) -> DaySchedule:
    return rules.day_schedule_from(
        day=DAY,
        weekdays=[0, 1, 2, 3, 4],
        start=time(*start),
        end=time(*end),
        tz=TZ,
        break_minutes=kw.pop("break_minutes", 60),
        **kw,
    )


def punches(*items: tuple[datetime, str]) -> list[Punch]:
    return [Punch(at=at, direction=d, id=str(i)) for i, (at, d) in enumerate(items)]


EVENING = t(23, 0)


# RG-02 ------------------------------------------------------------------------------------------


def test_rg02_lateness_counts_from_planned_start():
    assert rules.late_minutes(schedule(), t(7, 52)) == 22


@pytest.mark.parametrize(
    ("arrival", "expected"), [((7, 30), 0), ((7, 40), 0), ((7, 41), 11), ((9, 0), 90)]
)
def test_rg02_tolerance_boundary(arrival, expected):
    assert rules.late_minutes(schedule(), t(*arrival)) == expected


def test_rg02_day_status_late():
    day = rules.compute_day(schedule(), punches((t(7, 52), "in"), (t(16, 35), "out")), now=EVENING)
    assert (day.status, day.late_minutes) == (DayStatus.LATE, 22)


# RG-03 ------------------------------------------------------------------------------------------


def test_rg03_early_leave_before_end_minus_tolerance():
    day = rules.compute_day(schedule(), punches((t(7, 30), "in"), (t(16, 0), "out")), now=EVENING)
    assert day.early_leave_minutes == 30
    on_time = rules.compute_day(
        schedule(), punches((t(7, 30), "in"), (t(16, 21), "out")), now=EVENING
    )
    assert on_time.early_leave_minutes == 0


# RG-04 ------------------------------------------------------------------------------------------


def test_rg04_absence_only_after_the_working_day():
    assert rules.compute_day(schedule(), [], now=t(10)).status == DayStatus.PENDING
    assert rules.compute_day(schedule(), [], now=EVENING).status == DayStatus.ABSENT


def test_rg04_justified_absence():
    day = rules.compute_day(
        schedule(), [], now=EVENING, justifications=Justifications(absence=True)
    )
    assert day.status == DayStatus.ABSENT_JUSTIFIED


# RG-05 ------------------------------------------------------------------------------------------


def test_rg05_entry_without_exit_is_incomplete_after_the_day():
    day = rules.compute_day(schedule(), punches((t(7, 30), "in")), now=EVENING)
    assert day.status == DayStatus.INCOMPLETE and day.incomplete
    during = rules.compute_day(schedule(), punches((t(7, 30), "in")), now=t(11))
    assert during.status == DayStatus.PRESENT and not during.incomplete


# RG-06 / RG-07 ----------------------------------------------------------------------------------


def test_rg06_duplicate_within_two_minutes():
    assert rules.is_duplicate(t(7, 30), t(7, 31))
    assert not rules.is_duplicate(t(7, 30), t(7, 33))
    assert not rules.is_duplicate(None, t(7, 30))


def test_rg07_direction_alternates_and_ignores_breaks():
    assert rules.next_direction([]) == "in"
    assert rules.next_direction(punches((t(7, 30), "in"))) == "out"
    assert rules.next_direction(punches((t(7, 30), "in"), (t(12), "break_out"))) == "out"
    assert rules.next_direction(punches((t(7, 30), "in"), (t(16, 30), "out"))) == "in"


# RG-09 / RG-10 ----------------------------------------------------------------------------------


def test_rg09_holiday_no_lateness_presence_is_overtime_to_validate():
    day = rules.compute_day(
        schedule(), punches((t(9), "in"), (t(12), "out")), now=EVENING, holiday=True
    )
    assert day.status == DayStatus.HOLIDAY
    assert (day.late_minutes, day.overtime_minutes, day.overtime_validated) == (0, 180, False)


def test_rg09_weekend_is_off():
    saturday = date(2026, 11, 21)
    sat = rules.day_schedule_from(
        day=saturday, weekdays=[0, 1, 2, 3, 4], start=time(7, 30), end=time(16, 30), tz=TZ
    )
    assert not sat.works
    assert rules.compute_day(sat, [], now=t(23, day=saturday)).status == DayStatus.OFF


def test_rg10_overtime_from_30_minutes_counted_once_validated():
    long_day = punches((t(7, 30), "in"), (t(17, 30), "out"))  # 10 h − 1 h break = 9 h, planned 8 h
    day = rules.compute_day(schedule(), long_day, now=EVENING)
    assert (day.overtime_minutes, day.overtime_validated) == (60, False)
    validated = rules.compute_day(
        schedule(), long_day, now=EVENING, justifications=Justifications(overtime_validated=True)
    )
    assert validated.overtime_validated
    short = rules.compute_day(
        schedule(), punches((t(7, 30), "in"), (t(16, 50), "out")), now=EVENING
    )
    assert short.overtime_minutes == 0  # 20 minutes extra: under the 30-minute threshold


# RG-11 ------------------------------------------------------------------------------------------


def test_rg11_justified_lateness_keeps_minutes():
    day = rules.compute_day(
        schedule(),
        punches((t(8), "in"), (t(16, 30), "out")),
        now=EVENING,
        justifications=Justifications(late=True),
    )
    assert (day.status, day.late_minutes) == (DayStatus.LATE_JUSTIFIED, 30)


# RG-12 ------------------------------------------------------------------------------------------


def test_rg12_correction_replaces_the_original_without_deleting_it():
    original = Punch(at=t(7, 55), direction="in", id="orig")
    correction = Punch(at=t(7, 35), direction="in", id="corr", corrects="orig")
    effective = rules.effective_punches([original, correction])
    assert [p.id for p in effective] == ["corr"]
    day = rules.compute_day(
        schedule(),
        [original, correction, Punch(at=t(16, 30), direction="out", id="x")],
        now=EVENING,
    )
    assert day.late_minutes == 0


def test_rg12_added_missing_exit_completes_the_day():
    added = Punch(at=t(16, 40), direction="out", id="added")
    day = rules.compute_day(
        schedule(), [Punch(at=t(7, 30), direction="in", id="a"), added], now=EVENING
    )
    assert day.status == DayStatus.PRESENT and not day.incomplete


# RG-15 ------------------------------------------------------------------------------------------


def test_rg15_night_shift_belongs_to_its_start_date():
    assert rules.work_date_for(t(5, 50, DAY + timedelta(days=1)), night_shift=True) == DAY
    assert rules.work_date_for(t(19, 55), night_shift=True) == DAY
    assert rules.work_date_for(
        t(5, 50, DAY + timedelta(days=1)), night_shift=False
    ) == DAY + timedelta(days=1)


def test_rg15_night_schedule_ends_the_next_day():
    night = rules.day_schedule_from(
        day=DAY,
        weekdays=[0, 1, 2, 3, 4, 5, 6],
        start=time(20),
        end=time(6),
        tz=TZ,
        break_minutes=30,
    )
    assert night.end == t(6, day=DAY + timedelta(days=1))
    shift = punches((t(20, 5), "in"), (t(6, 2, DAY + timedelta(days=1)), "out"))
    day = rules.compute_day(night, shift, now=t(12, day=DAY + timedelta(days=1)))
    assert day.status == DayStatus.PRESENT
    assert day.worked_minutes == (9 * 60 + 57) - 30  # 20:05 → 06:02 minus the 30-minute break


# Worked time and confirmation -----------------------------------------------------------------


def test_recorded_breaks_replace_the_planned_break():
    items = punches(
        (t(7, 30), "in"), (t(12), "break_out"), (t(12, 30), "break_in"), (t(16, 30), "out")
    )
    assert rules.worked_minutes(schedule(), items) == (9 * 60 - 30, False)


def test_planned_break_assumed_on_long_presence_only():
    assert rules.worked_minutes(schedule(), punches((t(8), "in"), (t(9), "out")))[0] == 60


def test_arrival_messages():
    assert rules.arrival_message(schedule(), t(7, 52), "in") == ("Retard de 22 min", 22)
    assert rules.arrival_message(schedule(), t(7, 35), "in") == ("À l'heure", 0)
    assert rules.arrival_message(schedule(), t(16, 40), "out")[0] == "Sortie enregistrée"
    assert rules.arrival_message(None, t(7, 52), "in")[0] == "Pointage enregistré"


def test_planned_minutes():
    assert schedule().planned_minutes == 8 * 60
    assert DaySchedule(works=False).planned_minutes == 0
