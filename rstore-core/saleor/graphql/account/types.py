import json

import graphene
from django.contrib.auth import get_user_model, models as auth_models
from graphene import relay
from graphene.types.generic import GenericScalar
from graphene_federation import key
from graphql_jwt.exceptions import PermissionDenied

from ...account import models
from ...checkout.utils import get_user_checkout
from ...core.permissions import AccountPermissions, OrderPermissions
from ...order import models as order_models
from ..checkout.types import Checkout
from ..core.connection import CountableDjangoObjectType
from ..core.fields import PrefetchingConnectionField
from ..core.types import CountryDisplay, Image, Permission
from ..core.utils import from_global_id_strict_type
from ..decorators import one_of_permissions_required, permission_required
from ..meta.deprecated.resolvers import resolve_meta, resolve_private_meta
from ..meta.types import ObjectWithMetadata
from ..utils import format_permissions_for_display, get_immediate_parent
from ..wishlist.resolvers import resolve_wishlist_items_from_user
from .enums import CountryCodeEnum, CustomerEventsEnum
from .utils import can_user_manage_group, get_groups_which_user_can_manage


class AddressInput(graphene.InputObjectType):
    first_name = graphene.String(description="Given name.")
    last_name = graphene.String(description="Family name.")
    company_name = graphene.String(description="Company or organization.")
    street_address_1 = graphene.String(description="Address.")
    street_address_2 = graphene.String(description="Address.")
    city = graphene.String(description="City.")
    city_area = graphene.String(description="District.")
    postal_code = graphene.String(description="Postal code.")
    country = CountryCodeEnum(description="Country.")
    country_area = graphene.String(description="State or province.")
    phone = graphene.String(description="Phone number.")


@key(fields="id")
class Address(CountableDjangoObjectType):
    country = graphene.Field(
        CountryDisplay, required=True, description="Shop's default country."
    )
    is_default_shipping_address = graphene.Boolean(
        required=False, description="Address is user's default shipping address."
    )
    is_default_billing_address = graphene.Boolean(
        required=False, description="Address is user's default billing address."
    )

    class Meta:
        description = "Represents user address data."
        interfaces = [relay.Node]
        model = models.Address
        only_fields = [
            "city",
            "city_area",
            "company_name",
            "country",
            "country_area",
            "first_name",
            "id",
            "last_name",
            "phone",
            "postal_code",
            "street_address_1",
            "street_address_2",
        ]

    @staticmethod
    def resolve_country(root: models.Address, _info):
        return CountryDisplay(code=root.country.code, country=root.country.name)

    @staticmethod
    def resolve_is_default_shipping_address(root: models.Address, _info):
        """Look if the address is the default shipping address of the user.

        This field is added through annotation when using the
        `resolve_addresses` resolver. It's invalid for
        `resolve_default_shipping_address` and
        `resolve_default_billing_address`
        """
        if not hasattr(root, "user_default_shipping_address_pk"):
            return None

        user_default_shipping_address_pk = getattr(
            root, "user_default_shipping_address_pk"
        )
        if user_default_shipping_address_pk == root.pk:
            return True
        return False

    @staticmethod
    def resolve_is_default_billing_address(root: models.Address, _info):
        """Look if the address is the default billing address of the user.

        This field is added through annotation when using the
        `resolve_addresses` resolver. It's invalid for
        `resolve_default_shipping_address` and
        `resolve_default_billing_address`
        """
        if not hasattr(root, "user_default_billing_address_pk"):
            return None

        user_default_billing_address_pk = getattr(
            root, "user_default_billing_address_pk"
        )
        if user_default_billing_address_pk == root.pk:
            return True
        return False

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)


class CustomerEvent(CountableDjangoObjectType):
    date = graphene.types.datetime.DateTime(
        description="Date when event happened at in ISO 8601 format."
    )
    type = CustomerEventsEnum(description="Customer event type.")
    user = graphene.Field(lambda: User, description="User who performed the action.")
    message = graphene.String(description="Content of the event.")
    count = graphene.Int(description="Number of objects concerned by the event.")
    order = graphene.Field(
        "saleor.graphql.order.types.Order", description="The concerned order."
    )
    order_line = graphene.Field(
        "saleor.graphql.order.types.OrderLine", description="The concerned order line."
    )

    class Meta:
        description = "History log of the customer."
        model = models.CustomerEvent
        interfaces = [relay.Node]
        only_fields = ["id"]

    @staticmethod
    def resolve_user(root: models.CustomerEvent, info):
        user = info.context.user
        if (
                user == root.user
                or user.has_perm(AccountPermissions.MANAGE_USERS)
                or user.has_perm(AccountPermissions.MANAGE_STAFF)
        ):
            return root.user
        raise PermissionDenied()

    @staticmethod
    def resolve_message(root: models.CustomerEvent, _info):
        return root.parameters.get("message", None)

    @staticmethod
    def resolve_count(root: models.CustomerEvent, _info):
        return root.parameters.get("count", None)

    @staticmethod
    def resolve_order_line(root: models.CustomerEvent, info):
        if "order_line_pk" in root.parameters:
            try:
                qs = order_models.OrderLine.objects
                order_line_pk = root.parameters["order_line_pk"]
                return qs.filter(pk=order_line_pk).first()
            except order_models.OrderLine.DoesNotExist:
                pass
        return None


class Document(CountableDjangoObjectType):
    content_file = graphene.String(description="Document file path.")

    class Meta:
        description = "Represents documents."
        model = models.Document
        interfaces = [relay.Node]

    @staticmethod
    def resolve_content_file(root: models.Document, info):
        return info.context.build_absolute_uri(root.content_file.url)


class UserPermission(Permission):
    source_permission_groups = graphene.List(
        graphene.NonNull("saleor.graphql.account.types.Group"),
        description="List of user permission groups which contains this permission.",
        user_id=graphene.Argument(
            graphene.ID,
            description="ID of user whose groups should be returned.",
            required=True,
        ),
        required=False,
    )

    def resolve_source_permission_groups(root: Permission, _info, user_id, **_kwargs):
        user_id = from_global_id_strict_type(user_id, only_type="User", field="pk")
        groups = auth_models.Group.objects.filter(
            user__pk=user_id, permissions__name=root.name
        )
        return groups


class Region(CountableDjangoObjectType):
    class Meta:
        interfaces = [relay.Node]
        description = "Represent a region"
        model = models.Region


class UserStoreInfo(CountableDjangoObjectType):
    store_name = graphene.String(description='Store name')
    store_phone = graphene.String(description='Store phone')
    store_address = graphene.String(description='Store address')
    coordinates = GenericScalar()

    class Meta:
        model = models.User
        description = "Store details"
        only_fields = ['phone', 'coordinates', 'store_address', 'store_name', 'store_phone']
        interfaces = [relay.Node]

    @staticmethod
    def resolve_store_name(root: models.User, info, **_kwargs):
        return root.metadata.get('store_name', None)

    @staticmethod
    def resolve_store_phone(root: models.User, info, **_kwargs):
        address = root.default_billing_address
        if address:
            return address.phone
        return None

    @staticmethod
    def resolve_store_address(root: models.User, info, **_kwargs):
        store_address = None
        address = root.default_billing_address
        if address:
            store_address = address.street_address_1
            if store_address and address.postal_code:
                store_address = f'{store_address}, {address.postal_code}'

        return store_address

    @staticmethod
    def resolve_coordinates(root: models.User, _info, **_kwargs):
        location = root.metadata.get('location', None)
        if location:
            location = json.loads(location)
        return location


class Parent(CountableDjangoObjectType):

    class Meta:
        interfaces = [relay.Node]
        description = "Represents a parent (user)"
        model = get_user_model()
        only_fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "id",
            "phone"
        ]


# class Parent(graphene.ObjectType):
#     first_name = graphene.String()
#     last_name = graphene.String()
#     email = graphene.String()
#     phone = graphene.String()
#
#     class Meta:
#         description = "Represents immediate parent"
#         interfaces = [relay.Node]


@key("id")
@key("email")
class User(UserStoreInfo):
    addresses = graphene.List(Address, description="List of all user's addresses.")
    checkout = graphene.Field(
        Checkout, description="Returns the last open checkout of this user."
    )
    gift_cards = PrefetchingConnectionField(
        "saleor.graphql.giftcard.types.GiftCard",
        description="List of the user gift cards.",
    )
    note = graphene.String(description="A note about the customer.")
    orders = PrefetchingConnectionField(
        "saleor.graphql.order.types.Order", description="List of user's orders."
    )
    # deprecated, to remove in #5389
    permissions = graphene.List(
        Permission,
        description="List of user's permissions.",
        deprecation_reason=(
            "Will be removed in Saleor 2.11." "Use the `userPermissions` instead."
        ),
    )
    user_permissions = graphene.List(
        UserPermission, description="List of user's permissions."
    )
    permission_groups = graphene.List(
        "saleor.graphql.account.types.Group",
        description="List of user's permission groups.",
    )
    editable_groups = graphene.List(
        "saleor.graphql.account.types.Group",
        description="List of user's permission groups which user can manage.",
    )
    avatar = graphene.Field(Image, size=graphene.Int(description="Size of the avatar."))
    events = graphene.List(
        CustomerEvent, description="List of events associated with the user."
    )
    stored_payment_sources = graphene.List(
        "saleor.graphql.payment.types.PaymentSource",
        description="List of stored payment sources.",
    )
    documents = graphene.List(Document, description="List of documents user provided.")
    regions = graphene.List(Region, description="User region")
    nid_front = graphene.Field(Document, description="Nid front of user")
    nid_back = graphene.Field(Document, description="Nid back of user")
    nid = graphene.String(description='User NID')
    agent_banking_number = graphene.String(description="Agent banking number information")
    agent_banking = graphene.Boolean(description="Agent banking information")
    bdtickets = graphene.Boolean(description="Bdtickets information")
    robicash = graphene.Boolean(description="Robicash information")
    insurance = graphene.Boolean(description="Insurance information")
    collection_point = graphene.Boolean(description="Collection point information")
    device_accessories = graphene.Boolean(description="Device accessories information")
    iot_smart_product = graphene.Boolean(description="IOT smart product information")
    payment_collection = graphene.Boolean(description="Payment collection information")
    parent = graphene.Field(Parent, description="Immediate parent of a user")

    class Meta:
        description = "Represents user data."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = get_user_model()
        only_fields = [
            "date_joined",
            "default_billing_address",
            "default_shipping_address",
            "email",
            "first_name",
            "last_name",
            "id",
            "oidc_id",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "approval_status",
            "note",
            "phone",
            "metadata",
            "documents",
            "regions"
        ]

    @staticmethod
    def resolve_parent(root: models.User, _info):
        return get_immediate_parent(root)
        # user = get_immediate_parent(root)
        # parent = graphene.Field(Parent)
        # if user is not None:
        #     parent.first_name = user.first_name
        #     parent.last_name = user.last_name
        #     parent.email = user.email
        #     parent.phone = user.phone
        #     return parent
        # return user

    @staticmethod
    def resolve_nid_front(root: models.User, _info, **_kwargs):
        return root.documents.filter(file_tag='nid_front').first()

    @staticmethod
    def resolve_nid_back(root: models.User, _info, **_kwargs):
        return root.documents.filter(file_tag='nid_back').first()

    @staticmethod
    def resolve_addresses(root: models.User, _info, **_kwargs):
        return root.addresses.annotate_default(root).all()

    @staticmethod
    def resolve_checkout(root: models.User, _info, **_kwargs):
        return get_user_checkout(root)[0]

    @staticmethod
    def resolve_gift_cards(root: models.User, info, **_kwargs):
        return root.gift_cards.all()

    @staticmethod
    def resolve_permissions(root: models.User, _info, **_kwargs):
        # deprecated, to remove in #5389
        from .resolvers import resolve_permissions

        return resolve_permissions(root)

    @staticmethod
    def resolve_user_permissions(root: models.User, _info, **_kwargs):
        from .resolvers import resolve_permissions

        return resolve_permissions(root)

    @staticmethod
    def resolve_permission_groups(root: models.User, _info, **_kwargs):
        return root.groups.all()

    @staticmethod
    def resolve_editable_groups(root: models.User, _info, **_kwargs):
        return get_groups_which_user_can_manage(root)

    @staticmethod
    @one_of_permissions_required(
        [AccountPermissions.MANAGE_USERS, AccountPermissions.MANAGE_STAFF]
    )
    def resolve_note(root: models.User, info):
        return root.note

    @staticmethod
    @one_of_permissions_required(
        [AccountPermissions.MANAGE_USERS, AccountPermissions.MANAGE_STAFF]
    )
    def resolve_events(root: models.User, info):
        return root.events.all()

    @staticmethod
    def resolve_orders(root: models.User, info, **_kwargs):
        viewer = info.context.user
        if viewer.has_perm(OrderPermissions.MANAGE_ORDERS):
            return root.orders.all()
        return root.orders.confirmed()

    @staticmethod
    def resolve_avatar(root: models.User, info, size=None, **_kwargs):
        if root.avatar:
            return Image.get_adjusted(
                image=root.avatar,
                alt=None,
                size=size,
                rendition_key_set="user_avatars",
                info=info,
            )

    @staticmethod
    def resolve_stored_payment_sources(root: models.User, info):
        from .resolvers import resolve_payment_sources

        if root == info.context.user:
            return resolve_payment_sources(root)
        raise PermissionDenied()

    @staticmethod
    def resolve_documents(root: models.User, _info, **_kwargs):
        return root.documents.all()

    @staticmethod
    def resolve_regions(root: models.User, _info, **_kwargs):
        return root.regions.all()

    @staticmethod
    @one_of_permissions_required(
        [AccountPermissions.MANAGE_USERS, AccountPermissions.MANAGE_STAFF]
    )
    def resolve_private_meta(root: models.User, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root: models.User, _info):
        return resolve_meta(root, _info)

    @staticmethod
    def resolve_wishlist(root: models.User, info, **_kwargs):
        return resolve_wishlist_items_from_user(root)

    @staticmethod
    def resolve_nid(root: models.User, info, **_kwargs):
        return root.metadata.get('nid', None)

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        if root.id is not None:
            return graphene.Node.get_node_from_global_id(_info, root.id)
        return get_user_model().objects.get(email=root.email)

    @staticmethod
    def resolve_nid(root: models.User, info, **_kwargs):
        return root.metadata.get('nid', None)

    @staticmethod
    def resolve_agent_banking_number(root: models.User, info, **_kwargs):
        return root.metadata.get('agent_banking_number', None)

    @staticmethod
    def resolve_agent_banking(root: models.User, info, **_kwargs):
        return root.metadata.get('agent_banking', None)

    @staticmethod
    def resolve_bdtickets(root: models.User, info, **_kwargs):
        return root.metadata.get('bdtickets', None)

    @staticmethod
    def resolve_robicash(root: models.User, info, **_kwargs):
        return root.metadata.get('robicash', None)

    @staticmethod
    def resolve_insurance(root: models.User, info, **_kwargs):
        return root.metadata.get('insurance', None)

    @staticmethod
    def resolve_collection_point(root: models.User, info, **_kwargs):
        return root.metadata.get('collection_point', None)

    @staticmethod
    def resolve_device_accessories(root: models.User, info, **_kwargs):
        return root.metadata.get('device_accessories', None)

    @staticmethod
    def resolve_iot_smart_product(root: models.User, info, **_kwargs):
        return root.metadata.get('iot_smart_product', None)

    @staticmethod
    def resolve_payment_collection(root: models.User, info, **_kwargs):
        return root.metadata.get('payment_collection', None)

    @staticmethod
    def resolve_store_name(root: models.User, info, **_kwargs):
        return root.metadata.get('store_name', None)

    @staticmethod
    def resolve_store_address(root: models.User, info, **_kwargs):
        store_address = None

        if root.addresses and len(root.addresses.annotate_default(root)) > 0:
            default_address = root.addresses.annotate_default(root)[0]
            store_address = default_address.street_address_1

            if default_address.postal_code:
                if store_address != "":
                    store_address = f'{store_address}, '
                store_address = store_address + default_address.postal_code

        return store_address


class UserRequest(graphene.ObjectType):
    user = graphene.Field(
        User,
        description="user"
    )
    assigned = graphene.Field(
        User,
        description="assigned"
    )
    status = graphene.String(description="Status")

    class Meta:
        model = models.UserRequest
        description = "Represents an User request"
        filter_fields = ['status']
        interfaces = [relay.Node]

    @staticmethod
    def resolve_user(root: models.User, info):
        return root


class ChoiceValue(graphene.ObjectType):
    raw = graphene.String()
    verbose = graphene.String()


class TupleValue(graphene.ObjectType):
    key = graphene.String()
    label = graphene.String()


class AddressValidationData(graphene.ObjectType):
    country_code = graphene.String()
    country_name = graphene.String()
    address_format = graphene.String()
    address_latin_format = graphene.String()
    allowed_fields = graphene.List(graphene.String)
    required_fields = graphene.List(graphene.String)
    upper_fields = graphene.List(graphene.String)
    country_area_type = graphene.String()
    country_area_choices = graphene.List(ChoiceValue)
    city_type = graphene.String()
    city_choices = graphene.List(ChoiceValue)
    city_area_type = graphene.String()
    city_area_choices = graphene.List(ChoiceValue)
    postal_code_type = graphene.String()
    postal_code_matchers = graphene.List(graphene.String)
    postal_code_examples = graphene.List(graphene.String)
    postal_code_prefix = graphene.String()


class StaffNotificationRecipient(CountableDjangoObjectType):
    user = graphene.Field(
        User,
        description="Returns a user subscribed to email notifications.",
        required=False,
    )
    email = graphene.String(
        description=(
            "Returns email address of a user subscribed to email notifications."
        ),
        required=False,
    )
    active = graphene.Boolean(description="Determines if a notification active.")

    class Meta:
        description = (
            "Represents a recipient of email notifications send by Saleor, "
            "such as notifications about new orders. Notifications can be "
            "assigned to staff users or arbitrary email addresses."
        )
        interfaces = [relay.Node]
        model = models.StaffNotificationRecipient
        only_fields = ["user", "active"]

    @staticmethod
    def resolve_user(root: models.StaffNotificationRecipient, info):
        user = info.context.user
        if user == root.user or user.has_perm(AccountPermissions.VIEW_STAFF):
            return root.user
        raise PermissionDenied()

    @staticmethod
    def resolve_email(root: models.StaffNotificationRecipient, _info):
        return root.get_email()


class Group(CountableDjangoObjectType):
    users = graphene.List(User, description="List of group users")
    permissions = graphene.List(Permission, description="List of group permissions")
    user_can_manage = graphene.Boolean(
        required=True,
        description=(
            "True, if the currently authenticated user has rights to manage a group."
        ),
    )
    user_count = graphene.Int(description="Number of users per each group")
    has_txn = graphene.Boolean(description="Group has transactions")

    class Meta:
        description = "Represents permission group data."
        interfaces = [relay.Node]
        model = auth_models.Group
        only_fields = ["name", "permissions", "id"]

    @staticmethod
    @permission_required(AccountPermissions.VIEW_STAFF)
    def resolve_users(root: auth_models.Group, _info):
        return root.user_set.all()

    @staticmethod
    def resolve_permissions(root: auth_models.Group, _info):
        permissions = root.permissions.prefetch_related("content_type").order_by(
            "codename"
        )
        return format_permissions_for_display(permissions)

    @staticmethod
    def resolve_user_can_manage(root: auth_models.Group, info):
        user = info.context.user
        return can_user_manage_group(user, root)

    def resolve_user_count(self, info):
        user_count = models.User.objects.filter(groups__name=self.name).count()
        return user_count

    @staticmethod
    def resolve_has_txn(root: auth_models.Group, _info, **_kwargs):
        try:
            entry = models.GroupHierarchy.objects.get(parent=root)
            has_txn = entry.has_txn
        except models.GroupHierarchy.DoesNotExist:
            has_txn = False
        return has_txn


class Thana(CountableDjangoObjectType):
    class Meta:
        interfaces = [relay.Node]
        description = "Represents a Thana"
        model = models.Thana


class District(CountableDjangoObjectType):
    class Meta:
        interfaces = [relay.Node]
        description = "Represents a district with the thanas in it"
        model = models.District

    thanas = graphene.List(Thana)

    def resolve_thanas(self, info):
        return models.Thana.objects.filter(district_id=self.id)


class MFSAccountType(CountableDjangoObjectType):
    class Meta:
        interfaces = [relay.Node]
        model = models.MFSAccountType


class AgentRequest(CountableDjangoObjectType):
    class Meta:
        model = models.UserRequest
        description = "Represents an agent request"
        filter_fields = ['status']
        interfaces = [relay.Node]


class UserCorrectionRequest(CountableDjangoObjectType):
    class Meta:
        interfaces = [relay.Node, ObjectWithMetadata]
        description = "Represents an user correction request"
        model = models.UserCorrectionRequest
        filter_fields = ['status']


class UserCorrection(CountableDjangoObjectType):
    addresses = graphene.List(Address, description="List of all user's addresses.")
    avatar = graphene.Field(Image, size=graphene.Int(description="Size of the avatar."))
    documents = graphene.List(Document, description="List of documents user provided.")
    correction_request = graphene.Field(UserCorrectionRequest, description="User correction request id")

    class Meta:
        interfaces = [relay.Node, ObjectWithMetadata]
        description = "Represents an user correction request"
        model = models.UserCorrection

    @staticmethod
    def resolve_addresses(root: models.UserCorrection, _info, **_kwargs):
        return root.addresses.all()

    @staticmethod
    def resolve_avatar(root: models.UserCorrection, info, size=None, **_kwargs):
        if root.avatar:
            return Image.get_adjusted(
                image=root.avatar,
                alt=None,
                size=size,
                rendition_key_set="user_avatars",
                info=info,
            )

    @staticmethod
    def resolve_documents(root: models.UserCorrection, _info, **_kwargs):
        return root.documents.all()

    @staticmethod
    def resolve_correction_request(root: models.UserCorrection, _info, **_kwargs):
        return models.UserCorrectionRequest.objects.get(user_correction_id=root.id)


class GroupMap(CountableDjangoObjectType):

    class Meta:
        description = "Represents group"
        interfaces = [relay.Node]
        model = models.GroupHierarchy


class GroupChildTrxMap(graphene.ObjectType):
    group_name = graphene.String(description="Name of the parent group")
    child_name = graphene.String(description="Name of the child group")
    has_txn = graphene.Boolean(description="If group has transactional hierarchy")


# class AuthGroup(CountableDjangoObjectType):
#     has_txn = graphene.Boolean(description="Group has transactions")
#
#     class Meta:
#         interfaces = [relay.Node]
#         description = "Represents a Group from auth model"
#         model = auth_models.Group
#
#     @staticmethod
#     def resolve_has_txn(root: models.Group, _info, **_kwargs):
#         try:
#             entry = models.GroupHierarchy.objects.get(parent=root)
#             has_txn = entry.has_txn
#         except models.GroupHierarchy.DoesNotExist:
#             has_txn = False
#         return has_txn
