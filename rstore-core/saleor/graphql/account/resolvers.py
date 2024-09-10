from itertools import chain
from typing import Optional

import graphene
from django.contrib.auth import models as auth_models
from django.contrib.auth.models import Group
from django.db.models import Q
from django.shortcuts import get_object_or_404
from graphql_jwt.exceptions import PermissionDenied
from i18naddress import get_validation_rules

from ...account import models, UserApproval
from ...account.models import GroupHierarchy
from ...core.permissions import AccountPermissions
from ...payment import gateway
from ...payment.utils import fetch_customer_id
from ..utils import format_permissions_for_display, get_user_or_app_from_context, get_child_group_names
from ..utils.filters import filter_by_query_param
from .types import AddressValidationData, ChoiceValue
from .utils import (
    get_allowed_fields_camel_case,
    get_required_fields_camel_case,
    get_user_permissions,
)

USER_SEARCH_FIELDS = (
    "email",
    "first_name",
    "last_name",
    "default_shipping_address__first_name",
    "default_shipping_address__last_name",
    "default_shipping_address__city",
    "default_shipping_address__country",
)

AGENT_SEARCH_FIELD = (
    "phone",
    "email",
    "first_name",
    "last_name",
)


def resolve_customers(info, query, **_kwargs):
    qs = models.User.objects.customers()
    qs = filter_by_query_param(
        queryset=qs, query=query, search_fields=USER_SEARCH_FIELDS
    )
    return qs.distinct()


def resolve_permission_groups(info, **_kwargs):
    return auth_models.Group.objects.all()


def resolve_staff_users(info, query, **_kwargs):
    children_list = info.context.user.get_children()
    if _kwargs.get("group"):
        qs = models.User.objects.staff().filter(Q(groups__name__iexact=_kwargs.get("group")) & Q(id__in=children_list))
    else:
        qs = models.User.objects.staff().filter(Q(id__in=children_list))

    return qs.distinct()


def resolve_user(info, id):
    requester = get_user_or_app_from_context(info.context)
    if requester:
        _model, user_pk = graphene.Node.from_global_id(id)
        if requester.has_perms(
                [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_USERS]
        ):
            return models.User.objects.filter(pk=user_pk).first()
        if requester.has_perm(AccountPermissions.MANAGE_STAFF):
            return models.User.objects.staff().filter(pk=user_pk).first()
        if requester.has_perm(AccountPermissions.VIEW_STAFF):
            return models.User.objects.filter(pk=user_pk).first()
        if requester.has_perm(AccountPermissions.MANAGE_USERS):
            return models.User.objects.customers().filter(pk=user_pk).first()
    return PermissionDenied()


def resolve_address_validation_rules(
        info,
        country_code: str,
        country_area: Optional[str],
        city: Optional[str],
        city_area: Optional[str],
):
    params = {
        "country_code": country_code,
        "country_area": country_area,
        "city": city,
        "city_area": city_area,
    }
    rules = get_validation_rules(params)
    return AddressValidationData(
        country_code=rules.country_code,
        country_name=rules.country_name,
        address_format=rules.address_format,
        address_latin_format=rules.address_latin_format,
        allowed_fields=get_allowed_fields_camel_case(rules.allowed_fields),
        required_fields=get_required_fields_camel_case(rules.required_fields),
        upper_fields=rules.upper_fields,
        country_area_type=rules.country_area_type,
        country_area_choices=[
            ChoiceValue(area[0], area[1]) for area in rules.country_area_choices
        ],
        city_type=rules.city_type,
        city_choices=[ChoiceValue(area[0], area[1]) for area in rules.city_choices],
        city_area_type=rules.city_type,
        city_area_choices=[
            ChoiceValue(area[0], area[1]) for area in rules.city_area_choices
        ],
        postal_code_type=rules.postal_code_type,
        postal_code_matchers=[
            compiled.pattern for compiled in rules.postal_code_matchers
        ],
        postal_code_examples=rules.postal_code_examples,
        postal_code_prefix=rules.postal_code_prefix,
    )


def resolve_payment_sources(user: models.User):
    stored_customer_accounts = (
        (gtw["id"], fetch_customer_id(user, gtw["id"]))
        for gtw in gateway.list_gateways()
    )
    return list(
        chain(
            *[
                prepare_graphql_payment_sources_type(
                    gateway.list_payment_sources(gtw, customer_id)
                )
                for gtw, customer_id in stored_customer_accounts
                if customer_id is not None
            ]
        )
    )


def prepare_graphql_payment_sources_type(payment_sources):
    sources = []
    for src in payment_sources:
        sources.append(
            {
                "gateway": src.gateway,
                "credit_card_info": {
                    "last_digits": src.credit_card_info.last_4,
                    "exp_year": src.credit_card_info.exp_year,
                    "exp_month": src.credit_card_info.exp_month,
                    "brand": "",
                    "first_digits": "",
                },
            }
        )
    return sources


def resolve_address(info, id):
    user = info.context.user
    app = info.context.app
    _model, address_pk = graphene.Node.from_global_id(id)
    if app and app.has_perm(AccountPermissions.MANAGE_USERS):
        return models.Address.objects.filter(pk=address_pk).first()
    if user and not user.is_anonymous:
        return user.addresses.filter(id=address_pk).first()
    return PermissionDenied()


def resolve_permissions(root: models.User):
    permissions = get_user_permissions(root)
    permissions = permissions.prefetch_related("content_type").order_by("codename")
    return format_permissions_for_display(permissions)


def resolve_districts(info):
    return models.District.objects.all()


def resolve_thanas(info, district_id):
    _model, pk = graphene.Node.from_global_id(district_id)
    return models.Thana.objects.filter(district_id=pk)


def resolve_all_thanas(info):
    return models.Thana.objects.all()


def resolve_tuple(array: list):
    values = []
    for ar in array:
        values.append({'key': ar[0], 'label': ar[1]})
    return values


def resolve_mfs_account_types():
    return models.MFSAccountType.objects.all()


def resolve_agent_requests(info, query, **_kwargs):
    requester = info.context.user
    if requester.groups.filter(name='admin').exists():
        qs = models.UserRequest.objects.all().order_by('-created')
    else:
        qs = models.UserRequest.objects.filter(assigned_id=requester).order_by('-created')

    valid_requests_ids = []
    used = {}

    for item in qs:
        if used.get(item.user_id) != item.status:
            used[item.user_id] = item.status
            valid_requests_ids.append(item.id)

    return qs.filter(id__in=valid_requests_ids)


def resolve_agent_request_search(info, query, **_kwargs):
    requester = info.context.user
    if requester.groups.filter(name='admin').exists():
        qs = models.UserRequest.objects.all().order_by('-created')
    else:
        qs = models.UserRequest.objects.filter(assigned_id=requester).order_by('-created')
    valid_requests_ids = []
    used = {}

    for item in qs:
        if used.get(item.user_id) != item.status:
            used[item.user_id] = item.status
            valid_requests_ids.append(item.id)

    return qs.filter(id__in=valid_requests_ids)


def resolve_requested_agent(info, query, **_kwargs):
    requester = info.context.user
    _model, request_pk = graphene.Node.from_global_id(_kwargs.get("id"))
    agent_request = models.UserRequest.objects.get(pk=request_pk)

    if (requester.id == agent_request.assigned_id) or requester.groups.filter(name='admin').exists():
        return agent_request
    else:
        return None





def resolve_all_permissions(info):
    from .resolvers import resolve_permissions
    return resolve_permissions(models.User)


def resolve_stores(info, district, thana):
    district_id = None
    thana_id = None

    if district:
        _, district_id = graphene.Node.from_global_id(district)
    if thana:
        _, thana_id = graphene.Node.from_global_id(thana)

    q = Q(approval_status=UserApproval.APPROVED) & Q(is_active=True) & Q(groups__name__icontains='agent')
    # patch: exclude non robi/airtel numbers
    q &= Q(phone__iregex=r'01(6|8)\d{8}')
    if district_id:
        q &= Q(regions__district__id=district_id)
    if thana_id:
        q &= Q(regions__thana__id=thana_id)

    queryset_users = models.User.objects.filter(q)

    return queryset_users.distinct()


def resolve_user_correction_request_search(info, query, **_kwargs):
    requester = info.context.user
    if requester.groups.filter(name='admin').exists():
        qs = models.UserCorrectionRequest.objects.all().order_by('-created')
    else:
        qs = models.UserCorrectionRequest.objects.filter(assigned_id=requester).order_by('-created')
    valid_requests_ids = []
    used = {}

    for item in qs:
        if used.get(item.user_id) != item.status:
            used[item.user_id] = item.status
            valid_requests_ids.append(item.id)

    return qs.filter(id__in=valid_requests_ids)


def resolve_user_correction_requests(info, **kwargs):
    user = info.context.user

    if user.groups.filter(name='admin').exists():
        qs = models.UserCorrectionRequest.objects.all()
    else:
        children = user.get_children()
        qs = models.UserCorrectionRequest.objects.filter(user__in=children)
    return qs


def resolve_user_correction_request(id):
    _, user_correction_request_pk = graphene.Node.from_global_id(id)
    return models.UserCorrectionRequest.objects.get(id=user_correction_request_pk)


def resolve_group_map():
    return GroupHierarchy.objects.all()


def resolve_groups(info):
    return auth_models.Group.objects.all()


def resolve_user_manageable_groups(info):
    user = info.context.user
    if user.is_authenticated:
        request_user_grp_id = user.groups.first().id
        has_hierarchy = GroupHierarchy.objects.filter(
            Q(parent_id=request_user_grp_id) | Q(child_id=request_user_grp_id)
        ).exists()
        if has_hierarchy:
            child_groups = get_child_group_names(user.groups.first(), True)
            return auth_models.Group.objects.filter(name__in=child_groups)
        else:
            return Group.objects.filter(parent_group__has_txn=True)
    return []

