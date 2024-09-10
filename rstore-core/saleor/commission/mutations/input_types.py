import graphene
from ..enums import RuleCategoryEnum, GroupEnum, CommissionCategoryEnum, CommissionTypeEnum, ProfileTypeEnum, \
    RuleTypeEnum, VatAitEnum


class TimelineInput(graphene.InputObjectType):
    use_timeline = graphene.Boolean(default_value=False, required=True)
    start_date = graphene.types.datetime.Date(
        description=(
            "Start date for campaign by timeline. ISO 8601 standard: YYYY-MM-DD"
            " Required when use_timeline is True."
        )
    )
    end_date = graphene.types.datetime.Date(
        description=(
            "End date for campaign by timeline.ISO 8601 standard: YYYY-MM-DD"
            " Required when use_timeline is True."
        )
    )


class TargetByGeographyInput(graphene.InputObjectType):
    districts = graphene.List(
        description=(
            "List of District IDs to be targeted."
            "Required if target_by_geography=True"
        ),
        default_value=[],
        of_type=graphene.String
    )
    thanas = graphene.List(
        description=(
            "List of Thana IDs to be targeted. Optional"
        ),
        default_value=[],
        of_type=graphene.String
    )


class TargetByGroupInput(graphene.InputObjectType):
    name = GroupEnum(
        description=(
            "DCO/DCM: Required if target_by_group=True"
        ),
        default_value=None
    )
    users = graphene.List(
        graphene.String,
        description=(
            "List of DCO/DCM ids: Required if target_by_group=True"
        ),
        default_value=[]
    )


class TargetByInput(graphene.InputObjectType):
    target_by_all = graphene.Boolean(description="If target by all users", default_value=False)
    target_by_profile = graphene.Boolean(description="If target by profile", default_value=False)
    target_by_geography = graphene.Boolean(description="If target by geography", default_value=False)
    target_by_group = graphene.Boolean(description="If target by groups", default_value=False)
    profile = graphene.String(
        description=(
            "Name of the User Profile to be targeted."
            "Required if target_by_profile=True"
        )
    )
    geography = TargetByGeographyInput(
        description=(
            "Geography to be targeted by district and/or thana"
            "Required if target_by_geography=True"
        ),
        default_value=None
    )
    group = TargetByGroupInput(
        description=(
            "Profile to be targeted. Platinum/Gold/Silver/Bronze"
            "Required if target_by_group=True"
        ),
        default_value=None
    )


class RangeInput(graphene.InputObjectType):
    min = graphene.Float(description="Minimum value of range")
    max = graphene.Float(description="Maximum value of range")
    commission = graphene.Float(description="Maximum value of range")
    max_cap = graphene.Float(description="Max cap")


class ProductInputForRule(graphene.InputObjectType):
    product_sku = graphene.String(description="SKU of the product")
    commission = graphene.Float(description="Maximum value of range")
    max_cap = graphene.Float(description="Max cap")


class FixedCommissionInput(graphene.InputObjectType):
    commission = graphene.Float(
        description=(
            "Fixed commission."
        ),
        required=False
    )
    max_cap = graphene.Float(
        description=(
            "Max Cap."
        ),
        required=False
    )


class CommissionCalculationInput(graphene.InputObjectType):
    commission_type = CommissionTypeEnum(
        description=(
            "Commission type: absolute/percentage"
        ),
        required=True
    )
    commission_category = CommissionCategoryEnum(
        description=(
            "Commission Category: fixed/range/product"
        ),
        required=True
    )
    fixed = graphene.Field(
        description=(
            "Input values for `fixed` commission. Required if commission_category=`fixed`."
        ),
        type=FixedCommissionInput
    )
    range = graphene.List(
        description=(
            "List of range values. Required if commission_category=`range`."
        ),
        of_type=RangeInput
    )
    product = graphene.List(
        description=(
            "List of products. Required if commission_category=`product`."
        ),
        of_type=ProductInputForRule
    )
    vat_ait = VatAitEnum(
        description=(
            "Include/exclude vat/ait: INCLUDE_VAT/INCLUDE_VAT_AIT/EXCLUDE_VAT/EXCLUDE_VAT_AIT"
        ),
        required=True
    )


class CreateRuleInput(graphene.InputObjectType):
    name = graphene.String(description="Name of the rule", required=True)
    service = graphene.String(description="Name of the service", required=True)
    type = RuleTypeEnum(
        description=(
            "Rule type: regular/campaign"
        ),
        required=True
    )
    category = RuleCategoryEnum(
        description=(
            "Rule category: realtime/consolidate"
        ),
        required=True
    )
    is_active = graphene.Boolean(description="Is Active", default_value=True)
    timeline = TimelineInput(description="Timeline", required=True)
    target = TargetByInput(description="Target by", required=True)
    calculation = CommissionCalculationInput(description="Commission calculation input", required=True)

