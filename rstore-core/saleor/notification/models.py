from auditlog.registry import auditlog
from django.contrib.auth.models import Group
from django.contrib.postgres.fields.jsonb import JSONField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.deletion import SET_NULL

from saleor.account.models import User, Region
from saleor.commission.models import UserProfile
from saleor.core.models import ModelWithMetadata
from saleor.core.permissions import NotificationPermissions, AnnouncementPermissions, NotificationMetaPermissions
from saleor.notification import NotificationType


class Announcement(ModelWithMetadata):
    title = models.CharField(max_length=100, null=False)
    message = models.CharField(max_length=250, null=False)
    target_url = models.URLField(max_length=255, null=False)
    send_to_all = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    schedule = models.DateTimeField(auto_now=True, editable=True)

    class Meta:
        app_label = "notification"
        verbose_name = "announcement"
        verbose_name_plural = "announcement"
        ordering = ("-created",)
        permissions = (
            (AnnouncementPermissions.MANAGE_ANNOUNCEMENTS.codename, "Manage announcements."),
            (AnnouncementPermissions.VIEW_ANNOUNCEMENTS.codename, "View announcements."),
        )

    def __repr__(self):
        return self.title


class Segment(models.Model):
    name = models.CharField(max_length=100, unique=True, null=False)
    details = models.TextField(max_length=512, blank=True, null=False)
    segment_id = models.CharField(max_length=100, unique=True, null=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        app_label = "notification"
        verbose_name = "segment"
        verbose_name_plural = "segments"
        ordering = ("-created",)

    def __repr__(self):
        return self.name


class NotificationManager(models.Manager):
    def create_notification(self, type, path, message, **extra_fields):
        options = NotificationType.get_keys()

        if not path:
            return ValueError("Path is Required")

        if not type:
            return ValueError("notification type  be empty")
        else:
            if type not in options:
                return ValueError("Not a valid notification type")

        notification = self.model(type=type, path=path, message=message)
        notification.save()

        recipients = extra_fields.pop("recipients", None)
        if recipients:
            notification.recipients.add(*recipients)

        groups = extra_fields.pop("groups", None)
        if groups:
            notification.groups.add(*groups)

        regions = extra_fields.pop("regions", None)
        if regions:
            notification.recipients.add(*regions)

        profiles = extra_fields.pop("profiles", None)
        if profiles:
            notification.profiles.add(*profiles)

        return notification


class Notification(models.Model):
    type = models.CharField(
        max_length=64,
        choices=NotificationType.CHOICES
    )

    recipients = models.ManyToManyField(User, related_name="user_notifications")
    groups = models.ManyToManyField(Group, related_name="group_notifications")
    regions = models.ManyToManyField(Region, related_name="region_notifications")
    profiles = models.ManyToManyField(UserProfile, related_name="profile_notifications")
    path = models.CharField(max_length=255, null=False)
    message = models.CharField(max_length=64, null=False, default="You have a notification")
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    objects = NotificationManager()

    class Meta:
        app_label = "notification"
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ("-created",)
        permissions = (
            (NotificationPermissions.MANAGE_NOTIFICATIONS.codename, "Manage notifications."),
            (NotificationPermissions.VIEW_NOTIFICATIONS.codename, "View notifications."),
        )

    def __repr__(self):
        return self.type


class NotificationMeta(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        app_label = "notification"
        verbose_name = "notification_meta"
        verbose_name_plural = "notifications_meta"
        unique_together = [['notification', 'recipient']]
        permissions = (
            (NotificationMetaPermissions.MANAGE_NOTIFICATION_METAS.codename, "Manage notifications."),
        )

    def __repr__(self):
        return self.notification.type


auditlog.register(Announcement)
auditlog.register(Segment)
auditlog.register(Notification)
auditlog.register(NotificationMeta)
