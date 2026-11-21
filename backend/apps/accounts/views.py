from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record
from apps.tenancy.resolver import REFRESH_COOKIE
from common.exceptions import DomainError

from . import invitations, services
from .models import User
from .permissions import IsCompanyAdmin
from .serializers import (
    ActivationInfoSerializer,
    ActivationSerializer,
    AuthResponseSerializer,
    LoginSerializer,
    MeSerializer,
    MfaVerifySerializer,
    UserSerializer,
)
from .tokens import IssuedTokens, clear_refresh_cookie, issue_tokens, set_refresh_cookie


def _authenticated(user: User, tokens: IssuedTokens) -> Response:
    response = Response(
        {"step": "authenticated", "access": tokens.access, "user": MeSerializer(user).data}
    )
    set_refresh_cookie(response, tokens.refresh)
    return response


class AuthThrottled(APIView):
    authentication_classes: list[Any] = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LoginView(AuthThrottled):
    @extend_schema(
        operation_id="auth_login",
        request=LoginSerializer,
        responses=AuthResponseSerializer,
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        company = services.resolve_login_company(
            getattr(request._request, "company", None), data.validated_data.get("company_code", "")
        )
        outcome = services.login(
            request._request,
            company=company,
            username=data.validated_data["username"],
            password=data.validated_data["password"],
        )
        if outcome.step == "authenticated" and outcome.tokens:
            return _authenticated(outcome.user, outcome.tokens)
        body: dict[str, Any] = {"step": outcome.step, "mfa_token": outcome.mfa_token}
        if outcome.step == "mfa_setup":
            body |= {"otpauth_url": outcome.otpauth_url, "secret": outcome.secret}
        return Response(body)


class ActivationView(AuthThrottled):
    """EF-09: an invited agent checks their link, then chooses a password and is signed in."""

    @extend_schema(
        operation_id="auth_activation_check",
        parameters=[
            OpenApiParameter("entreprise", str, required=True),
            OpenApiParameter("jeton", str, required=True),
        ],
        responses=ActivationInfoSerializer,
        tags=["auth"],
    )
    def get(self, request: Request) -> Response:
        company = services.resolve_login_company(None, request.query_params.get("entreprise", ""))
        if company is None:
            raise DomainError("Code entreprise manquant.", code="unknown_company", status_code=404)
        return Response(invitations.check(company, request.query_params.get("jeton", "")))

    @extend_schema(
        operation_id="auth_activate",
        request=ActivationSerializer,
        responses=AuthResponseSerializer,
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        data = ActivationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        company = services.resolve_login_company(None, data.validated_data["company_code"])
        if company is None:
            raise DomainError("Code entreprise manquant.", code="unknown_company", status_code=404)
        user = invitations.activate(
            company,
            data.validated_data["token"],
            data.validated_data["password"],
            request=request._request,
        )
        if user.mfa_required:  # privileged account: the usual sign-in with its second factor
            return Response({"step": "activated"})
        return _authenticated(user, issue_tokens(user, mfa=False))


class MfaVerifyView(AuthThrottled):
    @extend_schema(
        operation_id="auth_mfa_verify",
        request=MfaVerifySerializer,
        responses=AuthResponseSerializer,
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        data = MfaVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.verify_mfa(
            request._request,
            mfa_token=data.validated_data["mfa_token"],
            code=data.validated_data["code"],
        )
        return _authenticated(user, issue_tokens(user, mfa=True))


class RefreshView(AuthThrottled):
    throttle_scope = "refresh"

    @extend_schema(
        operation_id="auth_refresh", request=None, responses=AuthResponseSerializer, tags=["auth"]
    )
    def post(self, request: Request) -> Response:
        user, tokens = services.rotate_refresh(request.COOKIES.get(REFRESH_COOKIE))
        return _authenticated(user, tokens)


class LogoutView(AuthThrottled):
    @extend_schema(operation_id="auth_logout", request=None, responses={204: None}, tags=["auth"])
    def post(self, request: Request) -> Response:
        services.logout(request.COOKIES.get(REFRESH_COOKIE))
        response = Response(status=204)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    @extend_schema(operation_id="auth_me", responses=MeSerializer, tags=["auth"])
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)  # type: ignore[arg-type]


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet[User],
):
    """Company accounts and roles. Deactivate instead of deleting (audit trail)."""

    serializer_class = UserSerializer
    permission_classes = [IsCompanyAdmin]
    queryset = User.objects.none()
    search_fields = ["username", "display_name", "email"]

    def get_queryset(self) -> Any:
        return User.objects.filter(company=self.request._request.company).order_by("username")  # type: ignore[attr-defined]

    def perform_create(self, serializer: Any) -> None:
        user = serializer.save()
        record(
            "user.created",
            user,
            actor=self.request.user,
            request=self.request._request,
            after={"username": user.username, "roles": user.roles},
        )

    def perform_update(self, serializer: Any) -> None:
        before = {"roles": serializer.instance.roles, "is_active": serializer.instance.is_active}
        user = serializer.save()
        record(
            "user.updated",
            user,
            actor=self.request.user,
            request=self.request._request,
            before=before,
            after={"roles": user.roles, "is_active": user.is_active},
        )
