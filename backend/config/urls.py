from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.accounts import views as accounts
from apps.attendance import days_views, me_views
from apps.attendance import views as attendance
from apps.audit import views as audit
from apps.kiosks import views as kiosks
from apps.notifications import views as notifications
from apps.organization import views as organization
from apps.reports import views as reports
from apps.requests_app import views as requests_views
from apps.schedules import views as schedules
from apps.tenancy import views as tenancy
from common.downloads import SignedDownloadView

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
router.register("requests", requests_views.RequestViewSet, basename="request")
router.register("audit-logs", audit.AuditLogViewSet, basename="audit-log")
router.register("reports", reports.ReportJobViewSet, basename="report")
router.register("report-schedules", reports.ReportScheduleViewSet, basename="report-schedule")
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
    path("me/history/", me_views.MyHistoryView.as_view(), name="me-history"),
    path("me/export/", me_views.MyExportView.as_view(), name="me-export"),
    path("corrections/", me_views.CorrectionView.as_view(), name="corrections"),
    path("files/", SignedDownloadView.as_view(), name="files"),
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
