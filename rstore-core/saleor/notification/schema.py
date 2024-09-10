from typing import Counter
import graphene
from saleor.graphql.core.connection import CountableConnection, CountableDjangoObjectType

from .filters import SegmentFilterInput
from .types import Announcement, Segment, Notification
from .resolvers import resolve_announcement, resolve_announcements, resolve_segment, resolve_segments, \
    resolve_notifications, resolve_notification, resolve_unread_notification
from .mutations.announcement import CreateAnnouncement, AnnouncementDelete
from .mutations.segment import CreateSegment, SegmentDelete
from .mutations.notification_meta import CreateNotificationMeta, NotificationMetaDelete

from ..core.fields import FilterInputConnectionField
from ..decorators import permission_required
from ...core.permissions import AnnouncementPermissions, NotificationPermissions


class AnnouncementQueries(graphene.ObjectType):
    announcements = FilterInputConnectionField(
        Announcement,
        description='Title of announcements'
    )

    announcement = graphene.Field(
        Announcement,
        id=graphene.ID(description="Announcement id"),
        description="Get announcement details using id"
    )

    @permission_required(AnnouncementPermissions.MANAGE_ANNOUNCEMENTS)
    def resolve_announcements(self, info, **kwargs):
        return resolve_announcements()

    @permission_required(AnnouncementPermissions.MANAGE_ANNOUNCEMENTS)
    def resolve_announcement(self, info, id):
        return resolve_announcement(id)


class NotificationQueries(graphene.ObjectType):
    notifications = graphene.List(
        Notification,
        description='List of notifications'
    )

    notification = graphene.Field(
        Notification,
        id=graphene.ID(description="Notification id"),
        description="Get notification details using id"
    )

    unread_notifications = graphene.Field(
        graphene.Int,
        description="Get unread notifications counts of given user id"
    )

    @permission_required(NotificationPermissions.VIEW_NOTIFICATIONS)
    def resolve_notifications(self, info, **kwargs):
        return resolve_notifications(info)

    @permission_required(NotificationPermissions.VIEW_NOTIFICATIONS)
    def resolve_notification(self, info, id):
        return resolve_notification(id)

    @permission_required(NotificationPermissions.VIEW_NOTIFICATIONS)
    def resolve_unread_notifications(self, info):
        return resolve_unread_notification(info)

class SegmentQueries(graphene.ObjectType):
    segments = FilterInputConnectionField(
        Segment,
        filter=SegmentFilterInput(description="Filtering options for segments"),
        description='Name of segment'
    )

    segment = graphene.Field(
        Segment,
        description="Look up a segment by ID.",
        id=graphene.Argument(graphene.ID, description="ID of a segment.", required=True)
    )

    @permission_required(AnnouncementPermissions.MANAGE_ANNOUNCEMENTS)
    def resolve_segments(self, info, **kwargs):
        return resolve_segments()

    @permission_required(AnnouncementPermissions.MANAGE_ANNOUNCEMENTS)
    def resolve_segment(self, info, **data):
        return resolve_segment(info, data.get("id"))


class AnnouncementMutations(graphene.ObjectType):
    create_announcement = CreateAnnouncement.Field()
    delete_announcement = AnnouncementDelete.Field()


class SegmentMutations(graphene.ObjectType):
    create_segment = CreateSegment.Field()
    delete_segment = SegmentDelete.Field()


class NotificationMetaMutations(graphene.ObjectType):
    create_notification_meta = CreateNotificationMeta.Field()
    delete_notification_meta = NotificationMetaDelete.Field()
