import decimal
from datetime import datetime

from business_rules.actions import BaseActions, rule_action
from business_rules.fields import FIELD_NUMERIC, FIELD_TEXT
from business_rules.variables import BaseVariables, numeric_rule_variable, string_rule_variable, select_rule_variable, \
    select_multiple_rule_variable
from django.db.models import Sum

from ..order.models import OrderLine
from ..commission.models import Commission, Rule, CommissionServiceMonth
from ..graphql.commission.enums import VatAitEnum


class OrderVariables(BaseVariables):

    def __init__(self, order):
        self.order = order

    @string_rule_variable(label='Partner')
    def service(self):
        return self.order.partner.partner_id

    @numeric_rule_variable(label='Timeline')
    def timeline(self):
        return datetime.timestamp(self.order.created)

    @select_multiple_rule_variable(label='DCO')
    def dco(self):
        return [str(self.order.user.parent.id)]

    @select_multiple_rule_variable(label='DCM')
    def dcm(self):
        return [str(self.order.user.parent.parent.id)]

    @select_multiple_rule_variable(label='District')
    def district(self):
        return [str(item.district_id) for item in self.order.user.regions.all()]

    @select_multiple_rule_variable(label='Thana')
    def thana(self):
        return [str(item.thana_id) for item in self.order.user.regions.all()]

    @select_multiple_rule_variable(label='Group')
    def group(self):
        return [str(group.id) for group in self.order.user.groups.all()]

    @numeric_rule_variable(label='Transaction')
    def transaction(self):
        return float(self.order.total.gross.amount)

    @select_rule_variable(label='Product SKU')
    def product_sku(self):
        order_lines = OrderLine.objects.filter(order=self.order)
        return [str(order_line.product_sku) for order_line in order_lines]

    @string_rule_variable(label='Profile')
    def profile(self):
        user_profile = self.order.user.get_profile()
        if user_profile:
            profile_name = user_profile.name
        else:
            profile_name = ''

        return profile_name


def calculate_net_amount(vat_ait, base_amount):
    net_output = 0

    if vat_ait == VatAitEnum.INCLUDE_VAT.value:
        net_output = base_amount / 1.15
    elif vat_ait == VatAitEnum.EXCLUDE_VAT.value:
        net_output = base_amount + (base_amount * 0.15)
    elif vat_ait == VatAitEnum.INCLUDE_VAT_AIT.value:
        net_output = (base_amount / 1.15) - ((base_amount / 1.15) * 0.10)
    elif vat_ait == VatAitEnum.EXCLUDE_VAT_AIT.value:
        net_output = base_amount + (base_amount * 0.15) + (base_amount * 0.10)

    return decimal.Decimal(net_output)


def create_commission(user, order, amount, rule):
    # month = datetime.today().strftime("%Y-%m-01")
    month = order.created.strftime("%Y-%m-01")
    service_month, created = CommissionServiceMonth.objects.get_or_create(service=order.partner, month=month, user=user)

    commission_item = Commission()
    commission_item.user = user
    commission_item.order = order
    commission_item.amount = amount
    commission_item.rule_history = rule
    commission_item.commission_service_month = service_month
    commission_item.save()


class OrderActions(BaseActions):

    def __init__(self, order):
        self.order = order

    @rule_action(params={
        'max_cap': FIELD_NUMERIC,
        'rule_id': FIELD_NUMERIC,
        'commission': FIELD_NUMERIC,
        'vat_ait': FIELD_TEXT,
    })
    def calculate_commission_absolute(self, max_cap, rule_id, commission, vat_ait):
        rule = Rule.objects.get(pk=rule_id).get_latest_rule()
        quantity = list(OrderLine.objects.filter(order=self.order).aggregate(Sum('quantity')).values())[0]
        total_amount = quantity * commission
        total_amount = max_cap if total_amount > max_cap else total_amount
        net_amount = calculate_net_amount(vat_ait, total_amount)
        create_commission(self.order.user, self.order, net_amount, rule)

    @rule_action(params={
        'max_cap': FIELD_NUMERIC,
        'rule_id': FIELD_NUMERIC,
        'commission': FIELD_NUMERIC,
        'vat_ait': FIELD_TEXT,
    })
    def calculate_commission_percentage(self, max_cap, rule_id, commission, vat_ait):
        rule = Rule.objects.get(pk=rule_id).get_latest_rule()
        total_amount = float(self.order.total.gross.amount)
        total_amount = total_amount * (commission / 100)
        total_amount = max_cap if total_amount > max_cap else total_amount
        net_amount = calculate_net_amount(vat_ait, total_amount)

        create_commission(self.order.user, self.order, net_amount, rule)

    @rule_action(params={
        'max_cap': FIELD_NUMERIC,
        'rule_id': FIELD_NUMERIC,
        'commission': FIELD_NUMERIC,
        'product_sku': FIELD_TEXT,
        'vat_ait': FIELD_TEXT,
    })
    def calculate_commission_absolute_product(self, max_cap, rule_id, commission, product_sku, vat_ait):
        rule = Rule.objects.get(pk=rule_id).get_latest_rule()
        quantity = OrderLine.objects.filter(order=self.order, product_sku=product_sku).first().quantity
        total_amount = quantity * commission
        total_amount = max_cap if total_amount > max_cap else total_amount
        net_amount = calculate_net_amount(vat_ait, total_amount)

        create_commission(self.order.user, self.order, net_amount, rule)

    @rule_action(params={
        'max_cap': FIELD_NUMERIC,
        'rule_id': FIELD_NUMERIC,
        'commission': FIELD_NUMERIC,
        'product_sku': FIELD_TEXT,
        'vat_ait': FIELD_TEXT,
    })
    def calculate_commission_percentage_product(self, max_cap, rule_id, commission, product_sku, vat_ait):
        rule = Rule.objects.get(pk=rule_id).get_latest_rule()
        order_line = OrderLine.objects.filter(order=self.order, product_sku=product_sku).first()
        total_amount = order_line.quantity * float(order_line.unit_price_gross_amount)
        total_amount = total_amount * (commission / 100)
        total_amount = max_cap if total_amount > max_cap else total_amount
        net_amount = calculate_net_amount(vat_ait, total_amount)

        create_commission(self.order.user, self.order, net_amount, rule)
