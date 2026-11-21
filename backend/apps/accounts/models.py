"""Users and roles (section 4 of the specification). A user may hold several roles."""

import uuid
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models

from common.models import TenantModel


class Role(models.TextChoices):
    COMPANY_ADMIN = "company_admin", "Administrateur entreprise"
    HR = "hr", "Gestionnaire RH"
    MANAGER = "manager", "Manager"
    AGENT = "agent", "Agent"
    AUDITOR = "auditor", "Auditeur"


#: Roles for which two-factor authentication is mandatory (ENF-09).
MFA_REQUIRED_ROLES = frozenset({Role.COMPANY_ADMIN, Role.HR})


def build_login(company_slug: str | None, username: str) -> str:
    """Globally unique login: ``<company-slug>/<username>``; super-admins have no company."""
    username = username.strip().lower()
    return f"{company_slug}/{username}" if company_slug else username


class UserManager(BaseUserManager["User"]):
    def create_user(
        self, username: str, password: str | None = None, *, company: Any = None, **extra: Any
    ) -> "User":
        user = self.model(
            login=build_login(company.slug if company else None, username),
            username=username.strip().lower(),
            company=company,
            **extra,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superadmin(self, username: str, password: str, **extra: Any) -> "User":
        return self.create_user(username, password, company=None, is_superadmin=True, **extra)


class User(AbstractBaseUser):
    """Belongs to one company (row level security); super-admins (editor team) have none."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    login = models.CharField(max_length=200, unique=True, editable=False)
    username = models.CharField("identifiant", max_length=150)
    email = models.EmailField("e-mail", blank=True)
    display_name = models.CharField("nom affiché", max_length=200, blank=True)
    agent = models.OneToOneField(
        "organization.Agent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user",
    )
    roles = ArrayField(
        models.CharField(max_length=32, choices=Role.choices), default=list, blank=True
    )
    is_active = models.BooleanField(default=True)
    is_superadmin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "login"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        verbose_name = "utilisateur"
        constraints = [
            models.UniqueConstraint(fields=["company", "username"], name="user_unique_per_company"),
            models.CheckConstraint(
                condition=models.Q(is_superadmin=True) | models.Q(company__isnull=False),
                name="user_has_company_unless_superadmin",
            ),
        ]

    def __str__(self) -> str:
        return self.display_name or self.username

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    @property
    def mfa_required(self) -> bool:
        return self.is_superadmin or any(r in MFA_REQUIRED_ROLES for r in self.roles)

    # Django admin / permission API compatibility (no Django admin is exposed).
    @property
    def is_staff(self) -> bool:
        return False

    def has_perm(self, perm: str, obj: Any = None) -> bool:
        return False

    def has_module_perms(self, app_label: str) -> bool:
        return False


class ActivationInvite(TenantModel):
    """Single-use activation link sent to an agent (EF-09). Only the SHA-256 of the token is kept."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invites")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    sent_to = models.EmailField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "invitation d'activation"
        indexes = [models.Index(fields=["user", "used_at"])]
