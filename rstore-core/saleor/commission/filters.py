import django_filters

from ..core.types import FilterInputObjectType
from ..utils.filters import filter_by_query_param
from ...commission.models import Rule, Commission
from ...commission import CommissionStatus, RuleCategory


def filter_search(qs, _, value):
    search_fields = (
        "name",
        "type",
        "category",
        "commission_category",
        "is_active",
        "created",
        "updated",
    )
    if value:
        qs = filter_by_query_param(qs, value, search_fields)
    return qs


def filter_is_active(qs, filter_field, value):
    lookup = {f"{filter_field}__icontains": value}
    qs = qs.filter(**lookup)
    return qs


def filter_status(qs, filter_field, value):
    lookup = {f"{filter_field}__contains": value}
    qs = qs.filter(**lookup)
    return qs


def filter_rule_category(qs, filter_field, value):
    lookup = {f"{filter_field}__contains": value}
    qs = qs.filter(**lookup)
    return qs


class CommissionFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(method=filter_status, choices=CommissionStatus.CHOICES)
    rule_category = django_filters.ChoiceFilter(method=filter_rule_category, choices=RuleCategory.CHOICES)

    class Meta:
        model = Commission
        fields = [
            "status",
            "rule_category"
        ]


class CommissionFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CommissionFilter


class RuleFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_search)
    is_active = django_filters.BooleanFilter(method=filter_is_active)

    class Meta:
        model = Rule
        fields = [
            "search",
            "is_active",
        ]


class RuleFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RuleFilter
