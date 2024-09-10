from auditlog.registry import auditlog
from django.db import models
from django.db.models import Q

from .. import settings
from django.contrib.postgres.fields import JSONField
from saleor.core.utils.json_serializer import CustomJsonEncoder
from typing import Any
from softdelete.models import SoftDeleteModel

from ..account.models import User
from ..order.models import Order
from ..core.permissions import CommissionPermissions, RulePermissions
from . import CommissionStatus, RuleType, RuleCategory, CommissionCategory
from ..partner.models import Partner


class Rule(SoftDeleteModel):
    name = models.TextField(blank=False, null=False)
    type = models.CharField(
        blank=False, null=False,
        max_length=10,
        choices=RuleType.CHOICES,
    )
    category = models.CharField(
        blank=False, null=False,
        max_length=12,
        choices=RuleCategory.CHOICES,
    )
    commission_category = models.CharField(
        max_length=8,
        choices=CommissionCategory.CHOICES,
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        app_label = "commission"
        ordering = ("-updated",)
        permissions = (
            (RulePermissions.MANAGE_RULES.codename, "Manage rules"),
        )
        constraints = [
            models.UniqueConstraint(
                name="unique_name",
                fields=["name"],
                condition=Q(deleted_at=None)
            )
        ]

    def __str__(self):
        return "%s - %s" % (self.name, self.type)

    def get_latest_rule(self):
        return self.rule_histories.first()

    def get_rule_histories_pk_list(self):
        rule_histories = self.rule_histories.values_list('pk', flat=True)
        return list(rule_histories)


class RuleHistory(models.Model):
    rule = models.ForeignKey(
        Rule,
        related_name="rule_histories",
        on_delete=models.DO_NOTHING,
        null=True, blank=True
    )
    client_rule = JSONField(blank=True, default=dict, encoder=CustomJsonEncoder, null=True, editable=False)
    engine_rule = JSONField(blank=True, default=dict, encoder=CustomJsonEncoder, null=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        app_label = "commission"
        ordering = ("-updated",)
        permissions = (
            (RulePermissions.MANAGE_RULES.codename, "Manage rules"),
        )

    def save(self, *args, **kwargs):
        if self.pk is None:
            super(RuleHistory, self).save(*args, **kwargs)

    def get_value_from_client_rule(self, key: str, default: Any = None) -> Any:
        return self.client_rule.get(key, default)

    def get_value_from_engine_rule(self, key: str, default: Any = None) -> Any:
        return self.engine_rule.get(key, default)


class CommissionServiceMonth(models.Model):
    user = models.ForeignKey(
        User, related_name='commission_service_month', on_delete=models.SET_NULL, blank=True, null=True, default=None
    )
    service = models.ForeignKey(Partner, blank=True, null=True, related_name='commission_service_month', on_delete=models.SET_NULL)
    month = models.DateField(db_index=True, blank=False, unique=False)
    status = models.CharField(max_length=32, choices=CommissionStatus.CHOICES, default="pending")
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        unique_together = ('service', 'month', 'user')
        ordering = ('-month',)


class Commission(SoftDeleteModel):
    user = models.ForeignKey(
        User, related_name='commissions', on_delete=models.SET_NULL, blank=True, null=True, default=None
    )
    order = models.ForeignKey(
        Order, related_name='commissions', on_delete=models.SET_NULL, blank=True, null=True, default=None
    )

    rule_history = models.ForeignKey(
        RuleHistory, related_name='commissions', on_delete=models.SET_NULL, null=True, blank=True, default=None
    )

    amount = models.DecimalField(
        max_digits=settings.DEFAULT_MAX_DIGITS,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES,
        default=0,
    )
    commission_service_month = models.ForeignKey(
        CommissionServiceMonth, related_name="commissions", blank=True, null=True,
        on_delete=models.SET_NULL
    )

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        app_label = "commission"
        ordering = ("-updated",)
        permissions = (
            (CommissionPermissions.MANAGE_COMMISSIONS.codename, "Manage commissions."),
        )


class UserProfile(models.Model):
    name = models.TextField(unique=True, blank=False, null=False)
    total_orders = models.IntegerField(blank=False, null=False)
    total_transaction = models.IntegerField(blank=False, null=False)
    priority_order = models.IntegerField(unique=True, blank=False, null=False)
    period = models.IntegerField(default=3, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        app_label = "commission"
        ordering = ("-updated",)

    def __str__(self):
        return self.name


auditlog.register(Rule)
auditlog.register(UserProfile)
auditlog.register(Commission)
auditlog.register(RuleHistory)
