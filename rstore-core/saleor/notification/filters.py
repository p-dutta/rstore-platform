import django_filters

from ..core.types import FilterInputObjectType
from ..utils.filters import filter_by_query_param
from ...notification.models import Announcement, Segment
from ...search.backends import picker


def filter_search(qs, _, value):
    if value:
        search = picker.pick_backend()
        qs &= search(value).distinct()
    return qs


def filter_search_segment(qs, _, value):
    qs = filter_by_query_param(
        queryset=qs, query=value, search_fields=["name", "details"]
    )
    return qs


class AnnouncementFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_search)

    class Meta:
        model = Announcement
        fields = [
            "title",
            "search",
        ]


class SegmentFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_search_segment)

    class Meta:
        model = Segment
        fields = [
            "search"
        ]


class NotificationFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = AnnouncementFilter


class SegmentFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = SegmentFilter
