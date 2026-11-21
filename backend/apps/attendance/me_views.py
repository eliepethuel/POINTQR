"""Agents' rights (ENF-05): see their data, export their history; HR direct corrections (R7)."""

import csv
from datetime import date
from typing import Any

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsHrOrAdmin
from common.exceptions import DomainError
from common.request import company_of

from . import corrections
from .days_views import WorkDaySerializer
from .models import CheckIn, Direction, WorkDay
from .serializers import CheckInSerializer


def _agent(request: Request) -> Any:
    agent = getattr(request.user, "agent", None)
    if agent is None:
        raise DomainError("Ce compte n'est lié à aucun agent.", code="no_agent", status_code=403)
    return agent


class MyHistorySerializer(serializers.Serializer[Any]):
    workdays = WorkDaySerializer(many=True)
    checkins = CheckInSerializer(many=True)


class MyHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="me_history",
        responses=MyHistorySerializer,
        parameters=[OpenApiParameter("start", date), OpenApiParameter("end", date)],
    )
    def get(self, request: Request) -> Response:
        agent = _agent(request)
        days = WorkDay.objects.filter(agent=agent).order_by("-date")
        checkins = (
            CheckIn.objects.filter(agent=agent).select_related("site").order_by("-effective_ts")
        )
        if request.query_params.get("start"):
            days = days.filter(date__gte=request.query_params["start"])
            checkins = checkins.filter(effective_ts__date__gte=request.query_params["start"])
        if request.query_params.get("end"):
            days = days.filter(date__lte=request.query_params["end"])
            checkins = checkins.filter(effective_ts__date__lte=request.query_params["end"])
        return Response(
            {
                "workdays": WorkDaySerializer(days[:93], many=True).data,
                "checkins": CheckInSerializer(checkins[:300], many=True).data,
            }
        )


class MyExportView(APIView):
    """Full personal history as CSV (data portability)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="me_export", responses={(200, "text/csv"): bytes})
    def get(self, request: Request) -> HttpResponse:
        agent = _agent(request)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="pointages-{agent.employee_number}.csv"'
        )
        response.write("﻿")  # Excel opens UTF-8 correctly with a BOM
        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Date et heure",
                "Sens",
                "Mode",
                "Site",
                "Résultat",
                "Motif de refus",
                "Hors-ligne",
                "Correction",
            ]
        )
        tz = company_of(request).timezone
        from zoneinfo import ZoneInfo

        zone = ZoneInfo(tz)
        for c in (
            CheckIn.objects.filter(agent=agent).select_related("site").order_by("effective_ts")
        ):
            writer.writerow(
                [
                    c.effective_ts.astimezone(zone).strftime("%d/%m/%Y %H:%M:%S"),
                    c.get_direction_display(),
                    c.get_mode_display(),
                    c.site.name if c.site else "",
                    c.get_result_display(),
                    c.get_refusal_code_display() if c.refusal_code else "",
                    "oui" if c.offline else "non",
                    "oui" if c.is_correction else "non",
                ]
            )
        return response


class CorrectionSerializer(serializers.Serializer[Any]):
    checkin = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Pointage à corriger ; vide = ajouter un pointage oublié.",
    )
    agent = serializers.UUIDField(required=False, allow_null=True)
    effective_ts = serializers.DateTimeField()
    direction = serializers.ChoiceField(choices=Direction.choices)
    reason = serializers.CharField(max_length=2000)


class CorrectionView(APIView):
    """HR corrects or adds a check-in: the original is kept, the change is audited (R7)."""

    permission_classes = [IsHrOrAdmin]

    @extend_schema(
        operation_id="checkins_correct", request=CorrectionSerializer, responses=CheckInSerializer
    )
    def post(self, request: Request) -> Response:
        from apps.organization.models import Agent

        data = CorrectionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        original = CheckIn.objects.filter(id=v["checkin"]).first() if v.get("checkin") else None
        if v.get("checkin") and original is None:
            raise DomainError("Pointage introuvable.", code="not_found", status_code=404)
        agent = original.agent if original else Agent.objects.filter(id=v.get("agent")).first()
        if agent is None:
            raise DomainError("Agent introuvable.", code="not_found", status_code=404)
        line = corrections.correct(
            company=company_of(request),
            agent=agent,
            author=request.user,
            reason=v["reason"],
            effective_ts=v["effective_ts"],
            direction=v["direction"],
            original=original,
            request=request._request,
        )
        return Response(CheckInSerializer(line).data, status=201)
