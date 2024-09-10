import graphene


class RuleCategoryEnum(graphene.Enum):
    REALTIME = "realtime"
    CONSOLIDATE = "consolidate"


class RuleTypeEnum(graphene.Enum):
    REGULAR = "regular"
    CAMPAIGN = "campaign"


class GroupEnum(graphene.Enum):
    DCO = "dco"
    DCM = "dcm"


class TargetByTypeEnum(graphene.Enum):
    ALL = "all"
    PROFILE = "profile"
    GEOGRAPHY = "geography"
    GROUP = "group"


class ProfileTypeEnum(graphene.Enum):
    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


class CommissionTypeEnum(graphene.Enum):
    ABSOLUTE = "absolute"
    PERCENTAGE = "percentage"


class CommissionCategoryEnum(graphene.Enum):
    FIXED = "fixed"
    RANGE = "range"
    PRODUCT = "product"


class CommissionStatusEnum(graphene.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DONE = "done"


class VatAitEnum(graphene.Enum):
    INCLUDE_VAT = "include_vat"
    INCLUDE_VAT_AIT = "include_vat_ait"
    EXCLUDE_VAT = "exclude_vat"
    EXCLUDE_VAT_AIT = "exclude_vat_ait"
