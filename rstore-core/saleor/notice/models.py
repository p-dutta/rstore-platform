from auditlog.registry import auditlog
from datetime import date

from django.core.validators import FileExtensionValidator
from django.db import models
from django.contrib.postgres.fields import JSONField
from django.db.models import Q

from saleor.core.models import ModelWithMetadata
from saleor.core.permissions import NoticePermissions
from saleor.core.utils.json_serializer import CustomJsonEncoder
from saleor.notice import DocumentType


class NoticeQueryset(models.QuerySet):
    def active(self, date):
        return self.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=date),
            start_date__lte=date,
            is_active=True,
        )


class Notice(ModelWithMetadata):
    title = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=256, blank=True)
    groups = JSONField(default=dict, encoder=CustomJsonEncoder, blank=True)
    regions = JSONField(default=dict, encoder=CustomJsonEncoder, blank=True, null=True)
    note = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    start_date = models.DateField(default=date.today, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, blank=True)

    objects = NoticeQueryset.as_manager()

    class Meta:
        app_label = "notice"
        verbose_name = "notice"
        verbose_name_plural = "notices"
        ordering = ("end_date",)
        permissions = (
            (NoticePermissions.MANAGE_NOTICES.codename, "Manage notices."),
        )


class NoticeDocument(models.Model):
    notice = models.ForeignKey(
        Notice, blank=True, related_name="document", on_delete=models.CASCADE, null=True
    )
    mimetype = models.CharField(max_length=128, blank=True)
    content_file = models.FileField(
        upload_to="notices", blank=True,
        validators=[FileExtensionValidator(allowed_extensions=dict(DocumentType.CHOICES))]
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        app_label = "notice"
        verbose_name = "notice_document"
        verbose_name_plural = "notice_documents"
        ordering = ("pk",)
        permissions = (
            (NoticePermissions.MANAGE_NOTICES.codename, "Manage notices."),
        )


auditlog.register(Notice)
auditlog.register(NoticeDocument)
