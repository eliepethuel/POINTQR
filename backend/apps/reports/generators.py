"""Report builders. Figures come only from WorkDay rows, so they always match the dashboard (R9)."""

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, QuerySet, Sum
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from apps.attendance.models import CheckIn, WorkDay
from apps.organization.models import Agent
from apps.tenancy.models import Company

Progress = Callable[[int], None]
VIOLET = colors.HexColor("#7C5CFF")
INK = colors.HexColor("#0E0F1A")
MUTED = colors.HexColor("#55576B")
LATE_STATUSES = (WorkDay.Status.LATE, WorkDay.Status.LATE_JUSTIFIED)
STATUS_FR = dict(WorkDay.Status.choices)


@dataclass(slots=True)
class AgentTotals:
    agent_id: UUID
    employee_number: str
    name: str
    unit: str
    days: int = 0
    present: int = 0
    late_count: int = 0
    late_minutes: int = 0
    early_count: int = 0
    early_minutes: int = 0
    absences: int = 0
    justified_absences: int = 0
    incomplete: int = 0
    worked_minutes: int = 0
    overtime_minutes: int = 0


def _agents(unit_id: UUID | None, agent_id: UUID | None) -> QuerySet[Agent]:
    qs = Agent.objects.select_related("org_unit").order_by("last_name", "first_names")
    if agent_id:
        return qs.filter(id=agent_id)
    if unit_id:
        from apps.organization.selectors import unit_descendant_ids

        qs = qs.filter(org_unit_id__in=unit_descendant_ids(unit_id))
    return qs


def punctuality(
    start: date, end: date, unit_id: UUID | None = None, agent_id: UUID | None = None
) -> list[AgentTotals]:
    """One aggregated query: retards (count, cumulated minutes), early leaves, absences (EF-34)."""
    agents = list(_agents(unit_id, agent_id))
    rows = (
        WorkDay.objects.filter(date__gte=start, date__lte=end, agent__in=agents)
        .values("agent_id")
        .annotate(
            days=Count("id", filter=~Q(status__in=[WorkDay.Status.OFF, WorkDay.Status.HOLIDAY])),
            present=Count("id", filter=Q(first_in__isnull=False)),
            late_count=Count("id", filter=Q(status__in=LATE_STATUSES)),
            late_minutes=Sum("late_minutes", filter=Q(status__in=LATE_STATUSES)),
            early_count=Count("id", filter=Q(early_leave_minutes__gt=0)),
            early_minutes=Sum("early_leave_minutes"),
            absences=Count("id", filter=Q(status=WorkDay.Status.ABSENT)),
            justified_absences=Count("id", filter=Q(status=WorkDay.Status.ABSENT_JUSTIFIED)),
            incomplete=Count("id", filter=Q(incomplete=True)),
            worked_minutes=Sum("worked_minutes"),
            overtime_minutes=Sum("overtime_minutes", filter=Q(overtime_validated=True)),
        )
    )
    by_agent = {r["agent_id"]: r for r in rows}
    result = []
    for a in agents:
        r = by_agent.get(a.id, {})
        result.append(
            AgentTotals(
                agent_id=a.id,
                employee_number=a.employee_number,
                name=a.full_name,
                unit=a.org_unit.name if a.org_unit else "",
                **{
                    k: int(r.get(k) or 0)
                    for k in (
                        "days",
                        "present",
                        "late_count",
                        "late_minutes",
                        "early_count",
                        "early_minutes",
                        "absences",
                        "justified_absences",
                        "incomplete",
                        "worked_minutes",
                        "overtime_minutes",
                    )
                },
            )
        )
    return result


def _hours(minutes: int) -> str:
    return f"{minutes // 60}h{minutes % 60:02d}"


def _sheet(title: str, headers: list[str], rows: list[list[Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active or wb.create_sheet()
    ws.title = title[:31]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="7C5CFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in rows:
        ws.append(row)
    for i, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, len(header) + 2)
    ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def punctuality_xlsx(
    company: Company,
    start: date,
    end: date,
    *,
    unit_id: UUID | None = None,
    agent_id: UUID | None = None,
    progress: Progress = lambda _: None,
) -> bytes:
    totals = punctuality(start, end, unit_id, agent_id)
    progress(60)
    rows = [
        [
            t.employee_number,
            t.name,
            t.unit,
            t.days,
            t.present,
            t.late_count,
            t.late_minutes,
            t.early_count,
            t.early_minutes,
            t.absences,
            t.justified_absences,
            t.incomplete,
            round(100 * (t.present - t.late_count) / t.present, 1) if t.present else 100.0,
        ]
        for t in totals
    ]
    return _sheet(
        f"Ponctualité {start:%m-%Y}",
        [
            "Matricule",
            "Agent",
            "Unité",
            "Jours ouvrés",
            "Jours présents",
            "Retards",
            "Minutes de retard",
            "Départs anticipés",
            "Minutes de départ anticipé",
            "Absences",
            "Absences justifiées",
            "Journées incomplètes",
            "Ponctualité (%)",
        ],
        rows,
    )


def payroll_xlsx(
    company: Company,
    start: date,
    end: date,
    *,
    unit_id: UUID | None = None,
    agent_id: UUID | None = None,
    progress: Progress = lambda _: None,
) -> bytes:
    """Variable payroll elements only — PointQR does not compute payroll (CDC §3)."""
    totals = punctuality(start, end, unit_id, agent_id)
    progress(60)
    rows = [
        [
            t.employee_number,
            t.name,
            t.days,
            t.present,
            t.absences,
            t.justified_absences,
            t.late_minutes,
            t.early_minutes,
            round(t.worked_minutes / 60, 2),
            round(t.overtime_minutes / 60, 2),
        ]
        for t in totals
    ]
    return _sheet(
        "Variables de paie",
        [
            "Matricule",
            "Agent",
            "Jours ouvrés",
            "Jours présents",
            "Absences non justifiées",
            "Absences justifiées",
            "Minutes de retard",
            "Minutes de départ anticipé",
            "Heures travaillées",
            "Heures supplémentaires validées",
        ],
        rows,
    )


def checkins_csv(
    company: Company,
    start: date,
    end: date,
    *,
    unit_id: UUID | None = None,
    agent_id: UUID | None = None,
    progress: Progress = lambda _: None,
) -> bytes:
    tz = ZoneInfo(company.timezone)
    agents = _agents(unit_id, agent_id)
    qs = (
        CheckIn.objects.filter(
            effective_ts__date__gte=start, effective_ts__date__lte=end, agent__in=agents
        )
        .select_related("agent", "site")
        .order_by("effective_ts")
    )
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, delimiter=";")
    writer.writerow(
        [
            "Matricule",
            "Agent",
            "Date",
            "Heure",
            "Sens",
            "Mode",
            "Confiance",
            "Site",
            "Résultat",
            "Motif",
            "Distance (m)",
            "Hors-ligne",
            "Correction",
        ]
    )
    for c in qs.iterator(chunk_size=2000):
        local = c.effective_ts.astimezone(tz)
        writer.writerow(
            [
                c.agent.employee_number if c.agent else "",
                c.agent.full_name if c.agent else "",
                local.strftime("%d/%m/%Y"),
                local.strftime("%H:%M:%S"),
                c.get_direction_display(),
                c.mode,
                c.get_trust_display(),
                c.site.name if c.site else "",
                c.get_result_display(),
                c.get_refusal_code_display() if c.refusal_code else "",
                c.distance_m or "",
                "oui" if c.offline else "non",
                "oui" if c.is_correction else "non",
            ]
        )
    progress(90)
    return out.getvalue().encode("utf-8")


def monthly_sheet_pdf(
    company: Company,
    start: date,
    end: date,
    *,
    unit_id: UUID | None = None,
    agent_id: UUID | None = None,
    progress: Progress = lambda _: None,
) -> bytes:
    """Monthly attendance sheet, one page per agent, with signature boxes (EF-35)."""
    tz = ZoneInfo(company.timezone)
    agents = list(_agents(unit_id, agent_id))
    days = {
        (w.agent_id, w.date): w
        for w in WorkDay.objects.filter(date__gte=start, date__lte=end, agent__in=agents)
    }
    totals = {t.agent_id: t for t in punctuality(start, end, unit_id, agent_id)}
    buffer = io.BytesIO()
    pdf = Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"Feuilles de présence {start:%m/%Y} — {company.legal_name}")
    width, height = A4
    for index, agent in enumerate(agents):
        y = height - 20 * mm
        pdf.setFillColor(VIOLET)
        pdf.rect(0, height - 8 * mm, width, 8 * mm, stroke=0, fill=1)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(15 * mm, y, "Feuille de présence")
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(
            width - 15 * mm, y, f"{company.legal_name} — {start:%d/%m/%Y} au {end:%d/%m/%Y}"
        )
        y -= 7 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(15 * mm, y, f"{agent.full_name}  ({agent.employee_number})")
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(MUTED)
        pdf.drawString(15 * mm, y - 5 * mm, agent.org_unit.name if agent.org_unit else "")
        y -= 13 * mm
        cols = [15, 40, 72, 92, 112, 137, 162]
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8)
        for x, label in zip(
            cols,
            ["Date", "Statut", "Entrée", "Sortie", "Retard", "Départ ant.", "Heures"],
            strict=True,
        ):
            pdf.drawString(x * mm, y, label)
        y -= 2 * mm
        pdf.line(15 * mm, y, width - 15 * mm, y)
        pdf.setFont("Helvetica", 8)
        day = start
        while day <= end:
            y -= 5 * mm
            wd = days.get((agent.id, day))
            pdf.setFillColor(MUTED if day.weekday() >= 5 else INK)
            pdf.drawString(cols[0] * mm, y, day.strftime("%a %d/%m").capitalize())
            if wd:
                pdf.drawString(cols[1] * mm, y, STATUS_FR.get(wd.status, wd.status))
                pdf.drawString(
                    cols[2] * mm,
                    y,
                    wd.first_in.astimezone(tz).strftime("%H:%M") if wd.first_in else "—",
                )
                pdf.drawString(
                    cols[3] * mm,
                    y,
                    wd.last_out.astimezone(tz).strftime("%H:%M") if wd.last_out else "—",
                )
                pdf.drawString(cols[4] * mm, y, f"{wd.late_minutes} min" if wd.late_minutes else "")
                pdf.drawString(
                    cols[5] * mm,
                    y,
                    f"{wd.early_leave_minutes} min" if wd.early_leave_minutes else "",
                )
                pdf.drawString(
                    cols[6] * mm, y, _hours(wd.worked_minutes) if wd.worked_minutes else ""
                )
            day += timedelta(days=1)
        t = totals[agent.id]
        y -= 9 * mm
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(
            15 * mm,
            y,
            (
                f"Présent {t.present}/{t.days} j · {t.late_count} retard(s), "
                f"{t.late_minutes} min · {t.absences} absence(s) · "
                f"{_hours(t.worked_minutes)} travaillées"
            ),
        )
        y = 30 * mm
        pdf.setFont("Helvetica", 8)
        for x, label in ((15, "Signature de l'agent"), (110, "Visa du responsable")):
            pdf.rect(x * mm, y - 18 * mm, 80 * mm, 22 * mm)
            pdf.drawString((x + 2) * mm, y + 1 * mm, label)
        pdf.setFillColor(MUTED)
        pdf.drawString(
            15 * mm, 8 * mm, "Heures fixées par le serveur PointQR — aucune saisie manuelle."
        )
        pdf.showPage()
        if index % 25 == 0:
            progress(10 + int(85 * index / max(1, len(agents))))
    pdf.save()
    return buffer.getvalue()


def badges_pdf(
    company: Company,
    start: date | None = None,
    end: date | None = None,
    *,
    unit_id: UUID | None = None,
    agent_id: UUID | None = None,
    progress: Progress = lambda _: None,
) -> bytes:
    """Sheet of printable QR badges, 10 per A4 page (mode C, EF-11)."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing

    from apps.attendance.tokens import badge_token
    from apps.organization.services import ensure_badge_key
    from common.crypto import decrypt

    agents = list(_agents(unit_id, agent_id))
    buffer = io.BytesIO()
    pdf = Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"Badges PointQR — {company.legal_name}")
    _width, height = A4
    card_w, card_h = 85 * mm, 54 * mm  # credit-card size
    for index, agent in enumerate(agents):
        if not agent.badge_key:
            ensure_badge_key(agent)
            agent.save(update_fields=["badge_key", "updated_at"])
        slot = index % 10
        if slot == 0 and index:
            pdf.showPage()
        x = 15 * mm + (slot % 2) * (card_w + 10 * mm)
        y = height - 15 * mm - (slot // 2 + 1) * (card_h + 2 * mm)
        pdf.setStrokeColor(colors.HexColor("#D0D2DC"))
        pdf.roundRect(x, y, card_w, card_h, 4 * mm)
        pdf.setFillColor(VIOLET)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x + 5 * mm, y + card_h - 8 * mm, "PointQR")
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x + 5 * mm, y + card_h - 12 * mm, company.legal_name[:40])
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x + 5 * mm, y + 18 * mm, agent.full_name[:28])
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x + 5 * mm, y + 13 * mm, agent.employee_number)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6)
        pdf.drawString(
            x + 5 * mm, y + 5 * mm, f"Badge v{agent.badge_version} — personnel, ne pas prêter"
        )
        token = badge_token(decrypt(agent.badge_key), agent.id, agent.badge_version)
        widget = QrCodeWidget(token, barLevel="M")
        x0, y0, x1, y1 = widget.getBounds()
        size = 40 * mm
        drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
        drawing.add(widget)
        renderPDF.draw(drawing, pdf, x + card_w - size - 4 * mm, y + (card_h - size) / 2)
        if index % 20 == 0:
            progress(10 + int(85 * index / max(1, len(agents))))
    pdf.save()
    return buffer.getvalue()
