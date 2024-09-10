import graphene
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.query_utils import Q

from .types import Segment
from ...notification import models


def resolve_notifications(info):
    user = info.context.user
    user_group = user.groups.first()
    user_region = user.regions.all()
    notifications = models.Notification.objects.filter(
        Q(recipients=user) | Q(groups=user_group) | Q(regions__in=user_region)
    )
    for notification in notifications:
        try:
            models.NotificationMeta.objects.get(notification=notification, recipient=user)
            notification.status = 1
        except ObjectDoesNotExist:
            notification.status = 0
    return notifications


def resolve_notification(notification_id):
    _model, notification_pk = graphene.Node.from_global_id(notification_id)
    return models.Notification.objects.get(id=notification_pk)


def resolve_unread_notification(info):
    notifications = resolve_notifications(info)
    read_notification = list(models.NotificationMeta.objects.values_list('notification_id', flat=True))
    unread_notification = notifications.exclude(id__in=read_notification)
    return unread_notification.count()


def resolve_announcements():
    return models.Announcement.objects.all()


def resolve_announcement(announcement_id):
    _model, notification_pk = graphene.Node.from_global_id(announcement_id)
    return models.Announcement.objects.get(id=notification_pk)


def resolve_segments():
    return models.Segment.objects.all()


def resolve_segment(info, segment_id):
    return graphene.Node.get_node_from_global_id(info, segment_id, Segment)
