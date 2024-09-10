import graphene
from django.core.exceptions import ValidationError
from graphene.types import InputObjectType

from ...core.mutations import ModelMutation, ModelDeleteMutation
from ...core.types.common import UserProfileError
from ....commission.error_codes import UserProfileErrorCode
from ....commission.models import UserProfile
from ....core.permissions import CommissionPermissions
from ....commission import models


class CreateUserProfileInput(InputObjectType):
    name = graphene.String(description="Name of the profile.", required=True)
    total_orders = graphene.Int(
        description="Number of orders for the profile.", required=True
    )
    total_transaction = graphene.Int(
        description="Number of transaction for user profile.", required=True
    )
    priority_order = graphene.Int(
        description="Priority of the profile.", required=True
    )
    period = graphene.Int(
        description="Period of calculation.", required=False
    )


class CreateUserProfile(ModelMutation):
    class Arguments:
        input = CreateUserProfileInput(
            required=True, description="Fields required to create a user profile."
        )

    class Meta:
        description = "Creates a new user profile."
        model = models.UserProfile
        permissions = (CommissionPermissions.MANAGE_COMMISSIONS,)
        error_type_class = UserProfileError
        error_type_field = "user_profile_errors"

    @classmethod
    def clean_input(cls, info, instance, data, **kwargs):
        data['name'] = data.get('name').lower()
        validate_data(data)
        return super().clean_input(info, instance, data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        instance.save()


class UpdateUserProfileInput(InputObjectType):
    name = graphene.String(description="Name of the profile.", required=False)
    total_orders = graphene.Int(
        description="Number of orders for the profile.", required=False
    )
    total_transaction = graphene.Int(
        description="Number of transaction for user profile.", required=False
    )
    priority_order = graphene.Int(
        description="Priority of the profile.", required=False
    )
    period = graphene.Int(
        description="Period of calculation.", required=False
    )


class UpdateUserProfile(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a user profile to update.", required=True)
        input = UpdateUserProfileInput(
            required=False, description="Fields required to update a user profile."
        )

    class Meta:
        description = "Updates a new user profile."
        model = models.UserProfile
        permissions = (CommissionPermissions.MANAGE_COMMISSIONS,)
        error_type_class = UserProfileError
        error_type_field = "user_profile_errors"

    @classmethod
    def clean_input(cls, info, instance, data, **kwargs):
        data['name'] = data.get('name').lower()
        validate_data(data, instance)
        return super().clean_input(info, instance, data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        instance.save()


class DeleteUserProfile(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(description="ID of a user profile to delete.", required=True)

    class Meta:
        description = "Deletes user profile."
        model = models.UserProfile
        permissions = (CommissionPermissions.MANAGE_COMMISSIONS,)
        error_type_class = UserProfileError
        error_type_field = "user_profile_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        try:
            user_profile = cls.get_node_or_error(info, data.get("id"))
        except:
            raise ValidationError(
                {
                    "id": ValidationError(
                        "No User Profile found with this ID",
                        code=UserProfileErrorCode.NOT_FOUND
                    )
                }
            )
        db_id = user_profile.id
        user_profile.delete()
        user_profile.id = db_id
        return cls.success_response(user_profile)


def validate_data(data, instance=None):
    priority_order = data.get('priority_order') if data.get('priority_order') else instance.priority_order
    total_orders = data.get('total_orders') if data.get('total_orders') else instance.total_orders
    total_transaction = data.get('total_transaction') if data.get('total_transaction') else instance.total_transaction
    all_user_profile = UserProfile.objects.all().order_by('priority_order')
    previous_profile = next_profile = None

    for profile in all_user_profile:
        if profile.priority_order < priority_order:
            previous_profile = profile
        elif profile.priority_order > priority_order:
            next_profile = profile
            break

    if previous_profile:
        if total_orders <= previous_profile.total_orders or total_transaction <= previous_profile.total_transaction:
            raise ValidationError(
                {
                    "": ValidationError(
                        f"Total order should be greater than {previous_profile.total_orders}. "
                        f"Total transaction should be greater than {previous_profile.total_transaction}",
                        code=UserProfileErrorCode.INVALID
                    )
                }
            )
    if next_profile:
        if total_orders >= next_profile.total_orders or total_transaction >= next_profile.total_transaction:
            raise ValidationError(
                {
                    "": ValidationError(
                        f"Total order should be smaller than {next_profile.total_orders}. "
                        f"Total transaction should be smaller than {next_profile.total_transaction}",
                        code=UserProfileErrorCode.INVALID
                    )
                }
            )
