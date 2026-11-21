from typing import Any

from rest_framework import serializers

from .models import CheckIn, Direction, RefusalCode


class CheckInSerializer(serializers.ModelSerializer[CheckIn]):
    agent_name = serializers.CharField(source="agent.full_name", read_only=True, default=None)
    employee_number = serializers.CharField(
        source="agent.employee_number", read_only=True, default=None
    )
    site_name = serializers.CharField(source="site.name", read_only=True, default=None)
    kiosk_name = serializers.CharField(source="kiosk.name", read_only=True, default=None)
    refusal_label = serializers.SerializerMethodField()

    class Meta:
        model = CheckIn
        fields = [
            "id",
            "agent",
            "agent_name",
            "employee_number",
            "site",
            "site_name",
            "kiosk",
            "kiosk_name",
            "direction",
            "mode",
            "trust",
            "server_ts",
            "effective_ts",
            "offline",
            "distance_m",
            "accuracy_m",
            "result",
            "refusal_code",
            "refusal_label",
            "refusal_details",
            "is_correction",
            "corrects",
            "reason",
            "created_at",
        ]
        read_only_fields = fields

    def get_refusal_label(self, obj: CheckIn) -> str:
        return RefusalCode(obj.refusal_code).label if obj.refusal_code else ""


class PhoneCheckInRequestSerializer(serializers.Serializer[Any]):
    """Mobile payload — a few hundred bytes (ENF-21 < 5 KB)."""

    token = serializers.CharField(max_length=200)
    device_id = serializers.CharField(max_length=128)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False, allow_null=True)
    longitude = serializers.FloatField(
        min_value=-180, max_value=180, required=False, allow_null=True
    )
    accuracy_m = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    mock_location = serializers.BooleanField(required=False, default=False)
    wifi = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)
    direction = serializers.ChoiceField(choices=Direction.choices, required=False, allow_null=True)


class CheckInOutcomeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    result = serializers.CharField()
    direction = serializers.CharField(allow_blank=True)
    refusal_code = serializers.CharField(allow_blank=True)
    refusal_details = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()
    late_minutes = serializers.IntegerField()
    effective_ts = serializers.DateTimeField()
    offline = serializers.BooleanField()
    agent_name = serializers.CharField(allow_null=True)


class BadgeScanRequestSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=200)
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    scanned_at = serializers.DateTimeField(required=False, allow_null=True)
    offline = serializers.BooleanField(required=False, default=False)


class BadgeBatchRequestSerializer(serializers.Serializer[Any]):
    items = BadgeScanRequestSerializer(many=True, allow_empty=False, max_length=2000)  # type: ignore[call-arg]


class BatchItemResultSerializer(serializers.Serializer[Any]):
    client_uuid = serializers.UUIDField(allow_null=True)
    result = serializers.CharField()
    refusal_code = serializers.CharField(allow_blank=True)


class BatchResultSerializer(serializers.Serializer[Any]):
    received = serializers.IntegerField()
    accepted = serializers.IntegerField()
    items = BatchItemResultSerializer(many=True)


class ActivateRequestSerializer(serializers.Serializer[Any]):
    device_id = serializers.CharField(max_length=128)
    model = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    os = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")


class MobileStatusSerializer(serializers.Serializer[Any]):
    agent_id = serializers.UUIDField()
    agent_name = serializers.CharField()
    employee_number = serializers.CharField()
    device_bound = serializers.BooleanField()
    phone_state = serializers.ChoiceField(
        choices=["unbound", "this", "other", "change_pending"],
        help_text="unbound : à activer · this : ce téléphone · other : un autre téléphone est lié "
        "· change_pending : changement demandé, en attente du RH",
    )
    next_direction = serializers.CharField()
    site_name = serializers.CharField(allow_null=True)
    schedule = serializers.CharField(allow_null=True)
    today = CheckInSerializer(many=True)


class PersonalKeySerializer(serializers.Serializer[Any]):
    agent_id = serializers.UUIDField()
    key = serializers.CharField()
    window_seconds = serializers.IntegerField()


class PrintedTokenSerializer(serializers.Serializer[Any]):
    token = serializers.CharField()
    caption = serializers.CharField()
