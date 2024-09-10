import graphene

from ...core.mutations import ModelMutation, ModelDeleteMutation
from ...core.types.common import NotificationMetaError
from ....core.permissions import NotificationMetaPermissions

from ....notification import models


class CreateNotificationMetaInput(graphene.InputObjectType):
    notification = graphene.ID(description="notification id", required=True)


class CreateNotificationMeta(ModelMutation):
    class Arguments:
        input = CreateNotificationMetaInput(
            required=True,
            description="Fields required to create a notification meta."
        )

    class Meta:
        description = "Create a new notification meta."
        model = models.NotificationMeta
        permissions = (NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS,)
        error_type_class = NotificationMetaError
        error_type_field = "notification_meta_errors"

    @classmethod
    def clean_instance(cls, info, instance):
        recipient = info.context.user
        instance.recipient = recipient

    @classmethod
    def get_instance(cls, info, **data):
        id = data.get("input")['notification']
        _, notification_pk = graphene.Node.from_global_id(id)
        notification = models.Notification.objects.get(id=notification_pk)
        notification_meta, _ = models.NotificationMeta.objects.get_or_create(notification=notification,
                                                                             recipient=info.context.user)
        return notification_meta


class NotificationMetaDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a notification meta to delete.")

    class Meta:
        description = "Deletes a notification meta."
        model = models.NotificationMeta
        permissions = (NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS,)
        error_type_class = NotificationMetaError
        error_type_field = "notification_meta_errors"
