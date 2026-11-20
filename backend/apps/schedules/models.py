"""Working schedules, rotations, exceptions and public holidays (EF-12 to EF-16)."""

from datetime import date, time

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator
from django.db import models

from common.models import TenantManager, TenantModel, TimeStampedModel

MONDAY_TO_FRIDAY = [0, 1, 2, 3, 4]


def default_weekdays() -> list[int]:
    return list(MONDAY_TO_FRIDAY)


class Schedule(TenantModel):
    name = models.CharField("nom", max_length=120)
    weekdays = ArrayField(
        models.PositiveSmallIntegerField(validators=[MaxValueValidator(6)]),
        default=default_weekdays,
        help_text="0 = lundi … 6 = dimanche",
    )
    start_time = models.TimeField("heure d'arrivée", default=time(7, 30))
    end_time = models.TimeField("heure de départ", default=time(16, 30))
    break_minutes = models.PositiveSmallIntegerField("pause (min)", default=60)
    late_tolerance_min = models.PositiveSmallIntegerField(
        "tolérance de retard (min)", default=10, validators=[MaxValueValidator(240)]
    )
    early_tolerance_min = models.PositiveSmallIntegerField(
        "tolérance de départ anticipé (min)", default=10, validators=[MaxValueValidator(240)]
    )
    overtime_threshold_min = models.PositiveSmallIntegerField(
        "seuil d'heures supplémentaires (min)", default=30
    )

    class Meta:
        verbose_name = "horaire"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="schedule_unique_name")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"

    @property
    def is_night(self) -> bool:
        """A shift ending the next day (e.g. 20:00 → 06:00) belongs to its start date (RG-15)."""
        return self.end_time <= self.start_time


class ScheduleAssignment(TenantModel):
    """Rotation: an agent follows another schedule over a period (EF-14: day/night teams)."""

    agent = models.ForeignKey(
        "organization.Agent", on_delete=models.CASCADE, related_name="schedule_assignments"
    )
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT, related_name="assignments")
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        verbose_name = "affectation d'horaire"
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="assignment_dates_ordered",
            )
        ]


class ScheduleException(TenantModel):
    """Exceptional timetable over a period (Ramadan, administrative holidays — EF-16)."""

    name = models.CharField("libellé", max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT, related_name="exceptions")
    org_unit = models.ForeignKey(
        "organization.OrgUnit",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Vide = toute l'entreprise.",
    )

    class Meta:
        verbose_name = "horaire d'exception"
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="exception_dates_ordered",
            )
        ]

    def covers(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date


class PublicHoliday(TimeStampedModel):
    """``company`` NULL = national reference list (pre-filled for Côte d'Ivoire, EF-15)."""

    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    date = models.DateField()
    label = models.CharField("libellé", max_length=120)
    country = models.CharField(max_length=2, default="CI")
    is_worked = models.BooleanField(
        "travaillé", default=False, help_text="L'entreprise travaille exceptionnellement ce jour."
    )

    objects = TenantManager()

    class Meta:
        verbose_name = "jour férié"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "date", "country"], name="holiday_unique_per_company"
            ),
            models.UniqueConstraint(
                fields=["date", "country"],
                condition=models.Q(company__isnull=True),
                name="holiday_unique_reference",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.date:%d/%m/%Y} {self.label}"
