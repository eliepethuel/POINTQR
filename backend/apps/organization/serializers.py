from typing import Any

from rest_framework import serializers

from .models import Agent, Device, DeviceChangeRequest, OrgUnit, Site


class SiteSerializer(serializers.ModelSerializer[Site]):
    agent_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Site
        fields = [
            "id",
            "name",
            "address",
            "latitude",
            "longitude",
            "radius_m",
            "allowed_wifi",
            "is_active",
            "agent_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "agent_count"]

    def validate_allowed_wifi(self, value: Any) -> list[str]:
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise serializers.ValidationError("Liste de noms de réseaux attendue.")
        return [v.strip() for v in value if v.strip()]


class OrgUnitSerializer(serializers.ModelSerializer[OrgUnit]):
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default=None)

    class Meta:
        model = OrgUnit
        fields = ["id", "name", "kind", "parent", "manager", "manager_name"]
        read_only_fields = ["id", "manager_name"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        parent = attrs.get("parent")
        node = self.instance
        while parent is not None and node is not None:
            if parent.pk == node.pk:
                raise serializers.ValidationError(
                    {"parent": "Une unité ne peut pas être sa propre parente."}
                )
            parent = parent.parent
        return attrs


class OrgTreeNodeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    kind = serializers.CharField()
    manager_name = serializers.CharField(allow_null=True)
    agent_count = serializers.IntegerField()
    children = serializers.ListField(child=serializers.DictField())


class AgentSerializer(serializers.ModelSerializer[Agent]):
    full_name = serializers.CharField(read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True, default=None)
    org_unit_name = serializers.CharField(source="org_unit.name", read_only=True, default=None)
    has_device = serializers.BooleanField(read_only=True, required=False)

    class Meta:
        model = Agent
        fields = [
            "id",
            "employee_number",
            "last_name",
            "first_names",
            "full_name",
            "job_title",
            "phone",
            "email",
            "site",
            "site_name",
            "org_unit",
            "org_unit_name",
            "schedule",
            "status",
            "has_device",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "site_name",
            "org_unit_name",
            "has_device",
            "created_at",
        ]


class DeviceSerializer(serializers.ModelSerializer[Device]):
    class Meta:
        model = Device
        fields = ["id", "agent", "model", "os", "bound_at", "is_active", "revoked_at"]
        read_only_fields = fields


class DeviceChangeRequestSerializer(serializers.ModelSerializer[DeviceChangeRequest]):
    agent_name = serializers.CharField(source="agent.full_name", read_only=True)

    class Meta:
        model = DeviceChangeRequest
        fields = ["id", "agent", "agent_name", "model", "os", "status", "decided_at", "created_at"]
        read_only_fields = fields


class ImportErrorSerializer(serializers.Serializer[Any]):
    line = serializers.IntegerField()
    field = serializers.CharField()
    message = serializers.CharField()


class ImportReportSerializer(serializers.Serializer[Any]):
    total = serializers.IntegerField()
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    dry_run = serializers.BooleanField()
    # Not named `errors`: that name is the serializer's own validation-errors property.
    line_errors = ImportErrorSerializer(many=True, source="errors")


class ImportRequestSerializer(serializers.Serializer[Any]):
    file = serializers.FileField()
    dry_run = serializers.BooleanField(default=False)
