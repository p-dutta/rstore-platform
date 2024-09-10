import json

from auditlog.registry import auditlog
from django.core.validators import RegexValidator
from django.db import models
from versatileimagefield.fields import VersatileImageField

from ..account.models import Address
from ..app.models import App
from ..core.permissions import PartnerPermissions


class PartnerManager(models.Manager):

    @staticmethod
    def update_partner(partner, client_details):
        partner.partner_name = client_details.get('name', partner.partner_name)

        partner.description = client_details.get("description", partner.description)
        partner.enabled = client_details.get('enabled', partner.enabled)
        partner.consent_required = client_details.get('consentRequired', partner.consent_required)
        partner.standard_flow_enabled = client_details.get('standardFlowEnabled', partner.standard_flow_enabled)
        partner.direct_access_grant_enabled = client_details.get('directAccessGrantsEnabled',
                                                                 partner.direct_access_grant_enabled)
        partner.implicit_flow_enabled = client_details.get('implicitFlowEnabled', partner.implicit_flow_enabled)
        partner.full_scope_allowed = client_details.get('fullScopeAllowed', partner.full_scope_allowed)
        partner.root_url = client_details.get('rootUrl', partner.root_url)
        partner.default_scopes = json.dumps(client_details.get('defaultClientScopes'))
        partner.service_account_enabled = client_details.get('serviceAccountsEnabled',
                                                             partner.service_account_enabled)
        partner.redirect_urls = json.dumps(client_details.get('redirectUris')) \
            if client_details.get('redirectUris') else partner.redirect_urls
        partner.public_client = client_details.get('publicClient', partner.public_client)

        partner.save()


class Partner(models.Model):
    partner_name = models.CharField(max_length=255)
    partner_oidc_id = models.CharField(max_length=63, unique=True, null=False)
    partner_id = models.CharField(max_length=255, unique=True, null=False)
    call_center_number = models.CharField(max_length=11, blank=True, validators=[
        RegexValidator(regex='(^01[3-9][0-9]{8})|(^096[0-9]{8})|(^16[0-9]{3})$',
                       message='Please give correct phone number that is like 01*********, 16*** or 096********',
                       code='wrong_phone')])
    address = models.ForeignKey(
        Address, blank=True, related_name="partner_addresses", null=True, on_delete=models.CASCADE
    )
    email = models.EmailField(unique=True, null=True)
    description = models.TextField(default="", blank=True, null=True)
    enabled = models.BooleanField(default=False)
    consent_required = models.BooleanField(default=True)
    standard_flow_enabled = models.BooleanField(default=True)
    direct_access_grant_enabled = models.BooleanField(default=False)
    implicit_flow_enabled = models.BooleanField(default=False)
    full_scope_allowed = models.BooleanField(default=False)
    root_url = models.URLField(null=False)
    default_scopes = models.TextField(null=True)
    service_account_enabled = models.BooleanField(default=False)
    redirect_urls = models.TextField(null=False)
    secret = models.CharField(max_length=63, unique=True, null=False)
    logo = VersatileImageField(upload_to="partner-logos", blank=True, null=True)
    partner_app = models.ForeignKey(App, null=True, on_delete=models.SET_NULL)
    base_url = models.CharField(max_length=255, blank=True)
    web_origins = models.TextField(null=False, blank=True, default=[])
    public_client = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    objects = PartnerManager()

    class Meta:
        app_label = "partner"
        ordering = ("partner_name",)
        permissions = (
            (PartnerPermissions.MANAGE_PARTNERS.codename, "Manage partners."),
        )

    def __unicode__(self):
        return self.partner_id

    def __str__(self):
        return self.partner_name


auditlog.register(Partner)
