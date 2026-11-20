from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts import views as accounts
from apps.attendance import days_views
from apps.attendance import views as attendance
from apps.kiosks import views as kiosks
from apps.notifications import views as notifications
from apps.organization import views as organization
from apps.schedules import views as schedules
from apps.tenancy import views as tenancy

router = DefaultRouter(trailing_slash=True)
router.register("users", accounts.UserViewSet, basename="user")
router.register("sites", organization.SiteViewSet, basename="site")
router.register("org-units", organization.OrgUnitViewSet, basename="org-unit")
router.register("agents", organization.AgentViewSet, basename="agent")
router.register("devices", organization.DeviceViewSet, basename="device")
router.register(
    "device-requests", organization.DeviceChangeRequestViewSet, basename="device-request"
)
router.register("kiosks", kiosks.KioskViewSet, basename="kiosk")
router.register("checkins", attendance.CheckInViewSet, basename="checkin")
router.register("workdays", days_views.WorkDayViewSet, basename="workday")
router.register("periods", days_views.PeriodViewSet, basename="period")
router.register("schedules", schedules.ScheduleViewSet, basename="schedule")
router.register("schedule-assignments", schedules.AssignmentViewSet, basename="schedule-assignment")
router.register("schedule-exceptions", schedules.ExceptionViewSet, basename="schedule-exception")
router.register("holidays", schedules.HolidayViewSet, basename="holiday")
router.register("notifications", notifications.NotificationViewSet, basename="notification")
router.register("platform/companies", tenancy.CompanyViewSet, basename="platform-company")
router.register(
    "platform/subscriptions", tenancy.SubscriptionViewSet, basename="platform-subscription"
)

auth_urls = [
    path("login/", accounts.LoginView.as_view(), name="login"),
    path("mfa/verify/", accounts.MfaVerifyView.as_view(), name="mfa-verify"),
    path("refresh/", accounts.RefreshView.as_view(), name="refresh"),
    path("logout/", accounts.LogoutView.as_view(), name="logout"),
    path("me/", accounts.MeView.as_view(), name="me"),
]

api_v1: list[URLPattern | URLResolver] = [
    path("", include("apps.system.urls")),
    path("auth/", include((auth_urls, "auth"))),
    path("settings/company/", tenancy.CompanySettingsView.as_view(), name="company-settings"),
    path("platform/stats/", tenancy.PlatformStatsView.as_view(), name="platform-stats"),
    path("dashboard/today/", days_views.DashboardView.as_view(), name="dashboard-today"),
    path("kiosk/pair/", kiosks.KioskPairView.as_view(), name="kiosk-pair"),
    path("kiosk/heartbeat/", kiosks.KioskHeartbeatView.as_view(), name="kiosk-heartbeat"),
    path("kiosk/checkins/", kiosks.KioskCheckInView.as_view(), name="kiosk-checkin"),
    path("kiosk/checkins/batch/", kiosks.KioskBatchView.as_view(), name="kiosk-batch"),
    path("mobile/activate/", attendance.MobileActivateView.as_view(), name="mobile-activate"),
    path("mobile/status/", attendance.MobileStatusView.as_view(), name="mobile-status"),
    path("mobile/checkins/", attendance.MobileCheckInView.as_view(), name="mobile-checkin"),
    path(
        "mobile/personal-key/",
        attendance.MobilePersonalKeyView.as_view(),
        name="mobile-personal-key",
    ),
    path(
        "sites/<uuid:pk>/printed-qr/",
        attendance.SitePrintedQrView.as_view(),
        name="site-printed-qr",
    ),
    path("agents/<uuid:pk>/badge/", attendance.AgentBadgeView.as_view(), name="agent-badge"),
    path("", include(router.urls)),
]

urlpatterns = [
    path("api/v1/", include((api_v1, "v1"))),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
