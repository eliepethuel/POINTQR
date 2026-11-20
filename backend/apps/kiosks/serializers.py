from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from .models import Kiosk


class KioskSerializer(serializers.ModelSerializer[Kiosk]):
    site_name = serializers.CharField(source="site.name", read_only=True)
    online = serializers.SerializerMethodField()

    class Meta:
        model = Kiosk
        fields = [
            "id",
            "name",
            "site",
            "site_name",
            "status",
            "last_seen_at",
            "app_version",
            "pending_offline",
            "key_version",
            "online",
            "created_at",
        ]
        read_only_fields = fields

    def get_online(self, obj: Kiosk) -> bool:
        return bool(
            obj.is_active
            and obj.last_seen_at
            and timezone.now() - obj.last_seen_at < timedelta(minutes=2)
        )


class PairingCodeRequestSerializer(serializers.Serializer[Any]):
    site = serializers.UUIDField()
    name = serializers.CharField(max_length=120)


class PairingCodeSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    expires_at = serializers.DateTimeField()
    site_name = serializers.CharField()


class PairRequestSerializer(serializers.Serializer[Any]):
    code = serializers.RegexField(r"^\s*\d{6}\s*$")


class KioskSiteSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    radius_m = serializers.IntegerField()


class KioskCompanySerializer(serializers.Serializer[Any]):
    legal_name = serializers.CharField()
    code = serializers.CharField()
    timezone = serializers.CharField()
    primary_color = serializers.CharField()
    highlight_color = serializers.CharField()


class PairResponseSerializer(serializers.Serializer[Any]):
    kiosk_id = serializers.UUIDField()
    kiosk_name = serializers.CharField()
    token = serializers.CharField()
    secret = serializers.CharField()
    key_version = serializers.IntegerField()
    site = KioskSiteSerializer()
    company = KioskCompanySerializer()
    epoch_ms = serializers.IntegerField()


class HeartbeatRequestSerializer(serializers.Serializer[Any]):
    app_version = serializers.CharField(max_length=32, required=False, default="")
    pending = serializers.IntegerField(min_value=0, required=False, default=0)
    key_version = serializers.IntegerField(min_value=0, required=False, default=0)


class HeartbeatResponseSerializer(serializers.Serializer[Any]):
    status = serializers.CharField()
    key_version = serializers.IntegerField()
    secret = serializers.CharField(required=False)
    epoch_ms = serializers.IntegerField()
