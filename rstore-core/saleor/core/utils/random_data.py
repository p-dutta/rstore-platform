import random
import unicodedata

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.utils.text import slugify
from faker import Factory
from faker.providers import BaseProvider
from measurement.measures import Weight
from prices import Money
from django.db.models import F, Value
from django.db.models.functions import Replace

from .. import admin_connector
from ...account.models import Address
from ...core.permissions import (
    AccountPermissions,
    OrderPermissions,
    get_permissions, get_permissions_codename,
    PartnerPermissions, ProductPermissions, TargetPermissions, NotificationPermissions, LogPermissions, RulePermissions,
    CommissionPermissions, NoticePermissions, AnnouncementPermissions, NotificationMetaPermissions
)
from ...core.weight import zero_weight
from ...product.models import ProductType
from ...shipping.models import ShippingMethod, ShippingMethodType, ShippingZone
from ...warehouse.models import Warehouse

fake = Factory.create()
keycloak_roles = []


def get_weight(weight):
    if not weight:
        return zero_weight()
    value, unit = weight.split(":")
    return Weight(**{unit: value})


class SaleorProvider(BaseProvider):
    def default_shipping_charge(self):
        return Money(0, settings.DEFAULT_CURRENCY)

    def weight(self):
        return Weight(kg=fake.pydecimal(1, 2, positive=True))


fake.add_provider(SaleorProvider)


def get_email(first_name, last_name):
    _first = unicodedata.normalize("NFD", first_name).encode("ascii", "ignore")
    _last = unicodedata.normalize("NFD", last_name).encode("ascii", "ignore")
    return "%s.%s@example.com" % (
        _first.lower().decode("utf-8"),
        _last.lower().decode("utf-8"),
    )


def create_address(save=True):
    address = Address(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        street_address_1=fake.street_address(),
        city=fake.city(),
        country=settings.DEFAULT_COUNTRY,
    )

    if address.country == "US":
        state = fake.state_abbr()
        address.country_area = state
        address.postal_code = fake.postalcode_in_state(state)
    else:
        address.postal_code = fake.postalcode()

    if save:
        address.save()
    return address


def create_permission_groups():
    permissions = get_permissions()

    for permission in permissions:
        response = create_keycloak_roles(permission)
        yield f"Role: {response}"

    global keycloak_roles
    keycloak_roles = admin_connector.get_realm_roles()

    admin_codenames = [OrderPermissions.VIEW_ORDER.codename,
                       NoticePermissions.MANAGE_NOTICES.codename,
                       NoticePermissions.VIEW_NOTICES.codename,
                       PartnerPermissions.VIEW_PARTNER.codename,
                       PartnerPermissions.MANAGE_PARTNERS.codename,
                       OrderPermissions.MANAGE_ORDERS.codename,
                       TargetPermissions.VIEW_TARGET.codename,
                       TargetPermissions.MANAGE_TARGETS.codename,
                       AccountPermissions.VIEW_STAFF.codename,
                       AccountPermissions.VIEW_USER.codename,
                       AccountPermissions.MANAGE_STAFF.codename,
                       AccountPermissions.UPLOAD_DOCUMENT.codename,
                       ProductPermissions.VIEW_PRODUCT.codename,
                       ProductPermissions.MANAGE_PRODUCTS.codename,
                       NotificationPermissions.MANAGE_NOTIFICATIONS.codename,
                       NotificationPermissions.VIEW_NOTIFICATIONS.codename,
                       NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename,
                       LogPermissions.VIEW_LOGS.codename,
                       RulePermissions.MANAGE_RULES.codename,
                       RulePermissions.VIEW_RULE.codename,
                       CommissionPermissions.VIEW_COMMISSION.codename,
                       CommissionPermissions.MANAGE_COMMISSIONS.codename,
                       AccountPermissions.MANAGE_REPORTS.codename,
                       AnnouncementPermissions.MANAGE_ANNOUNCEMENTS.codename,
                       AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename,
                       ]

    group = create_group("admin", admin_codenames)
    yield f"Group: {group}"

    agent_codenames = [OrderPermissions.VIEW_ORDER.codename,
                       TargetPermissions.VIEW_TARGET.codename,
                       PartnerPermissions.VIEW_PARTNER.codename,
                       ProductPermissions.VIEW_PRODUCT.codename,
                       AccountPermissions.VIEW_USER.codename,
                       AccountPermissions.UPDATE_KYC.codename,
                       AccountPermissions.UPLOAD_DOCUMENT.codename,
                       AccountPermissions.UPDATE_PROFILE.codename,
                       RulePermissions.VIEW_RULE.codename,
                       NoticePermissions.VIEW_NOTICES.codename,
                       NotificationPermissions.VIEW_NOTIFICATIONS.codename,
                       NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename,
                       CommissionPermissions.VIEW_COMMISSION.codename,
                       AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename,
                       ]

    group = create_group("agent", agent_codenames)
    yield f"Group: {group}"

    cm_codenames = [OrderPermissions.VIEW_ORDER.codename,
                    TargetPermissions.VIEW_TARGET.codename,
                    TargetPermissions.MANAGE_TARGETS.codename,
                    AccountPermissions.VIEW_USER.codename,
                    AccountPermissions.MANAGE_REQUESTS.codename,
                    AccountPermissions.VIEW_STAFF.codename,
                    AccountPermissions.REMOVE_STAFF.codename,
                    AccountPermissions.CHANGE_USER.codename,
                    AccountPermissions.VIEW_USERCORRECTION.codename,
                    AccountPermissions.PROCESS_USERCORRECTION.codename,
                    PartnerPermissions.VIEW_PARTNER.codename,
                    ProductPermissions.VIEW_PRODUCT.codename,
                    RulePermissions.VIEW_RULE.codename,
                    CommissionPermissions.VIEW_COMMISSION.codename,
                    AccountPermissions.MANAGE_REPORTS.codename,
                    NoticePermissions.VIEW_NOTICES.codename,
                    NotificationPermissions.VIEW_NOTIFICATIONS.codename,
                    NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename,
                    AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename,
                    ]

    group = create_group("cm", cm_codenames)
    yield f"Group: {group}"

    dcm_codenames = [OrderPermissions.VIEW_ORDER.codename,
                     TargetPermissions.VIEW_TARGET.codename,
                     TargetPermissions.MANAGE_TARGETS.codename,
                     AccountPermissions.VIEW_STAFF.codename,
                     AccountPermissions.VIEW_USER.codename,
                     AccountPermissions.VIEW_USERCORRECTION.codename,
                     AccountPermissions.REQUEST_USERCORRECTION.codename,
                     PartnerPermissions.VIEW_PARTNER.codename,
                     ProductPermissions.VIEW_PRODUCT.codename,
                     RulePermissions.VIEW_RULE.codename,
                     CommissionPermissions.VIEW_COMMISSION.codename,
                     NoticePermissions.VIEW_NOTICES.codename,
                     NotificationPermissions.VIEW_NOTIFICATIONS.codename,
                     NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename,
                     AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename,
                     ]

    group = create_group("dcm", dcm_codenames)
    yield f"Group: {group}"

    dco_codenames = [OrderPermissions.VIEW_ORDER.codename,
                     TargetPermissions.VIEW_TARGET.codename,
                     TargetPermissions.MANAGE_TARGETS.codename,
                     AccountPermissions.MANAGE_REQUESTS.codename,
                     AccountPermissions.VIEW_STAFF.codename,
                     AccountPermissions.VIEW_USER.codename,
                     AccountPermissions.VIEW_USERCORRECTION.codename,
                     AccountPermissions.REQUEST_USERCORRECTION.codename,
                     PartnerPermissions.VIEW_PARTNER.codename,
                     ProductPermissions.VIEW_PRODUCT.codename,
                     RulePermissions.VIEW_RULE.codename,
                     CommissionPermissions.VIEW_COMMISSION.codename,
                     NoticePermissions.VIEW_NOTICES.codename,
                     NotificationPermissions.VIEW_NOTIFICATIONS.codename,
                     NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename,
                     AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename,
                     ]

    group = create_group("dco", dco_codenames)
    yield f"Group: {group}"

    sp_codenames = [OrderPermissions.VIEW_ORDER.codename,
                    OrderPermissions.MANAGE_ORDERS.codename,
                    TargetPermissions.VIEW_TARGET.codename,
                    TargetPermissions.MANAGE_TARGETS.codename,
                    AccountPermissions.UPLOAD_DOCUMENT.codename,
                    AccountPermissions.VIEW_USER.codename,
                    NoticePermissions.MANAGE_NOTICES.codename,
                    NoticePermissions.VIEW_NOTICES.codename,
                    NotificationPermissions.VIEW_NOTIFICATIONS.codename,
                    NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename,
                    RulePermissions.MANAGE_RULES.codename,
                    RulePermissions.VIEW_RULE.codename,
                    ProductPermissions.VIEW_PRODUCT.codename,
                    CommissionPermissions.VIEW_COMMISSION.codename,
                    CommissionPermissions.MANAGE_COMMISSIONS.codename,
                    AccountPermissions.MANAGE_REPORTS.codename,
                    PartnerPermissions.VIEW_PARTNER.codename,
                    AccountPermissions.MANAGE_STAFF.codename,
                    AccountPermissions.VIEW_STAFF.codename,
                    AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename,
                    ]

    group = create_group("sp", sp_codenames)
    yield f"Group: {group}"

    mgt_codenames = [OrderPermissions.VIEW_ORDER.codename,
                     OrderPermissions.MANAGE_ORDERS.codename,
                     TargetPermissions.VIEW_TARGET.codename,
                     TargetPermissions.MANAGE_TARGETS.codename,
                     AccountPermissions.VIEW_STAFF.codename,
                     AccountPermissions.VIEW_USER.codename,
                     AccountPermissions.MANAGE_STAFF.codename,
                     RulePermissions.MANAGE_RULES.codename,
                     RulePermissions.VIEW_RULE.codename,
                     ProductPermissions.VIEW_PRODUCT.codename,
                     CommissionPermissions.VIEW_COMMISSION.codename,
                     CommissionPermissions.MANAGE_COMMISSIONS.codename,
                     AccountPermissions.MANAGE_REPORTS.codename,
                     PartnerPermissions.VIEW_PARTNER.codename,
                     AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename,
                     NotificationPermissions.VIEW_NOTIFICATIONS.codename,
                     NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename,
                     ]

    group = create_group("mgt", mgt_codenames)
    yield f"Group: {group}"


def create_keycloak_roles(permission):
    try:
        admin_connector.create_realm_role({'name': permission.codename, 'description': permission.name})
        return "Role with name %s created" % permission.codename
    except Exception as e:
        return e


def create_group(name, codenames):
    keycloak_group = create_or_get_keycloak_group(name)
    if keycloak_group:
        assign_keycloak_group_role(name, codenames)
    else:
        return 'Something went wrong with identity provider'

    permissions = Permission.objects.filter(
        codename__in=codenames
    )

    group, _ = Group.objects.get_or_create(name=name)
    group.permissions.add(*permissions)

    return "%s" % group


def create_or_get_keycloak_group(name):
    response = True
    try:
        admin_connector.create_group({'name': name})
    except Exception as e:
        if e.response_code != 409:
            response = False

    return response


def assign_keycloak_group_role(name, codenames):
    roles = []
    group_id = admin_connector.get_group_by_name(group_name='/' + name)['id']
    for codename in codenames:
        role = get_role_by_name(codename)
        roles.append(role)
    admin_connector.assign_group_realm_roles(group_id=group_id, roles=roles)


def get_role_by_name(codename):
    for role in keycloak_roles:
        if role['name'] == codename:
            return role


def create_shipping_zone(shipping_methods_names, countries, shipping_zone_name):
    shipping_zone = ShippingZone.objects.get_or_create(
        name=shipping_zone_name, defaults={"countries": countries}, default=True
    )[0]
    ShippingMethod.objects.bulk_create(
        [
            ShippingMethod(
                name=name,
                price=fake.default_shipping_charge(),
                shipping_zone=shipping_zone,
                type=(
                    ShippingMethodType.PRICE_BASED
                    if random.randint(0, 1)
                    else ShippingMethodType.WEIGHT_BASED
                ),
                minimum_order_price=Money(0, settings.DEFAULT_CURRENCY),
                maximum_order_price_amount=None,
                minimum_order_weight=0,
                maximum_order_weight=None,
            )
            for name in shipping_methods_names
        ]
    )
    return "Shipping Zone: %s" % shipping_zone


def create_shipping_zones():
    countries = [
        "BD",
    ]
    yield create_shipping_zone(
        shipping_zone_name="Bangladesh",
        countries=countries,
        shipping_methods_names=["Default Shipping"],
    )


def create_warehouse_address():
    first_name = 'Robi'
    last_name = 'Corporate Office'
    company_name = "RStore"
    phone = "09610000888"
    city = "Dhaka"
    postal_code = 1212
    street_address_1 = "53, Nafi Tower"
    street_address_2 = "Gulshan South Avenue, Gulshan 1"

    address = Address(
        first_name=first_name,
        last_name=last_name,
        company_name=company_name,
        phone=phone,
        street_address_1=street_address_1,
        street_address_2=street_address_2,
        city=city,
        country=settings.DEFAULT_COUNTRY,
        postal_code=postal_code,
    )
    address.save()
    return address


def create_warehouses():
    for shipping_zone in ShippingZone.objects.all():
        shipping_zone_name = shipping_zone.name
        warehouse, _ = Warehouse.objects.update_or_create(
            name=shipping_zone_name,
            slug=slugify(shipping_zone_name),
            defaults={"company_name": "RStore", "address": create_warehouse_address()},
        )
        warehouse.shipping_zones.add(shipping_zone)


def create_product_types():
    defaults = {
        "name": "Default",
        "slug": "default",
        "has_variants": False,
        "is_shipping_required": True,
        "is_digital": False,
        "weight": "0.0:kg"
    }

    defaults["weight"] = get_weight(defaults["weight"])
    ProductType.objects.update_or_create(defaults=defaults)


def rename_permission_start_names():
    all_keycloak_roles = admin_connector.get_realm_roles()
    role_names = []
    for role in all_keycloak_roles:
        role_names.append(role['name'])
    updated_permissions = _update_permissions_name("Can view ", "View ", role_names)
    updated_permissions += _update_permissions_name("Can manage ", "Manage ", role_names)

    return updated_permissions


def _update_permissions_name(existing_start_name, update_start_name, role_names):
    keycloak_role_permissions = Permission.objects.filter(codename__in=role_names)
    existing_permissions = keycloak_role_permissions.filter(name__startswith=existing_start_name)

    perms_updated = existing_permissions.update(
        codename=F('codename'),
        name=Replace('name', Value(existing_start_name), Value(update_start_name))
    )

    updated_permissions = keycloak_role_permissions.filter(name__startswith=update_start_name)
    for perm in updated_permissions:
        admin_connector.update_role_by_name(perm.codename, perm.name)
    return perms_updated
