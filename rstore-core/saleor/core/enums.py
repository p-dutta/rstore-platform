import graphene

from ...account import error_codes as account_error_codes
from ...app import error_codes as app_error_codes
from ...checkout import error_codes as checkout_error_codes
from ...core import JobStatus, error_codes as core_error_codes
from ...core.permissions import get_permissions_enum_list
from ...core.weight import WeightUnits
from ...discount import error_codes as discount_error_codes
from ...giftcard import error_codes as giftcard_error_codes
from ...menu import error_codes as menu_error_codes
from ...notice import error_codes as notice_error_codes
from ...order import error_codes as order_error_codes
from ...page import error_codes as page_error_codes
from ...payment import error_codes as payment_error_codes
from ...plugins import error_codes as plugin_error_codes
from ...plugins.vatlayer import TaxRateType as CoreTaxRateType
from ...product import error_codes as product_error_codes
from ...shipping import error_codes as shipping_error_codes
from ...warehouse import error_codes as warehouse_error_codes
from ...webhook import error_codes as webhook_error_codes
from ...wishlist import error_codes as wishlist_error_codes
from ...partner import error_codes as partner_error_codes
from ...notification import error_codes as notification_error_codes
from ...target import error_codes as target_error_codes
from ...commission import error_codes as rule_error_codes
from ...commission.error_codes import CommissionErrorCode as commission_error_codes
from .utils import str_to_enum


# FIXME CoreTaxRateType should be removed after we will drop old api fields dedicated
#  to taxes


class OrderDirection(graphene.Enum):
    ASC = ""
    DESC = "-"

    @property
    def description(self):
        # Disable all the no-member violations in this function
        # pylint: disable=no-member
        if self == OrderDirection.ASC:
            return "Specifies an ascending sort order."
        if self == OrderDirection.DESC:
            return "Specifies a descending sort order."
        raise ValueError("Unsupported enum value: %s" % self.value)


class ReportingPeriod(graphene.Enum):
    TODAY = "TODAY"
    THIS_MONTH = "THIS_MONTH"


def to_enum(enum_cls, *, type_name=None, **options) -> graphene.Enum:
    """Create a Graphene enum from a class containing a set of options.

    :param enum_cls:
        The class to build the enum from.
    :param type_name:
        The name of the type. Default is the class name + 'Enum'.
    :param options:
        - description:
            Contains the type description (default is the class's docstring)
        - deprecation_reason:
            Contains the deprecation reason.
            The default is enum_cls.__deprecation_reason__ or None.
    :return:
    """

    # note this won't work until
    # https://github.com/graphql-python/graphene/issues/956 is fixed
    deprecation_reason = getattr(enum_cls, "__deprecation_reason__", None)
    if deprecation_reason:
        options.setdefault("deprecation_reason", deprecation_reason)

    type_name = type_name or (enum_cls.__name__ + "Enum")
    enum_data = [(str_to_enum(code.upper()), code) for code, name in enum_cls.CHOICES]
    return graphene.Enum(type_name, enum_data, **options)


TaxRateType = graphene.Enum(
    "TaxRateType", [(str_to_enum(rate[0]), rate[0]) for rate in CoreTaxRateType.CHOICES]
)

JobStatusEnum = to_enum(JobStatus)
PermissionEnum = graphene.Enum("PermissionEnum", get_permissions_enum_list())
WeightUnitsEnum = graphene.Enum(
    "WeightUnitsEnum", [(str_to_enum(unit[0]), unit[0]) for unit in WeightUnits.CHOICES]
)

AccountErrorCode = graphene.Enum.from_enum(account_error_codes.AccountErrorCode)
RequestErrorCode = graphene.Enum.from_enum(account_error_codes.RequestErrorCode)
AppErrorCode = graphene.Enum.from_enum(app_error_codes.AppErrorCode)
CheckoutErrorCode = graphene.Enum.from_enum(checkout_error_codes.CheckoutErrorCode)
DiscountErrorCode = graphene.Enum.from_enum(discount_error_codes.DiscountErrorCode)
PluginErrorCode = graphene.Enum.from_enum(plugin_error_codes.PluginErrorCode)
GiftCardErrorCode = graphene.Enum.from_enum(giftcard_error_codes.GiftCardErrorCode)
MenuErrorCode = graphene.Enum.from_enum(menu_error_codes.MenuErrorCode)
MetadataErrorCode = graphene.Enum.from_enum(core_error_codes.MetadataErrorCode)
OrderErrorCode = graphene.Enum.from_enum(order_error_codes.OrderErrorCode)
PageErrorCode = graphene.Enum.from_enum(page_error_codes.PageErrorCode)
PaymentErrorCode = graphene.Enum.from_enum(payment_error_codes.PaymentErrorCode)
PermissionGroupErrorCode = graphene.Enum.from_enum(
    account_error_codes.PermissionGroupErrorCode
)
ProductErrorCode = graphene.Enum.from_enum(product_error_codes.ProductErrorCode)
ShopErrorCode = graphene.Enum.from_enum(core_error_codes.ShopErrorCode)
ShippingErrorCode = graphene.Enum.from_enum(shipping_error_codes.ShippingErrorCode)
StockErrorCode = graphene.Enum.from_enum(warehouse_error_codes.StockErrorCode)
WarehouseErrorCode = graphene.Enum.from_enum(warehouse_error_codes.WarehouseErrorCode)
WebhookErrorCode = graphene.Enum.from_enum(webhook_error_codes.WebhookErrorCode)
WishlistErrorCode = graphene.Enum.from_enum(wishlist_error_codes.WishlistErrorCode)
TranslationErrorCode = graphene.Enum.from_enum(core_error_codes.TranslationErrorCode)
PartnerErrorCode = graphene.Enum.from_enum(partner_error_codes.PartnerErrorCode)
NotificationErrorCode = graphene.Enum.from_enum(notification_error_codes.NotificationErrorCode)
AnnouncementErrorCode = graphene.Enum.from_enum(notification_error_codes.AnnouncementErrorCode)
SegmentErrorCode = graphene.Enum.from_enum(notification_error_codes.SegmentErrorCode)
NotificationMetaErrorCode = graphene.Enum.from_enum(notification_error_codes.NotificationMetaErrorCode)
UserPermissionUpdateErrorCode = graphene.Enum.from_enum(account_error_codes.UserPermissionUpdateErrorCode)
TargetErrorCode = graphene.Enum.from_enum(target_error_codes.TargetErrorCode)
AchievementErrorCode = graphene.Enum.from_enum(target_error_codes.AchievementErrorCode)
RuleErrorCode = graphene.Enum.from_enum(rule_error_codes.RuleErrorCode)
UserProfileErrorCode = graphene.Enum.from_enum(rule_error_codes.UserProfileErrorCode)
CommissionErrorCode = graphene.Enum.from_enum(commission_error_codes)
TargetPartnerSalesErrorCode = graphene.Enum.from_enum(target_error_codes.TargetPartnerSalesErrorCode)
NoticeErrorCode = graphene.Enum.from_enum(notice_error_codes.NoticeErrorCode)
NoticeDocumentErrorCode = graphene.Enum.from_enum(notice_error_codes.NoticeDocumentErrorCode)
