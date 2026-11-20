"""Agent import from Excel (.xlsx) or CSV with a line-by-line error report (EF-08)."""

import csv
import io
import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import IO, Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from openpyxl import load_workbook

from .models import Agent, OrgUnit, Site

#: Accepted column headers (normalised: lowercase, no accents) → model field.
COLUMNS: dict[str, str] = {
    "matricule": "employee_number",
    "nom": "last_name",
    "prenoms": "first_names",
    "prenom": "first_names",
    "fonction": "job_title",
    "telephone": "phone",
    "email": "email",
    "e-mail": "email",
    "site": "site",
    "unite": "org_unit",
    "service": "org_unit",
}
REQUIRED = ("employee_number", "last_name", "first_names")
MAX_ROWS = 5000


@dataclass(slots=True)
class RowError:
    line: int
    field: str
    message: str


@dataclass(slots=True)
class ImportReport:
    total: int = 0
    created: int = 0
    updated: int = 0
    dry_run: bool = False
    errors: list[RowError] = field(default_factory=list)


def _normalise(header: Any) -> str:
    text = unicodedata.normalize("NFKD", str(header or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().lower()


def _rows_from_xlsx(stream: IO[bytes]) -> Iterator[list[Any]]:
    workbook = load_workbook(stream, read_only=True, data_only=True)
    sheet = workbook.active
    if sheet is None:
        return
    for row in sheet.iter_rows(values_only=True):
        yield list(row)


def _rows_from_csv(stream: IO[bytes]) -> Iterator[list[Any]]:
    raw = stream.read()
    text = raw.decode("utf-8-sig", errors="replace")
    dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t") if text.strip() else csv.excel
    yield from csv.reader(io.StringIO(text), dialect)


def read_rows(filename: str, stream: IO[bytes]) -> Iterable[list[Any]]:
    if filename.lower().endswith((".xlsx", ".xlsm")):
        return _rows_from_xlsx(stream)
    if filename.lower().endswith((".csv", ".txt")):
        return _rows_from_csv(stream)
    raise ValueError("Format non pris en charge : utilisez .xlsx ou .csv.")


def import_agents(filename: str, stream: IO[bytes], *, dry_run: bool = False) -> ImportReport:
    """Create or update agents by employee number. Nothing is written if any line is invalid."""
    report = ImportReport(dry_run=dry_run)
    rows = iter(read_rows(filename, stream))
    header = next(rows, None)
    if header is None:
        report.errors.append(RowError(1, "fichier", "Le fichier est vide."))
        return report

    mapping = {i: COLUMNS[_normalise(h)] for i, h in enumerate(header) if _normalise(h) in COLUMNS}
    missing = [f for f in REQUIRED if f not in mapping.values()]
    if missing:
        labels = {"employee_number": "matricule", "last_name": "nom", "first_names": "prénoms"}
        report.errors.append(
            RowError(1, "en-tête", "Colonnes manquantes : " + ", ".join(labels[m] for m in missing))
        )
        return report

    sites = {s.name.lower(): s for s in Site.objects.all()}
    units = {u.name.lower(): u for u in OrgUnit.objects.all()}
    existing = {a.employee_number: a for a in Agent.objects.all()}
    seen: set[str] = set()
    pending: list[tuple[Agent, bool]] = []

    for line_no, raw in enumerate(rows, start=2):
        if line_no - 1 > MAX_ROWS:
            report.errors.append(RowError(line_no, "fichier", f"Maximum {MAX_ROWS} lignes."))
            break
        values = {
            mapping[i]: ("" if v is None else str(v).strip())
            for i, v in enumerate(raw)
            if i in mapping
        }
        if not any(values.values()):
            continue
        report.total += 1
        line_errors = _validate_row(line_no, values, seen, sites, units)
        if line_errors:
            report.errors.extend(line_errors)
            continue
        number = values["employee_number"]
        seen.add(number)
        agent = existing.get(number)
        is_new = agent is None
        agent = agent or Agent(employee_number=number)
        agent.last_name = values["last_name"].upper()
        agent.first_names = values["first_names"]
        agent.job_title = values.get("job_title", agent.job_title)
        agent.phone = values.get("phone", agent.phone)
        agent.email = values.get("email", agent.email).lower()
        if values.get("site"):
            agent.site = sites[values["site"].lower()]
        if values.get("org_unit"):
            agent.org_unit = units[values["org_unit"].lower()]
        pending.append((agent, is_new))

    if report.errors or dry_run:
        report.created = sum(1 for _, new in pending if new)
        report.updated = len(pending) - report.created
        return report

    with transaction.atomic():
        for agent, is_new in pending:
            agent.save()
            if is_new:
                report.created += 1
            else:
                report.updated += 1
    return report


def _validate_row(
    line: int,
    values: dict[str, str],
    seen: set[str],
    sites: dict[str, Site],
    units: dict[str, OrgUnit],
) -> list[RowError]:
    errors = [
        RowError(line, label, "Champ obligatoire.")
        for key, label in (
            ("employee_number", "matricule"),
            ("last_name", "nom"),
            ("first_names", "prénoms"),
        )
        if not values.get(key)
    ]
    number = values.get("employee_number", "")
    if number and number in seen:
        errors.append(RowError(line, "matricule", f"Matricule {number} en double dans le fichier."))
    if number and len(number) > 32:
        errors.append(RowError(line, "matricule", "32 caractères maximum."))
    if values.get("email"):
        try:
            validate_email(values["email"])
        except ValidationError:
            errors.append(RowError(line, "email", "Adresse e-mail invalide."))
    if values.get("phone") and not re.fullmatch(r"\+?[0-9 .-]{8,20}", values["phone"]):
        errors.append(RowError(line, "téléphone", "Numéro de téléphone invalide."))
    if values.get("site") and values["site"].lower() not in sites:
        errors.append(RowError(line, "site", f"Site « {values['site']} » introuvable."))
    if values.get("org_unit") and values["org_unit"].lower() not in units:
        errors.append(RowError(line, "unité", f"Unité « {values['org_unit']} » introuvable."))
    return errors
