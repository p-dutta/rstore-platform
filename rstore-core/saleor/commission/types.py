from operator import itemgetter

import graphene
from graphene import relay
from graphene.types.generic import GenericScalar

from ..account.types import User
from ..core.connection import CountableDjangoObjectType
from ..partner.types import Partner
from ...commission import models


class RuleMetadataItem(graphene.ObjectType):
    key = graphene.String(required=True, description="Key of a item.")
    value = GenericScalar(required=True, description="Value of a item.")


class ObjectWithRuleMetadata(graphene.Interface):
    client_rule = graphene.List(
        RuleMetadataItem,
        required=True,
        description=(
            "List of client rule items."
        ),
    )

    @staticmethod
    def resolve_client_rule(root: models.Rule, info):
        if root.get_latest_rule() is not None:
            return resolve_client_rule(root.get_latest_rule().client_rule, info)
        else:
            return []


class ObjectWithRuleHistoryMetadata(graphene.Interface):
    client_rule = graphene.List(
        RuleMetadataItem,
        required=True,
        description=(
            "List of client rule items."
        ),
    )

    @staticmethod
    def resolve_client_rule(root: models.RuleHistory, info):
        return resolve_client_rule(root.client_rule, info)


class RuleHistory(CountableDjangoObjectType):
    class Meta:
        description = "Represents rule history instance."
        model = models.RuleHistory
        interfaces = [relay.Node, ObjectWithRuleMetadata]
        only_fields = ["client_rule", "created", "updated"]


class Rule(CountableDjangoObjectType):
    class Meta:
        description = "Represents rule data."
        interfaces = [relay.Node, ObjectWithRuleMetadata]
        model = models.Rule
        only_fields = ["name", "type", "category", "commission_category", "client_rule", "is_active", "created",
                       "updated"]


class Commission(CountableDjangoObjectType):
    rule = graphene.Field(Rule, description="A rule item")

    class Meta:
        description = "Represents commission"
        interfaces = [relay.Node]
        model = models.Commission

    @staticmethod
    def resolve_rule(root: models.Commission, info):
        return root.rule_history.rule


class CommissionsGroup(CountableDjangoObjectType):
    service = graphene.Field(Partner, description="Partner")
    service_commissions = graphene.List(Commission, description="List of commissions")
    month = graphene.String(description="Month of the TargetUser.")
    user = graphene.Field(User, description="User")
    total_amount = graphene.Float(description="Total consolidated amount")

    class Meta:
        model = models.CommissionServiceMonth
        interfaces = [relay.Node]

    def resolve_total_amount(self, info):
        total = 0
        for commission in self.service_commissions:
            total += commission.amount
        return total


class UserProfile(CountableDjangoObjectType):
    class Meta:
        description = "Represents user profile."
        interfaces = [relay.Node]
        model = models.UserProfile


class ServiceCommission(graphene.ObjectType):
    commission_amount = graphene.Float(description="Partner's commission")
    service = graphene.Field(Partner, description="Partner")

    class Meta:
        description = "Represents partner"
        interfaces = [relay.Node]


class MonthlyServiceCommission(graphene.ObjectType):
    total_commission = graphene.Float(description='Total commission by month')
    top_services = graphene.List(of_type=ServiceCommission, description='Service Commission')

    class Meta:
        description = "Represents service list by commission"
        interfaces = [relay.Node]


def resolve_client_rule(root, _info):
    return sorted(
        [{"key": k, "value": v} for k, v in root.items()], key=itemgetter("key"),
    )
