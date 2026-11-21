from typing import Any

from rest_framework import serializers

from apps.tenancy.models import Company

from .models import Role, User


class LoginSerializer(serializers.Serializer[Any]):
    company_code = serializers.CharField(required=False, allow_blank=True, max_length=12)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class ActivationSerializer(serializers.Serializer[Any]):
    """First password of an invited agent (EF-09)."""

    company_code = serializers.CharField(max_length=12)
    token = serializers.CharField(max_length=128)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class ActivationInfoSerializer(serializers.Serializer[Any]):
    first_name = serializers.CharField()
    username = serializers.CharField()
    company = serializers.CharField()


class MfaVerifySerializer(serializers.Serializer[Any]):
    mfa_token = serializers.CharField()
    code = serializers.RegexField(r"^\s*\d{6}\s*$", error_messages={"invalid": "6 chiffres."})


class CompanyBrandingSerializer(serializers.ModelSerializer[Company]):
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
            "status",
        ]
        read_only_fields = fields


class MeSerializer(serializers.ModelSerializer[User]):
    company = CompanyBrandingSerializer(read_only=True)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=Role.choices))
    agent_id = serializers.UUIDField(source="agent.id", read_only=True, allow_null=True)
    mfa_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "display_name",
            "email",
            "roles",
            "is_superadmin",
            "agent_id",
            "company",
            "mfa_enabled",
        ]
        read_only_fields = fields

    def get_mfa_enabled(self, obj: User) -> bool:
        from django_otp.plugins.otp_totp.models import TOTPDevice

        return TOTPDevice.objects.filter(user=obj, confirmed=True).exists()


class AuthResponseSerializer(serializers.Serializer[Any]):
    """Either tokens (step=authenticated) or an MFA challenge."""

    step = serializers.ChoiceField(
        choices=["authenticated", "mfa_required", "mfa_setup", "activated"]
    )
    access = serializers.CharField(required=False)
    user = MeSerializer(required=False)
    mfa_token = serializers.CharField(required=False)
    otpauth_url = serializers.CharField(required=False)
    secret = serializers.CharField(required=False)


class UserSerializer(serializers.ModelSerializer[User]):
    """Accounts managed by the company administrator (EF-40)."""

    password = serializers.CharField(write_only=True, required=False, min_length=10)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=Role.choices), allow_empty=False
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "display_name",
            "email",
            "roles",
            "agent",
            "is_active",
            "password",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_roles(self, value: list[str]) -> list[str]:
        return sorted(set(value))

    def create(self, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop("password", None)
        company = self.context["request"].company
        return User.objects.create_user(
            validated_data.pop("username"), password, company=company, **validated_data
        )

    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop("password", None)
        validated_data.pop("username", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
