from rest_framework.pagination import CursorPagination, LimitOffsetPagination


class StandardPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 500


class TimelineCursorPagination(CursorPagination):
    """Stable pagination for append-only timelines (check-ins, audit log)."""

    page_size = 100
    max_page_size = 500
    page_size_query_param = "page_size"
    ordering = "-created_at"
