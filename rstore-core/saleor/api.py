from graphene_federation import build_schema

from .account.schema import AccountMutations, AccountQueries, AccountDataQueries, UserCorrectionQueries, GroupMapQueries
from .app.schema import AppMutations, AppQueries
from .auditlog.schema import LogQueries
from .checkout.schema import CheckoutMutations, CheckoutQueries
from .core.schema import CoreMutations, CoreQueries
from .discount.schema import DiscountMutations, DiscountQueries
from .giftcard.schema import GiftCardMutations, GiftCardQueries
from .menu.schema import MenuMutations, MenuQueries
from .meta.schema import MetaMutations
from .notice.schema import NoticeMutations, NoticeQueries
from .order.schema import OrderMutations, OrderQueries
from .page.schema import PageMutations, PageQueries
from .payment.schema import PaymentMutations, PaymentQueries
from .plugins.schema import PluginsMutations, PluginsQueries
from .product.schema import ProductMutations, ProductQueries
from .commission.schema import RuleQueries, RuleMutations, CommissionQueries, UserProfileMutations, UserProfileQueries, \
    CommissionMutations
from .shipping.schema import ShippingMutations, ShippingQueries
from .shop.schema import ShopMutations, ShopQueries
from .target.schema import TargetQueries, AchievementQueries, TargetMutations, PartnerTargetSalesQueries
from .translations.schema import TranslationQueries
from .warehouse.schema import StockQueries, WarehouseMutations, WarehouseQueries
from .webhook.schema import WebhookMutations, WebhookQueries
from .partner.schema import PartnerQueries, PartnerMutations
from .notification.schema import AnnouncementQueries, AnnouncementMutations, SegmentMutations, SegmentQueries, \
    NotificationQueries, NotificationMetaMutations


class Query(
    AccountQueries,
    AppQueries,
    CheckoutQueries,
    CoreQueries,
    DiscountQueries,
    PluginsQueries,
    GiftCardQueries,
    MenuQueries,
    OrderQueries,
    PageQueries,
    PaymentQueries,
    ProductQueries,
    ShippingQueries,
    ShopQueries,
    StockQueries,
    TranslationQueries,
    WarehouseQueries,
    WebhookQueries,
    AccountDataQueries,
    PartnerQueries,
    AnnouncementQueries,
    SegmentQueries,
    NotificationQueries,
    TargetQueries,
    AchievementQueries,
    LogQueries,
    CommissionQueries,
    RuleQueries,
    UserProfileQueries,
    PartnerTargetSalesQueries,
    UserCorrectionQueries,
    NoticeQueries,
    GroupMapQueries,
):
    pass


class Mutation(
    AccountMutations,
    AppMutations,
    CheckoutMutations,
    CoreMutations,
    DiscountMutations,
    PluginsMutations,
    GiftCardMutations,
    MenuMutations,
    MetaMutations,
    OrderMutations,
    PageMutations,
    PaymentMutations,
    ProductMutations,
    ShippingMutations,
    ShopMutations,
    WarehouseMutations,
    WebhookMutations,
    PartnerMutations,
    AnnouncementMutations,
    SegmentMutations,
    TargetMutations,
    RuleMutations,
    UserProfileMutations,
    CommissionMutations,
    NoticeMutations,
    NotificationMetaMutations,
):
    pass


schema = build_schema(Query, mutation=Mutation)
