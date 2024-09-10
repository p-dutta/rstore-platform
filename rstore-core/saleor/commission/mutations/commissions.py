import graphene
from django.core.exceptions import ValidationError
from datetime import datetime

from .. import CommissionStatus
from ..enums import CommissionStatusEnum
from ...core.mutations import ModelMutation
from ...core.types.common import CommissionError
from ....commission.error_codes import CommissionErrorCode
from ....core.permissions import CommissionPermissions
from ....commission import models


class UpdateCommissionStatusInput(graphene.InputObjectType):
    status = CommissionStatusEnum(description="Status of the CommissionServiceMonth: pending/confirmed/done", required=True)


class UpdateCommissionStatus(ModelMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a CommissionServiceMonth to update.")
        input = UpdateCommissionStatusInput(
            required=True, description="Fields required to update a CommissionServiceMonth."
        )

    class Meta:
        description = "Updates status of a CommissionServiceMonth."
        model = models.CommissionServiceMonth
        permissions = (CommissionPermissions.MANAGE_COMMISSIONS,)
        error_type_class = CommissionError
        error_type_field = "commission_errors"

    @classmethod
    def clean_input(cls, info, instance, data, **kwargs):

        if instance.status == CommissionStatus.DONE:
            raise ValidationError(
                {
                    "status": ValidationError(
                        "Commission status is already set to done.",
                        code=CommissionErrorCode.INVALID
                    )
                }
            )

        commission_month = instance.month.strftime("%Y-%m")
        current_month = datetime.now().date().strftime("%Y-%m")
        if commission_month >= current_month:
            raise ValidationError(
                {
                    "status": ValidationError(
                        "You can update commission status for a past month only",
                        code=CommissionErrorCode.INVALID
                    )
                }
            )

        return super().clean_input(info, instance, data)
