import graphene
from graphene import relay

from ..core.connection import CountableDjangoObjectType
from ..meta.types import ObjectWithMetadata
from ...notification import models


class Announcement(CountableDjangoObjectType):
    class Meta:
        description = "Represents announcement data."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Announcement


class Segment(CountableDjangoObjectType):
    class Meta:
        description = "Represents segments data."
        interfaces = [relay.Node]
        model = models.Segment


class Notification(CountableDjangoObjectType):
    status = graphene.Int(description="Notification status")

    class Meta:
        description = "Represents Notification data."
        interfaces = [relay.Node]
        model = models.Notification


class NotificationMeta(CountableDjangoObjectType):
    class Meta:
        description = "Represents Notification Meta data."
        interfaces = [relay.Node]
        model = models.NotificationMeta
