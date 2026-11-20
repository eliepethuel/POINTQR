import re
from datetime import date, timedelta
from typing import Any

from rest_framework import serializers

from .models import Company, Subscription


class SubscriptionSerializer(serializers.ModelSerializer[Subscription]):
    class Meta:
        model = Subscription
        fields = [
            "id",
            "company",
            "plan",
            "max_agents",
            "max_sites",
            "max_kiosks",
            "start_date",
            "end_date",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CompanySerializer(serializers.ModelSerializer[Company]):
    current_subscription = serializers.SerializerMethodField()
    agent_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Company
        fields = [
            "id",
            "legal_name",
            "slug",
            "code",
            "sector",
            "country",
            "timezone",
            "contact_name",
            "contact_email",
            "contact_phone",
            "status",
            "primary_color",
            "highlight_color",
            "created_at",
            "current_subscription",
            "agent_count",
        ]
        read_only_fields = ["id", "status", "created_at", "current_subscription", "agent_count"]

    def get_current_subscription(self, obj: Company) -> dict[str, Any] | None:
        sub = obj.subscriptions.filter(status=Subscription.Status.ACTIVE).first()
        return SubscriptionSerializer(sub).data if sub else None


HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CompanySettingsSerializer(serializers.ModelSerializer[Company]):
    """What a company administrator may change (EF-43 branding, rules defaults)."""

    class Meta:
        model = Company
        fields = [
            "id",
            "legal_name",
            "slug",
            "code",
            "timezone",
            "primary_color",
            "highlight_color",
            "logo",
            "default_radius_m",
            "approval_levels",
            "wifi_check_enabled",
            "break_checkins_enabled",
            "retention_checkins_years",
            "retention_gps_months",
        ]
        read_only_fields = ["id", "slug", "code"]

    def validate_primary_color(self, value: str) -> str:
        if not HEX_COLOR.match(value):
            raise serializers.ValidationError("Couleur hexadécimale attendue (#RRGGBB).")
        return value.upper()

    validate_highlight_color = validate_primary_color


class OnboardingSerializer(serializers.Serializer[Any]):
    """Super-admin creates a company, its subscription and first administrator (EF-01, EF-02)."""

    legal_name = serializers.CharField(max_length=200)
    slug = serializers.SlugField(max_length=63)
    code = serializers.RegexField(r"^[A-Z0-9]{4,12}$")
    sector = serializers.CharField(max_length=120, required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=64, default="Africa/Abidjan")
    contact_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    plan = serializers.ChoiceField(choices=Subscription.Plan.choices, default="starter")
    max_agents = serializers.IntegerField(min_value=1, default=50)
    max_sites = serializers.IntegerField(min_value=1, default=1)
    max_kiosks = serializers.IntegerField(min_value=1, default=1)
    start_date = serializers.DateField(default=date.today)
    end_date = serializers.DateField(default=lambda: date.today() + timedelta(days=365))
    admin_username = serializers.CharField(max_length=150)
    admin_password = serializers.CharField(min_length=10, write_only=True)
    admin_email = serializers.EmailField(required=False, allow_blank=True)

    def validate_slug(self, value: str) -> str:
        if Company.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Sous-domaine déjà utilisé.")
        return value

    def validate_code(self, value: str) -> str:
        if Company.objects.filter(code=value).exists():
            raise serializers.ValidationError("Code déjà utilisé.")
        return value


class PlatformStatsSerializer(serializers.Serializer[Any]):
    companies = serializers.IntegerField()
    active_companies = serializers.IntegerField()
    agents = serializers.IntegerField()
    checkins_today = serializers.IntegerField()
