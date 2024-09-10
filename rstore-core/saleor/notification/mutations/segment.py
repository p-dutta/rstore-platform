import graphene

from ....core.permissions import NotificationPermissions
from ...core.mutations import ModelMutation, ModelDeleteMutation
from ...core.types.common import SegmentError
from ....notification import models


class CreateSegmentInput(graphene.InputObjectType):
    name = graphene.String(description="Segment name", required=True)
    segment_id = graphene.String(description="Segment id", required=True)
    details = graphene.String(description="Segment description", required=True)


class CreateSegment(ModelMutation):

    class Arguments:
        input = CreateSegmentInput(
            required=True,
            description="Fields required to create a segment."
        )

    class Meta:
        description = "Create a new segment."
        model = models.Segment
        permissions = (NotificationPermissions.MANAGE_NOTIFICATIONS,)
        error_type_class = SegmentError
        error_type_field = "segment_errors"


class SegmentDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a segment to delete.")

    class Meta:
        description = "Deletes a segment."
        model = models.Segment
        permissions = (NotificationPermissions.MANAGE_NOTIFICATIONS,)
        error_type_class = SegmentError
        error_type_field = "segment_errors"
