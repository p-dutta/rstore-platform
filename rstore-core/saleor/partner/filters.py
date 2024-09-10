import django_filters

from ..core.types import FilterInputObjectType
from ...partner.models import Partner
from ...search.backends import picker


def filter_search(qs, _, value):
    if value:
        search = picker.pick_backend()
        qs &= search(value).distinct()
    return qs


class PartnerFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_search)

    class Meta:
        model = Partner
        fields = [
            "name",
            "account_code",
            "search",
        ]


class PartnerFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = PartnerFilter
