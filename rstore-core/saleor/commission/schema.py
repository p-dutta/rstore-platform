import graphene
from .filters import RuleFilterInput, CommissionFilterInput
from .types import Rule, Commission, UserProfile, CommissionsGroup, MonthlyServiceCommission
from .mutations.rule import CreateRule, UpdateRule, RuleDelete
from .mutations.user_profile import CreateUserProfile, UpdateUserProfile, DeleteUserProfile
from .resolvers import resolve_rules, resolve_rule, resolve_commissions, resolve_commission, resolve_user_profiles, \
    resolve_user_profile, resolve_get_user_by_user_profile, resolve_monthly_service_commission
from ..account.types import User
from ..core.fields import FilterInputConnectionField
from ..decorators import permission_required
from ...core.permissions import RulePermissions, CommissionPermissions
from .mutations.commissions import UpdateCommissionStatus


class RuleQueries(graphene.ObjectType):
    rules = FilterInputConnectionField(
        Rule,
        filter=RuleFilterInput(description="Filtering options for rules."),
        description='List of rules'
    )

    rule = graphene.Field(
        Rule,
        id=graphene.ID(description="Rule id"),
        description="Get rule details using rule id"
    )

    @permission_required(RulePermissions.VIEW_RULE)
    def resolve_rules(self, info, **kwargs):
        return resolve_rules()

    @permission_required(RulePermissions.VIEW_RULE)
    def resolve_rule(self, info, id):
        return resolve_rule(id)


class RuleMutations(graphene.ObjectType):
    create_rule = CreateRule.Field()
    update_rule = UpdateRule.Field()
    delete_rule = RuleDelete.Field()


class CommissionQueries(graphene.ObjectType):
    commissions = FilterInputConnectionField(
        CommissionsGroup,
        filter=CommissionFilterInput(description="Filtering options for commission."),
        description='List of commissions.'
    )

    commission = graphene.Field(
        CommissionsGroup,
        id=graphene.ID(description="Commission service month id"),
        description="Get commission details with commission service "
    )

    monthly_service_commission = graphene.Field(
        MonthlyServiceCommission,
        month=graphene.Argument(graphene.String, description='Month', required=True),
        description='Month wise commission by service'
    )

    @permission_required(CommissionPermissions.VIEW_COMMISSION)
    def resolve_commissions(self, info, **kwargs):
        return resolve_commissions(info, **kwargs)

    @permission_required(CommissionPermissions.VIEW_COMMISSION)
    def resolve_commission(self, _info, id):
        return resolve_commission(id)

    @permission_required(CommissionPermissions.VIEW_COMMISSION)
    def resolve_monthly_service_commission(self, info, month, **kwargs):
        return resolve_monthly_service_commission(info, month)


class UserProfileQueries(graphene.ObjectType):
    user_profiles = FilterInputConnectionField(
        UserProfile,
        description='List of user_profiles'
    )

    user_profile = graphene.Field(
        UserProfile,
        id=graphene.ID(description="User Profile id"),
        description="Get user profile details using id"
    )

    get_user_by_user_profile = graphene.List(
        User,
        name=graphene.Argument(graphene.String, description="User profile name", required=True),
        description="Get list of users of a user profile"
    )

    @permission_required(CommissionPermissions.VIEW_COMMISSION)
    def resolve_user_profiles(self, info, **kwargs):
        return resolve_user_profiles()

    @permission_required(CommissionPermissions.VIEW_COMMISSION)
    def resolve_user_profile(self, info, id):
        return resolve_user_profile(id)

    @permission_required(CommissionPermissions.VIEW_COMMISSION)
    def resolve_get_user_by_user_profile(self, info, **kwargs):
        return resolve_get_user_by_user_profile(info, **kwargs)


class UserProfileMutations(graphene.ObjectType):
    create_user_profile = CreateUserProfile.Field()
    update_user_profile = UpdateUserProfile.Field()
    delete_user_profile = DeleteUserProfile.Field()


class CommissionMutations(graphene.ObjectType):
    update_commission_status = UpdateCommissionStatus.Field()
