import graphene
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from django.db.models import Q
from graphene.types import InputObjectType

from ....account.models import User
from ....core.permissions import OrderPermissions
from ....core.taxes import zero_taxed_money
from ....order import events, models, OrderStatus, OrderType
from ....order.actions import (
    cancel_order,
    clean_mark_order_as_paid,
    mark_order_as_paid,
    order_captured,
    order_refunded,
    order_shipping_updated,
    order_voided,
    create_fulfillments,
    cancel_fulfillment,
    order_created,
)
from ....order.error_codes import OrderErrorCode
from ....order.utils import get_valid_shipping_methods_for_order, recalculate_order
from ....payment import CustomPaymentChoices, PaymentError, gateway
from ...account.types import AddressInput
from ...core.mutations import BaseMutation, ModelMutation
from ...core.scalars import Decimal, WeightScalar
from ...core.types.common import OrderError
from ...meta.deprecated.mutations import ClearMetaBaseMutation, UpdateMetaBaseMutation
from ...meta.deprecated.types import MetaInput, MetaPath
from ...order.mutations.draft_orders import DraftOrderUpdate
from ...order.types import Order, OrderEvent
from ...shipping.types import ShippingMethod
from ....order.actions import generate_pdf_receipt, generate_pdf_order_cancelled

from ..enums import OrderStatusFilter, OrderTypeEnum
from ...discount.mutations import VoucherInput
from ...meta.mutations import MetadataInput
from ...payment.enums import PaymentChargeStatusEnum
from ...shipping.mutations import ShippingPriceInput
from ....core.utils import get_client_ip
from ....core.utils.promo_code import generate_promo_code
from ....discount.models import Voucher as VoucherModel
from ....payment import ChargeStatus
from ....payment.utils import create_payment
from ....product.models import ProductVariant as ProductVariantModel
from ....product.models import Product as ProductModel
from ....product.models import Category as CategoryModel
from ....product.models import ProductType as ProductTypeModel
from ....warehouse.models import Warehouse as WarehouseModel
from ....warehouse.models import Stock as StockModel
from ....partner.models import Partner as PartnerModel
from ....payment.models import Payment as PaymentModel
from ....shipping.models import ShippingMethod as ShippingMethodModel
from ....shipping.models import ShippingZone as ShippingZoneModel
from ....product.error_codes import ProductErrorCode
from ...account.i18n import I18nMixin

from collections import defaultdict
import uuid
from datetime import datetime
from django.conf import settings

from business_rules import run_all
from ....commission.models import Rule
from ....commission.commission_calculation import OrderVariables, OrderActions
from ....order.sms import send_new_order_placement_sms, update_order_sms
from ....order.achievement_calculations import calculate_attribute_target_progress, calculate_partner_target_progress, \
    add_general_achievement, remove_general_achievement, remove_attribute_achievement, remove_partner_achievement


def clean_order_update_shipping(order, method):
    if not order.shipping_address:
        raise ValidationError(
            {
                "order": ValidationError(
                    "Cannot choose a shipping method for an order without "
                    "the shipping address.",
                    code=OrderErrorCode.ORDER_NO_SHIPPING_ADDRESS,
                )
            }
        )

    valid_methods = get_valid_shipping_methods_for_order(order)
    if valid_methods is None or method.pk not in valid_methods.values_list(
            "id", flat=True
    ):
        raise ValidationError(
            {
                "shipping_method": ValidationError(
                    "Shipping method cannot be used with this order.",
                    code=OrderErrorCode.SHIPPING_METHOD_NOT_APPLICABLE,
                )
            }
        )


def clean_order_cancel(order):
    if order and not order.can_cancel():
        raise ValidationError(
            {
                "order": ValidationError(
                    "This order can't be canceled.",
                    code=OrderErrorCode.CANNOT_CANCEL_ORDER,
                )
            }
        )


def clean_payment(payment):
    if not payment:
        raise ValidationError(
            {
                "payment": ValidationError(
                    "There's no payment associated with the order.",
                    code=OrderErrorCode.PAYMENT_MISSING,
                )
            }
        )


def clean_order_capture(payment):
    clean_payment(payment)
    if not payment.is_active:
        raise ValidationError(
            {
                "payment": ValidationError(
                    "Only pre-authorized payments can be captured",
                    code=OrderErrorCode.CAPTURE_INACTIVE_PAYMENT,
                )
            }
        )


def clean_void_payment(payment):
    """Check for payment errors."""
    clean_payment(payment)
    if not payment.is_active:
        raise ValidationError(
            {
                "payment": ValidationError(
                    "Only pre-authorized payments can be voided",
                    code=OrderErrorCode.VOID_INACTIVE_PAYMENT,
                )
            }
        )


def clean_refund_payment(payment):
    clean_payment(payment)
    if payment.gateway == CustomPaymentChoices.MANUAL:
        raise ValidationError(
            {
                "payment": ValidationError(
                    "Manual payments can not be refunded.",
                    code=OrderErrorCode.CANNOT_REFUND,
                )
            }
        )


def try_payment_action(order, user, payment, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except (PaymentError, ValueError) as e:
        message = str(e)
        events.payment_failed_event(
            order=order, user=user, message=message, payment=payment
        )
        raise ValidationError(
            {"payment": ValidationError(message, code=OrderErrorCode.PAYMENT_ERROR)}
        )
    return True


class OrderUpdateInput(graphene.InputObjectType):
    billing_address = AddressInput(description="Billing address of the customer.")
    user_email = graphene.String(description="Email address of the customer.")
    shipping_address = AddressInput(description="Shipping address of the customer.")


class OrderUpdate(DraftOrderUpdate):
    class Arguments:
        id = graphene.ID(required=True, description="ID of an order to update.")
        input = OrderUpdateInput(
            required=True, description="Fields required to update an order."
        )

    class Meta:
        description = "Updates an order."
        model = models.Order
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"
        exclude = ['order_receipt']

    @classmethod
    def clean_input(cls, info, instance, data):
        draft_order_cleaned_input = super().clean_input(info, instance, data)

        # We must to filter out field added by DraftOrderUpdate
        editable_fields = ["billing_address", "shipping_address", "user_email"]
        cleaned_input = {}
        for key in draft_order_cleaned_input:
            if key in editable_fields:
                cleaned_input[key] = draft_order_cleaned_input[key]
        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        super().save(info, instance, cleaned_input)
        if instance.user_email:
            user = User.objects.filter(email=instance.user_email).first()
            instance.user = user
        instance.save()
        order_lines = models.OrderLine.objects.filter(order=instance)
        generate_pdf_receipt(instance, order_lines)


class OrderUpdateShippingInput(graphene.InputObjectType):
    shipping_method = graphene.ID(
        description="ID of the selected shipping method.", name="shippingMethod"
    )


class OrderUpdateShipping(BaseMutation):
    order = graphene.Field(Order, description="Order with updated shipping method.")

    class Arguments:
        id = graphene.ID(
            required=True,
            name="order",
            description="ID of the order to update a shipping method.",
        )
        input = OrderUpdateShippingInput(
            description="Fields required to change shipping method of the order."
        )

    class Meta:
        description = "Updates a shipping method of the order."
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order = cls.get_node_or_error(info, data.get("id"), only_type=Order)
        data = data.get("input")

        if not data["shipping_method"]:
            if not order.is_draft() and order.is_shipping_required():
                raise ValidationError(
                    {
                        "shipping_method": ValidationError(
                            "Shipping method is required for this order.",
                            code=OrderErrorCode.SHIPPING_METHOD_REQUIRED,
                        )
                    }
                )

            order.shipping_method = None
            order.shipping_price = zero_taxed_money()
            order.shipping_method_name = None
            order.save(
                update_fields=[
                    "currency",
                    "shipping_method",
                    "shipping_price_net_amount",
                    "shipping_price_gross_amount",
                    "shipping_method_name",
                ]
            )
            return OrderUpdateShipping(order=order)

        method = cls.get_node_or_error(
            info,
            data["shipping_method"],
            field="shipping_method",
            only_type=ShippingMethod,
        )

        clean_order_update_shipping(order, method)

        order.shipping_method = method
        order.shipping_price = info.context.plugins.calculate_order_shipping(order)
        order.shipping_method_name = method.name
        order.save(
            update_fields=[
                "currency",
                "shipping_method",
                "shipping_method_name",
                "shipping_price_net_amount",
                "shipping_price_gross_amount",
            ]
        )
        # Post-process the results
        order_shipping_updated(order)

        order_lines = models.OrderLine.objects.filter(order__id=order.id)
        generate_pdf_receipt(order, order_lines)

        return OrderUpdateShipping(order=order)


class OrderAddNoteInput(graphene.InputObjectType):
    message = graphene.String(
        description="Note message.", name="message", required=True
    )


class OrderAddNote(BaseMutation):
    order = graphene.Field(Order, description="Order with the note added.")
    event = graphene.Field(OrderEvent, description="Order note created.")

    class Arguments:
        id = graphene.ID(
            required=True,
            description="ID of the order to add a note for.",
            name="order",
        )
        input = OrderAddNoteInput(
            required=True, description="Fields required to create a note for the order."
        )

    class Meta:
        description = "Adds note to the order."
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"

    @classmethod
    def clean_input(cls, _info, _instance, data):
        message = data["input"]["message"].strip()
        if not message:
            raise ValidationError(
                {
                    "message": ValidationError(
                        "Message can't be empty.", code=OrderErrorCode.REQUIRED,
                    )
                }
            )
        data["input"]["message"] = message
        return data

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order = cls.get_node_or_error(info, data.get("id"), only_type=Order)
        cleaned_input = cls.clean_input(info, order, data)
        event = events.order_note_added_event(
            order=order,
            user=info.context.user,
            message=cleaned_input["input"]["message"],
        )

        order_lines = models.OrderLine.objects.filter(order__id=order.id)
        generate_pdf_receipt(order, order_lines)

        return OrderAddNote(order=order, event=event)


class OrderCancel(BaseMutation):
    order = graphene.Field(Order, description="Canceled order.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of the order to cancel.")

    class Meta:
        description = "Cancel an order."
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order = cls.get_node_or_error(info, data.get("id"), only_type=Order)
        clean_order_cancel(order)
        cancel_order(order=order, user=info.context.user)
        remove_general_achievement.delay(order.pk)
        orderlines = models.OrderLine.objects.filter(order__id=order.id)
        generate_pdf_order_cancelled(order, orderlines, base_url=getattr(settings, "API_URL"))
        return OrderCancel(order=order)


class OrderMarkAsPaid(BaseMutation):
    order = graphene.Field(Order, description="Order marked as paid.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of the order to mark paid.")

    class Meta:
        description = "Mark order as manually paid."
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"

    @classmethod
    def clean_billing_address(cls, instance):
        if not instance.billing_address:
            raise ValidationError(
                "Order billing address is required to mark order as paid.",
                code=OrderErrorCode.BILLING_ADDRESS_NOT_SET,
            )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order = cls.get_node_or_error(info, data.get("id"), only_type=Order)

        cls.clean_billing_address(order)
        try_payment_action(
            order, info.context.user, None, clean_mark_order_as_paid, order
        )

        mark_order_as_paid(order, info.context.user)
        order_lines = models.OrderLine.objects.filter(order__id=order.id)
        generate_pdf_receipt(order, order_lines)

        return OrderMarkAsPaid(order=order)


class OrderCapture(BaseMutation):
    order = graphene.Field(Order, description="Captured order.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of the order to capture.")
        amount = Decimal(required=True, description="Amount of money to capture.")

    class Meta:
        description = "Capture an order."
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"

    @classmethod
    def perform_mutation(cls, _root, info, amount, **data):
        if amount <= 0:
            raise ValidationError(
                {
                    "amount": ValidationError(
                        "Amount should be a positive number.",
                        code=OrderErrorCode.ZERO_QUANTITY,
                    )
                }
            )

        order = cls.get_node_or_error(info, data.get("id"), only_type=Order)
        payment = order.get_last_payment()
        clean_order_capture(payment)

        try_payment_action(
            order, info.context.user, payment, gateway.capture, payment, amount
        )

        order_captured(order, info.context.user, amount, payment)
        return OrderCapture(order=order)


class OrderVoid(BaseMutation):
    order = graphene.Field(Order, description="A voided order.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of the order to void.")

    class Meta:
        description = "Void an order."
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        order = cls.get_node_or_error(info, data.get("id"), only_type=Order)
        payment = order.get_last_payment()
        clean_void_payment(payment)

        try_payment_action(order, info.context.user, payment, gateway.void, payment)
        order_voided(order, info.context.user, payment)
        return OrderVoid(order=order)


class OrderRefund(BaseMutation):
    order = graphene.Field(Order, description="A refunded order.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of the order to refund.")
        amount = Decimal(required=True, description="Amount of money to refund.")

    class Meta:
        description = "Refund an order."
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"

    @classmethod
    def perform_mutation(cls, _root, info, amount, **data):
        if amount <= 0:
            raise ValidationError(
                {
                    "amount": ValidationError(
                        "Amount should be a positive number.",
                        code=OrderErrorCode.ZERO_QUANTITY,
                    )
                }
            )

        order = cls.get_node_or_error(info, data.get("id"), only_type=Order)
        payment = order.get_last_payment()
        clean_refund_payment(payment)

        try_payment_action(
            order, info.context.user, payment, gateway.refund, payment, amount
        )

        order_refunded(order, info.context.user, amount, payment)
        return OrderRefund(order=order)


class OrderUpdateMeta(UpdateMetaBaseMutation):
    class Meta:
        description = "Updates meta for order."
        model = models.Order
        public = True

    class Arguments:
        token = graphene.UUID(
            description="Token of an object to update.", required=True
        )
        input = MetaInput(
            description="Fields required to update new or stored metadata item.",
            required=True,
        )

    @classmethod
    def get_instance(cls, info, **data):
        token = data["token"]
        return models.Order.objects.get(token=token)


class OrderUpdatePrivateMeta(UpdateMetaBaseMutation):
    class Meta:
        description = "Updates private meta for order."
        model = models.Order
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        public = False


class OrderClearMeta(ClearMetaBaseMutation):
    class Meta:
        description = "Clears stored metadata value."
        model = models.Order
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        public = True

    class Arguments:
        token = graphene.UUID(description="Token of an object to clear.", required=True)
        input = MetaPath(
            description="Fields required to update new or stored metadata item.",
            required=True,
        )

    @classmethod
    def get_instance(cls, info, **data):
        token = data["token"]
        return models.Order.objects.get(token=token)


class OrderClearPrivateMeta(ClearMetaBaseMutation):
    class Meta:
        description = "Clears stored private metadata value."
        model = models.Order
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        public = False


class OtherChargeInput(InputObjectType):
    name = graphene.String(description="Charge name, example: \"EMI charge\"", required=True)
    amount = Decimal(description="Charge amount.", required=True)


class OrderProductLineInput(InputObjectType):
    name = graphene.String(description="Product name.", required=True)
    sku = graphene.String(
        description=(
            "Stock keeping unit of a product. Note: this field is only used if "
            "a product doesn't use variants."
        ),
        required=True
    )
    base_price = Decimal(description="Product price.", required=True)
    quantity = graphene.Int(description="Quantity of product.", required=True)
    description = graphene.String(description="Product description (HTML/text).", required=False)
    weight = WeightScalar(description="Weight of the Product.", required=False)
    category = graphene.String(description="Name of the product's category.", required=True)
    meta_data = graphene.List(
        MetadataInput,
        description=(
            "Holds information of the product, this field is optional, example:\n"
            "[\n"
            "{\n\"key\": \"RAM\",\n"
            "\"value\": \"4 GB\"\n},\n"
            "{\n\"key\": \"Brand\",\n"
            "\"value\": \"Samsung\"\n},\n"
            "{\n\"key\": \"Color\",\n"
            "\"value\": \"Grey\"\n}\n"
            "]"

        ),
        required=False
    )


class CreateNewOrderInput(InputObjectType):
    user_phone = graphene.String(
        description="Phone number of the user. This field is required if userEmail field is not set"
    )
    user_email = graphene.String(description="Email of the user. This field is required if userPhone field is not set.")
    partner_order_id = graphene.String(
        description=(
            "Actual order ID generated by the partner's system for the order.\n"
            "This field is required.\nIt is used to track the original order in the partner's system."
        ),
        required=True
    )
    billing_address = AddressInput(
        description=(
            "Billing address of the user. "
            "This field is optional, "
            "if not provided the default billing address of the user will be used, "
            "example: \n"
            "{\n\"firstName\": \"Rakib\",\n"
            "\"lastName\": \"Hasan\"\n"
            "\"city\": \"Dhaka\",\n"
            "\"cityArea\": \"Mirpur\",\n"
            "\"streetAddress1\": \"240/A, minhaj road\",\n"
            "\"postalCode\": \"1216\",\n"
            "\"phone\": \"018********\"\n}\n"
            "All the fields in the example are not required."
        )
    )
    shipping_address = AddressInput(
        description=(
            "Shipping address of the user."
            "This field is optional, "
            "if not provided the default shipping address of the user will be used, "
            "example: \n"
            "{\n\"firstName\": \"Rakib\",\n"
            "\"lastName\": \"Hasan\"\n"
            "\"city\": \"Dhaka\",\n"
            "\"cityArea\": \"Mirpur\",\n"
            "\"streetAddress1\": \"240/A, minhaj road\",\n"
            "\"postalCode\": \"1216\",\n"
            "\"phone\": \"018********\"\n}\n"
            "All the fields in the example are not required."
        )
    )
    customer_note = graphene.String(
        description="A note from a user. Visible to user in the order summary."
    )

    products = graphene.List(
        OrderProductLineInput,
        description=(
            "List of products for the order. This field is required."
        ),
        required=True
    )
    payment_status = PaymentChargeStatusEnum(
        description=(
            "Status of the order's payment. "
            "This field is optional, if provided it only takes\nFULLY_CHARGED or NOT_CHARGED as input"
        ),
        required=False
    )
    shipping = graphene.Field(
        ShippingPriceInput,
        description=(
            "Shipping method for the order. "
            "This field is optional. "
            "If not provided, a default shipping service with 0 shipping charge is added\n"
            "Here is a sample shipping input\n "
            "{\n\"name\": \"xyz courier service\",\n"
            "\"price\": \"120\"\n}"
        ),
        required=False
    )
    discount = graphene.Field(
        VoucherInput,
        description=(
            "Discount option used for the order. "
            "This field is optional. "
            "Here is a sample discount input\n"
            "{\n\"name\": \"new-year\",\n"
            "\"code\": \"2021\",\n"
            "\"discountValue\": \"20\",\n"
            "\"discountValueType\": \"FIXED\"\n}\n"
            "discountValueType can be FIXED or PERCENTAGE."
        ),
        required=False
    )
    other_charge = graphene.Field(
        OtherChargeInput,
        description=(
            "Other charging option. "
            "This field is optional. "
            "Here is a sample OtherCharge input\n"
            "{\n\"name\": \"EMI-charge\",\n"
            "\"amount\": \"200.00\",\n}\n"
        ),
        required=False
    )
    type = OrderTypeEnum(
        description=(
            "Type of the order. "
            "This field is optional, if provided it only takes\nBUY or SELL as input."
        ),
        required=False
    )
    order_status = OrderStatusFilter(
        description=(
            "Status of the order. This field is optional.\n"
            "It only accepts \nUNFULFILLED or FULFILLED as input"

        ),
        required=False
    )


class CreateNewOrder(ModelMutation, I18nMixin):
    class Arguments:
        input = CreateNewOrderInput(
            required=True, description="Fields required to create an order from partner."
        )

    class Meta:
        description = "Creates a new draft order from partner."
        model = models.Order
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"
        exclude = ['order_receipt']

    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = {}
        cleaned_lines = []

        user_email = data.pop("user_email", None)
        user_phone = data.pop("user_phone", None)

        user = User.objects.filter(Q(email=user_email) | Q(phone=user_phone)).first()
        if user is None:
            raise ValidationError(
                {
                    "user": ValidationError(
                        "User is invalid.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )
        cleaned_input["user"] = user

        if info.context.app:
            partner = PartnerModel.objects.filter(partner_app=info.context.app).first()
        if not partner:
            raise ValidationError(
                {
                    "partner": ValidationError(
                        "Partner is not found",
                        code=OrderErrorCode.NOT_FOUND,
                    )
                }
            )
        cleaned_input["partner"] = partner

        partner_order_id = data.pop("partner_order_id", None)
        if partner_order_id is None or len(partner_order_id) == 0:
            raise ValidationError(
                {
                    "partnerOrderId": ValidationError(
                        "Partner Order ID is invalid.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )
        cleaned_input["partner_order_id"] = partner_order_id

        shipping_address = data.pop("shipping_address", None)
        billing_address = data.pop("billing_address", None)

        if shipping_address is None:
            cleaned_input["shipping_address"] = user.default_shipping_address
            cleaned_input["new_shipping_address"] = False

        if billing_address is None:
            cleaned_input["billing_address"] = user.default_billing_address
            cleaned_input["new_billing_address"] = False

        if shipping_address:
            shipping_address = cls.validate_address(
                shipping_address, instance=instance.shipping_address, info=info
            )
            cleaned_input["shipping_address"] = shipping_address
            cleaned_input["new_shipping_address"] = True

        if billing_address:
            billing_address = cls.validate_address(
                billing_address, instance=instance.billing_address, info=info
            )
            cleaned_input["billing_address"] = billing_address
            cleaned_input["new_billing_address"] = True

        if cleaned_input["shipping_address"] is None:
            raise ValidationError(
                {
                    "shipping_address": ValidationError(
                        "Agent has no default shipping address, shipping address is required.",
                        code=OrderErrorCode.ORDER_NO_SHIPPING_ADDRESS,
                    )
                }
            )

        if cleaned_input["billing_address"] is None:
            raise ValidationError(
                {
                    "billing_address": ValidationError(
                        "Agent has no default billing address, billing address is required.",
                        code=OrderErrorCode.BILLING_ADDRESS_NOT_SET,
                    )
                }
            )

        customer_note = data.pop("customer_note", None)
        if customer_note:
            cleaned_input["customer_note"] = customer_note

        lines = data.pop("products", None)
        if lines:
            for product in lines:
                cleaned_product = {}
                name = product.get("name", None)
                sku = product.get("sku", None)
                base_price = product.get("base_price", None)
                quantity = product.get("quantity", None)
                description = product.get("description", None)
                weight = product.get("weight", None)
                category = product.get("category", None)
                meta_data = product.get("meta_data", None)

                if name is None or len(name) == 0:
                    raise ValidationError(
                        {
                            "name": ValidationError(
                                "Product name can not be empty.",
                                code=ProductErrorCode.INVALID,
                            )
                        }
                    )
                cleaned_product["name"] = name

                if sku is None or len(sku) == 0:
                    raise ValidationError(
                        {
                            "sku": ValidationError(
                                "Product sku can not be empty.",
                                code=ProductErrorCode.INVALID,
                            )
                        }
                    )
                cleaned_product["sku"] = sku

                if base_price is None or base_price < 0:
                    raise ValidationError(
                        {
                            "basePrice": ValidationError(
                                "Product base price can not be negative.",
                                code=ProductErrorCode.INVALID,
                            )
                        }
                    )
                cleaned_product["base_price"] = base_price

                if quantity is None or quantity <= 0:
                    raise ValidationError(
                        {
                            "quantity": ValidationError(
                                "Product quantity can not be negative or zero.",
                                code=ProductErrorCode.INVALID,
                            )
                        }
                    )
                cleaned_product["quantity"] = quantity

                if description is None:
                    cleaned_product["description"] = ""
                else:
                    cleaned_product["description"] = description

                cleaned_product["weight"] = 0
                if weight is not None:
                    if weight.value < 0:
                        raise ValidationError(
                            {
                                "weight": ValidationError(
                                    "Product can't have negative weight.",
                                    code=ProductErrorCode.INVALID,
                                )
                            }
                        )
                    cleaned_product["weight"] = weight.value

                if category is None:
                    raise ValidationError(
                        {
                            "category": ValidationError(
                                "Product category is invalid.",
                                code=ProductErrorCode.INVALID,
                            )
                        }
                    )
                cleaned_product["category"] = category

                if meta_data is not None:
                    for meta_data_item in meta_data:
                        if len(meta_data_item["key"]) == 0 or len(meta_data_item["value"]) == 0:
                            raise ValidationError(
                                {
                                    "metaData": ValidationError(
                                        "Product meta data key and value can not be empty if provided.",
                                        code=ProductErrorCode.INVALID,
                                    )
                                }
                            )
                    cleaned_product["meta_data"] = meta_data
                else:
                    cleaned_product["meta_data"] = {}

                cleaned_lines.append(cleaned_product)

            cleaned_input["lines"] = cleaned_lines
        else:
            raise ValidationError(
                {
                    "metaData": ValidationError(
                        "Must provide product information to create order.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        warehouse = WarehouseModel.objects.filter(name="Bangladesh").first()
        cleaned_input["warehouse"] = warehouse

        shipping_zone = ShippingZoneModel.objects.filter(name="Bangladesh").first()
        cleaned_input["shipping_zone"] = shipping_zone

        shipping = data.pop("shipping", None)
        if shipping is not None and \
                (shipping.get("name") is None or shipping.get("price") is None or shipping.get("price") < 0):
            raise ValidationError(
                {
                    "shipping": ValidationError(
                        "If Shipping is provided, it requires a name and a price and price can not be negative.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        if shipping is None:
            existing_shipping_method = ShippingMethodModel.objects.filter(
                Q(name__iexact="Default Shipping") & Q(price_amount=0)
            ).first()
        else:
            existing_shipping_method = ShippingMethodModel.objects.filter(
                Q(name__iexact=shipping["name"]) & Q(price_amount=shipping["price"])
            ).first()

        cleaned_input["existing_shipping_method"] = existing_shipping_method
        cleaned_input["shipping"] = shipping

        payment_status = data.pop("payment_status", ChargeStatus.NOT_CHARGED)

        if payment_status not in \
                [
                    ChargeStatus.FULLY_CHARGED,
                    ChargeStatus.NOT_CHARGED
                ]:
            raise ValidationError(
                {
                    "payment_status": ValidationError(
                        "Payment status can only be FULLY_CHARGED or NOT_CHARGED.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        cleaned_input['payment_status'] = payment_status

        discount = data.pop("discount", None)
        if discount is not None and (
                discount.get("discount_value_type") is None
                or discount.get("discount_value") is None
                or discount.get("discount_value") < 0
        ):
            raise ValidationError(
                {
                    "discount": ValidationError(
                        "Discount value and type must be provided and value can not be negative.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )
        cleaned_input["discount"] = discount

        other_charge = data.pop("other_charge", None)
        if other_charge:
            name = other_charge.get("name", None)
            amount = other_charge.get("amount", None)

            if name is None or len(name) == 0:
                raise ValidationError(
                    {
                        "other_charge": ValidationError(
                            "Other charge name can not be empty.",
                            code=OrderErrorCode.INVALID,
                        )
                    }
                )

            if amount is None or amount < 0:
                raise ValidationError(
                    {
                        "other_charge": ValidationError(
                            "Other charge amount can not be negative.",
                            code=OrderErrorCode.INVALID,
                        )
                    }
                )

        cleaned_input["other_charge"] = other_charge

        order_type = data.pop("type", None)

        if order_type and order_type not in \
                [
                    OrderType.BUY,
                    OrderType.SELL
                ]:
            raise ValidationError(
                {
                    "type": ValidationError(
                        "Order type can only be BUY or SELL.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )
        elif order_type:
            cleaned_input['type'] = order_type

        order_status = data.pop("order_status", OrderStatusFilter.UNFULFILLED.value)

        if order_status not in \
                [
                    OrderStatusFilter.UNFULFILLED,
                    OrderStatusFilter.FULFILLED,
                ]:
            raise ValidationError(
                {
                    "order_status": ValidationError(
                        "Order status can only be UNFULFILLED or FULFILLED",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        cleaned_input["order_status"] = order_status

        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        with transaction.atomic():
            lines = cleaned_input["lines"]
            instance.status = cleaned_input["order_status"]
            instance.user = cleaned_input["user"]
            shipping_address = cleaned_input.get("shipping_address")
            billing_address = cleaned_input.get("billing_address")
            if cleaned_input["new_shipping_address"]:
                shipping_address.save()
            if cleaned_input["new_billing_address"]:
                billing_address.save()
            instance.shipping_address = shipping_address
            instance.billing_address = billing_address
            partner = cleaned_input["partner"]
            shipping = cleaned_input["shipping"]
            if cleaned_input["existing_shipping_method"] is not None:
                shipping_method = cleaned_input["existing_shipping_method"]
            else:
                shipping_method = ShippingMethodModel(
                    name=shipping["name"],
                    type="price",
                    price_amount=shipping["price"],
                    shipping_zone=cleaned_input["shipping_zone"]
                )
                shipping_method.save()
            instance.shipping_method = shipping_method
            instance.shipping_price_gross_amount = shipping_method.price_amount
            instance.shipping_price_net_amount = shipping_method.price_amount

            discount = cleaned_input["discount"]
            if discount is not None:
                voucher = VoucherModel(
                    type="entire_order",
                    code=generate_promo_code(),
                    name=discount.get("name", "") + "-" + discount.get("code", ""),
                    discount_value=discount["discount_value"],
                    discount_value_type=discount["discount_value_type"]
                )
                voucher.save()
                instance.voucher = voucher

            other_charge = cleaned_input["other_charge"]
            if other_charge:
                instance.other_charge_name = other_charge["name"]
                instance.other_charge_amount = other_charge["amount"]

            super().save(info, instance, cleaned_input)

            order_lines = []
            for item in lines:
                _sku = partner.partner_id + '-' + item.get("sku")
                product_variant = ProductVariantModel.objects.filter(sku=_sku).first()

                if product_variant:
                    product_id = product_variant.product_id
                    product = ProductModel.objects.get(pk=product_id)
                else:
                    product = ProductModel()

                category = item.get("category")
                category_object = CategoryModel.objects.filter(
                    Q(name__iexact=category) | Q(slug__iexact=category)
                ).first()
                if category_object is None:
                    category_object = CategoryModel(name=category, slug=slugify(category))
                    category_object.save()

                product.name = item.get("name")
                product.slug = item.get("name") + '-' + _sku
                product.description = item.get("description")
                product.price_amount = item.get("base_price")
                product.category_id = category_object.id
                product.product_type_id = ProductTypeModel.objects.first().id
                product.partner = partner
                product.is_published = True
                product.save()

                if product_variant is None:
                    product_variant = ProductVariantModel(product=product, sku=_sku)

                product_variant.name = item.get("name")
                product_variant.price_override_amount = item.get("base_price")
                product_variant.track_inventory = True
                product_variant.weight = item.get("weight")
                meta_data_items = {data.key: data.value for data in item.get("meta_data")}
                product_variant.metadata = meta_data_items
                product_variant.save()

                stock = StockModel.objects.filter(
                    product_variant=product_variant,
                    warehouse=cleaned_input["warehouse"]
                ).first()

                if stock is None:
                    stock = StockModel(
                        product_variant=product_variant,
                        warehouse=cleaned_input["warehouse"],
                        quantity=item.get("quantity")
                    )
                else:
                    stock.quantity = stock.quantity + item.get("quantity")

                stock.save()

                order_line = models.OrderLine(
                    order=instance,
                    product_name=product_variant.name,
                    product_sku=product_variant.sku,
                    quantity=item.get("quantity"),
                    variant=product_variant,
                    unit_price_net_amount=product_variant.price_override_amount,
                    variant_id=product_variant.id,
                    variant_name=product_variant.name,
                    unit_price_gross_amount=product_variant.price_override_amount,
                    is_shipping_required=True,

                )
                order_line.save()
                order_lines.append(order_line)

            order_created(instance, user=instance.user, from_draft=False)
            recalculate_order(instance)

            payment_status = cleaned_input['payment_status']
            payment = create_payment(
                gateway="rstore.payments",
                customer_ip_address=get_client_ip(info.context),
                email=instance.user_email,
                order=instance,
                payment_token=str(uuid.uuid4()),
                total=instance.total.gross.amount,
                currency=instance.total.gross.currency,
            )
            gateway.authorize(payment, payment.token)

            if payment_status == ChargeStatus.FULLY_CHARGED:
                gateway.capture(payment)

            generate_pdf_receipt(instance, order_lines, base_url=getattr(settings, "API_URL"))
            send_new_order_placement_sms.delay(instance.user.phone, instance.partner_order_id)

            for rule in Rule.objects.filter(is_active=True):
                if rule.get_latest_rule():
                    run_all(
                        rule_list=rule.get_latest_rule().engine_rule,
                        defined_variables=OrderVariables(instance),
                        defined_actions=OrderActions(instance),
                        stop_on_first_trigger=False
                    )

        month = datetime.today().strftime('%Y-%m') + '-01'
        add_general_achievement.delay(month, instance.pk, instance.user_id)
        calculate_partner_target_progress.delay(instance.pk)
        calculate_attribute_target_progress.delay(instance.pk)


class UpdateOrderInput(InputObjectType):
    partner_order_id = graphene.String(
        description=(
            "Actual order ID generated by the partner's system for the order.\n"
            "This field is required.\nIt is used to track the original order in the partner's system."
        ),
        required=True
    )
    payment_status = PaymentChargeStatusEnum(
        description=(
            "Status of the order's payment. This field is required if orderStatus is not provided.\n"
            "It only accepts \nFULLY_CHARGED, FULLY_REFUNDED or NOT_CHARGED as input"
        ),
        required=False
    )
    order_status = OrderStatusFilter(
        description=(
            "Status of the order. This field is required if paymentStatus is not provided.\n"
            "It only accepts \nUNFULFILLED, FULFILLED or CANCELED as input"

        ),
        required=False
    )


class UpdateOrder(ModelMutation):
    class Arguments:
        input = UpdateOrderInput(
            required=True, description="Fields required to update status or payment status of an order."
        )

    class Meta:
        description = "Updates existing order's status."
        model = models.Order
        permissions = (OrderPermissions.MANAGE_ORDERS,)
        error_type_class = OrderError
        error_type_field = "order_errors"
        exclude = ['order_receipt']

    @classmethod
    def get_instance(cls, info, **data):
        partner = None
        if info.context.app:
            partner = PartnerModel.objects.filter(partner_app=info.context.app).first()

        partner_order_id = data["input"]["partner_order_id"]
        instance = models.Order.objects.filter(Q(partner=partner) & Q(partner_order_id=partner_order_id)).first()
        return instance

    @classmethod
    def clean_input(cls, info, instance, data):

        cleaned_input = {}
        order_status = data.pop("order_status", None)
        payment_status = data.pop("payment_status", None)

        if order_status is None and payment_status is None:
            raise ValidationError(
                {
                    "order": ValidationError(
                        "Must provide order status or payment status information.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        if order_status is not None and order_status not in \
                [
                    OrderStatusFilter.UNFULFILLED,
                    OrderStatusFilter.FULFILLED,
                    OrderStatusFilter.CANCELED
                ]:
            raise ValidationError(
                {
                    "order_status": ValidationError(
                        "Order status can only be UNFULFILLED, FULFILLED or CANCELED",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        if payment_status is not None and \
                payment_status not in \
                [
                    ChargeStatus.FULLY_CHARGED,
                    ChargeStatus.FULLY_REFUNDED,
                    ChargeStatus.NOT_CHARGED
                ]:
            raise ValidationError(
                {
                    "payment_status": ValidationError(
                        "Payment status can only be FULLY_CHARGED, FULLY_REFUNDED or NOT_CHARGED",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        if instance is None:
            raise ValidationError(
                {
                    "order_id": ValidationError(
                        "Could not find order with given information.",
                        code=OrderErrorCode.INVALID,
                    )
                }
            )

        cleaned_input['order_status'] = order_status
        cleaned_input['payment_status'] = payment_status
        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        user = info.context.user
        notify_customer = False
        existing_order_status = instance.status
        order_status = cleaned_input['order_status']
        payment_status = cleaned_input['payment_status']
        payment = PaymentModel.objects.filter(order=instance).first()

        order_lines = models.OrderLine.objects.filter(order=instance)
        warehouse = WarehouseModel.objects.first()
        lines_for_warehouses = defaultdict(list)

        for order_line in order_lines:
            lines_for_warehouses[warehouse.id].append(
                {"order_line": order_line, "quantity": order_line.quantity}
            )

        if order_status == OrderStatusFilter.FULFILLED.value:
            if existing_order_status == OrderStatusFilter.UNFULFILLED.value:
                create_fulfillments(
                    user, instance, dict(lines_for_warehouses), notify_customer
                )
            elif existing_order_status == OrderStatusFilter.FULFILLED.value:
                pass
            else:
                raise ValidationError(
                    {
                        "order_status": ValidationError(
                            "Canceled order can not be fulfilled.",
                            code=OrderErrorCode.INVALID,
                        )
                    }
                )

        if order_status == OrderStatusFilter.UNFULFILLED.value:
            if existing_order_status == OrderStatusFilter.FULFILLED.value:
                fulfillments = models.Fulfillment.objects.filter(order=instance)
                for fulfillment in fulfillments:
                    cancel_fulfillment(fulfillment, user, warehouse)
                instance.status = order_status
            elif existing_order_status == OrderStatusFilter.UNFULFILLED.value:
                pass
            else:
                raise ValidationError(
                    {
                        "order_status": ValidationError(
                            "Canceled order can not be unfulfilled.",
                            code=OrderErrorCode.INVALID,
                        )
                    }
                )

        if order_status == OrderStatusFilter.CANCELED.value:
            if existing_order_status == OrderStatusFilter.UNFULFILLED.value:
                cancel_order(instance, user)
                remove_general_achievement.delay(instance.pk)
                remove_attribute_achievement.delay(instance.pk)
                remove_partner_achievement.delay(instance.pk)
            elif existing_order_status == OrderStatusFilter.CANCELED.value:
                pass
            else:
                fulfillments = models.Fulfillment.objects.filter(order=instance)
                for fulfillment in fulfillments:
                    cancel_fulfillment(fulfillment, user, warehouse)
                cancel_order(instance, user)
                remove_general_achievement.delay(instance.pk)
                remove_attribute_achievement.delay(instance.pk)
                remove_partner_achievement.delay(instance.pk)

        if payment_status == ChargeStatus.FULLY_REFUNDED:
            if payment and payment.charge_status == ChargeStatus.FULLY_CHARGED:
                gateway.refund(payment)
            elif payment and payment.charge_status == ChargeStatus.FULLY_REFUNDED:
                pass
            else:
                raise ValidationError(
                    {
                        "payment_status": ValidationError(
                            "An unpaid order can not be refunded.",
                            code=OrderErrorCode.CANNOT_REFUND,
                        )
                    }
                )

        if payment_status == ChargeStatus.FULLY_CHARGED:
            if payment and payment.charge_status == ChargeStatus.NOT_CHARGED:
                gateway.capture(payment)
            elif payment and payment.charge_status == ChargeStatus.FULLY_CHARGED:
                pass
            else:
                raise ValidationError(
                    {
                        "payment_status": ValidationError(
                            "A refunded order can not be paid again.",
                            code=OrderErrorCode.PAYMENT_ERROR,
                        )
                    }
                )

        if payment_status == ChargeStatus.NOT_CHARGED:
            if payment is None:
                payment = create_payment(
                    gateway="rstore.payments",
                    customer_ip_address=get_client_ip(info.context),
                    email=instance.user_email,
                    order=instance,
                    payment_token=str(uuid.uuid4()),
                    total=instance.total.gross.amount,
                    currency=instance.total.gross.currency,
                )
                gateway.authorize(payment, payment.token)
            elif payment and payment.charge_status == ChargeStatus.NOT_CHARGED:
                pass
            else:
                raise ValidationError(
                    {
                        "payment_status": ValidationError(
                            "A paid or refunded order can not be undone.",
                            code=OrderErrorCode.PAYMENT_ERROR,
                        )
                    }
                )

        instance.save()
        generate_pdf_receipt(instance, order_lines, base_url=getattr(settings, "API_URL"))
        if order_status is not None:
            update_order_sms.delay(instance.user.phone, instance.partner_order_id, order_status)
