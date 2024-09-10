import json

import graphene
from django.core.exceptions import ValidationError

from ...meta.mutations import UpdateMetadata
from ....core.permissions import AnnouncementPermissions
from ...core.mutations import ModelMutation, ModelDeleteMutation
from ...core.types.common import AnnouncementError
from ....notification import NotificationTarget, models
from ....notification.adapters import Webpushr

from ....notification.error_codes import AnnouncementErrorCode

webpushr = Webpushr()


class CreateAnnouncementInput(graphene.InputObjectType):
    title = graphene.String(description="Announcement title", required=True)
    message = graphene.String(description="Announcement title", required=True)
    target_url = graphene.String(description="Announcement title", required=True)
    send_to_all = graphene.Boolean(description="Sent to all", required=True)
    target = graphene.String(description="Target", required=False)
    recipients = graphene.List(description="ID of recipients", of_type=graphene.String, required=False)


class CreateAnnouncement(ModelMutation):
    class Arguments:
        input = CreateAnnouncementInput(
            required=True,
            description="Fields required to create a Announcement."
        )

    class Meta:
        description = "Create a new Announcement."
        model = models.Announcement
        permissions = (AnnouncementPermissions.MANAGE_ANNOUNCEMENTS,)
        error_type_class = AnnouncementError
        error_type_field = "announcement_errors"

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        is_sending_to_all = data.get("send_to_all")

        if not is_sending_to_all:
            target = data.get("target")
            recipients = data.get("recipients")
            if not target:
                raise ValidationError(
                    {
                        "target": ValidationError(
                            "Target is required", code=AnnouncementErrorCode.TARGET_REQUIRED
                        )
                    }
                )
            if not recipients:
                raise ValidationError(
                    {
                        "recipients": ValidationError(
                            "Recipients is required", code=AnnouncementErrorCode.RECIPIENT_REQUIRED
                        )
                    }
                )

            if target not in NotificationTarget.get_keys():
                raise ValidationError(
                    {
                        "target": ValidationError(
                            "Given target type is not valid", code=AnnouncementErrorCode.INVALID
                        )
                    }
                )
        return super().clean_input(info, instance, data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        if instance.send_to_all:
            response = webpushr.send_to_all(instance)
            if response.ok:
                instance.save()
            else:
                raise Exception(json.loads(response.content)['description'])

        target = cleaned_input.get('target')
        recipients = cleaned_input.get('recipients')
        meta_items = {'target': target, 'recipients': recipients}
        if not instance.send_to_all:
            if target == NotificationTarget.SEGMENT:
                instance.segments = recipients
                response = webpushr.send_to_segment(instance)
                if response.ok:
                    cls.save_with_recipients(info, instance, meta_items)
                else:
                    raise Exception(json.loads(response.content)['description'])

            elif target == NotificationTarget.USER:
                users = {}
                for recipient in recipients:
                    users['username'] = recipient
                instance.users = users
                response = webpushr.send_to_target_audience(instance)
                if response.ok:
                    cls.save_with_recipients(info, instance, meta_items)
                else:
                    raise Exception(json.loads(response.content)['description'])
            else:
                raise ValueError(target + ' is not a valid target')

    @classmethod
    def save_with_recipients(cls, info, instance, meta_items):
        instance.save()
        data = {"id": graphene.Node.to_global_id("Announcement", instance.pk)}
        meta_instance = UpdateMetadata.get_instance(info, **data)
        if meta_instance:
            meta_instance.store_value_in_metadata(items=meta_items)
            meta_instance.save(update_fields=["metadata"])


class AnnouncementDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a Announcement to delete.")

    class Meta:
        description = "Deletes a Announcement."
        model = models.Announcement
        permissions = (AnnouncementPermissions.MANAGE_ANNOUNCEMENTS,)
        error_type_class = AnnouncementError
        error_type_field = "announcement_errors"
