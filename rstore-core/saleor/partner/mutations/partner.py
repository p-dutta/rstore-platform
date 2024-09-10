import ast

from django.contrib.auth.models import Permission, Group
import graphene

from ....core import admin_connector
from ....core.permissions import PartnerPermissions, OrderPermissions
from ...core.mutations import BaseMutation, ModelMutation
from ...core.types import Upload
from ...core.types.common import PartnerError
from ...core.utils import validate_image_file
from ...account.mutations.account import AddressInput
from ...account.i18n import I18nMixin
from ....notification import NotificationType
from ....notification.models import Notification
from ....partner import models
from ....app import models as app_models


class CreatePartnerInput(graphene.InputObjectType):
    partner_name = graphene.String(description='Partner name', required=True)
    partner_id = graphene.String(description='Partner account code', required=True)
    email = graphene.String(description="Email address of the partner.", blank=False, required=True)
    call_center_number = graphene.String(description='Partner call center number', blank=True, required=False)
    address = AddressInput(description="Address", blank=True, required=False)
    description = graphene.String(description="Description text", blank=True, required=False)
    enabled = graphene.Boolean(description="Enabled status of the partner", required=True)
    consent_required = graphene.Boolean(description="User login consent required", required=True)
    standard_flow_enabled = graphene.Boolean(description="Status to enable standard flow", required=True)
    direct_access_grant_enabled = graphene.Boolean(description="Direct grant access status", required=True)
    implicit_flow_enabled = graphene.Boolean(description="Implicit flow status", required=True)
    full_scope_allowed = graphene.Boolean(description="Full scope allowed", required=True)
    root_url = graphene.String(description="Root url", required=True)
    default_scopes = graphene.List(description="Default scopes", of_type=graphene.String, required=True)
    public_client = graphene.Boolean(description="Public access client", required=True)
    service_account_enabled = graphene.Boolean(description="Service account status", required=True)
    redirect_urls = graphene.List(description="Redirect urls", of_type=graphene.String, required=True)
    base_url = graphene.String(description="Base url", blank=True, required=False)
    web_origins = graphene.List(description="Web Origins", of_type=graphene.String, required=True)


class UpdatePartnerInput(graphene.InputObjectType):
    partner_name = graphene.String(description='Partner name')
    email = graphene.String(description="Email address of the partner.")
    call_center_number = graphene.String(description='Partner call center number')
    address = AddressInput(description="Address")
    description = graphene.String(description="Description text")
    enabled = graphene.Boolean(description="Enabled status of the partner")
    consent_required = graphene.Boolean(description="User login consent required")
    standard_flow_enabled = graphene.Boolean(description="Status to enable standard flow")
    direct_access_grant_enabled = graphene.Boolean(description="Direct grant access status")
    implicit_flow_enabled = graphene.Boolean(description="Implicit flow status")
    full_scope_allowed = graphene.Boolean(description="Full scope allowed")
    root_url = graphene.String(description="Root url")
    default_scopes = graphene.List(description="Default scopes", of_type=graphene.String)
    service_account_enabled = graphene.Boolean(description="Service account status")
    public_client = graphene.Boolean(description="Public access client", required=False)
    redirect_urls = graphene.List(description="Redirect urls", of_type=graphene.String)
    base_url = graphene.String(description="Base url", blank=True)
    web_origins = graphene.List(description="Web Origins", of_type=graphene.String)


class CreatePartner(ModelMutation, I18nMixin):
    class Arguments:
        input = CreatePartnerInput(
            description="Fields required to create a partner.", required=True
        )

    class Meta:
        description = "Register a new partner."
        exclude = ["partner_oidc_id", "secret", "partner_app", "logo"]
        model = models.Partner
        permissions = (PartnerPermissions.MANAGE_PARTNERS,)
        error_type_class = PartnerError
        error_type_field = "partner_errors"

    @classmethod
    def mutate(cls, root, info, **data):
        response = super().mutate(root, info, **data)
        response.requires_confirmation = True
        return response

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        return super().clean_input(info, instance, data, input_cls=None)

    @classmethod
    def prepare_address(cls, cleaned_data, *args):
        address_form = cls.validate_address_form(cleaned_data["address"])
        return address_form.save()

    @classmethod
    def construct_instance(cls, instance, cleaned_data):
        if cleaned_data.get("address", None):
            cleaned_data["address"] = cls.prepare_address(cleaned_data, instance)

        return super().construct_instance(instance, cleaned_data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        data = {
            "clientId": instance.partner_id.lower(),
            "defaultClientScopes": ast.literal_eval(instance.default_scopes),
            "name": instance.partner_name,
            "publicClient": instance.public_client,
            "redirectUris": ast.literal_eval(instance.redirect_urls),
            "consentRequired": instance.consent_required,
            "directAccessGrantsEnabled": instance.direct_access_grant_enabled,
            "enabled": instance.enabled,
            "fullScopeAllowed": instance.full_scope_allowed,
            "implicitFlowEnabled": instance.implicit_flow_enabled,
            "rootUrl": instance.root_url,
            "serviceAccountsEnabled": instance.service_account_enabled,
            "standardFlowEnabled": instance.standard_flow_enabled
        }

        if instance.description:
            data["description"] = instance.description

        if cleaned_input.get("base_url"):
            data['baseUrl'] = cleaned_input["base_url"]

        if cleaned_input.get('web_origins'):
            data['webOrigins'] = ast.literal_eval(instance.web_origins)

        if cleaned_input.get("address"):
            instance.address = cleaned_input["address"]

        client_details = admin_connector.create_partner(data, instance.partner_id)

        if client_details:
            instance.partner_oidc_id = client_details['id']
            instance.secret = client_details['secret']

            permissions = Permission.objects.filter(codename__in=[OrderPermissions.MANAGE_ORDERS.codename,
                                                                  OrderPermissions.VIEW_ORDER.codename])
            app = app_models.App.objects.create(
                name=client_details['clientId'],
                is_active=True
            )
            for permission in permissions:
                app.permissions.add(permission)
            instance.partner_app = app
            app_models.AppToken.objects.create(
                app=app,
                name=client_details['clientId']
            )
            instance.save()
            agent = Group.objects.get(name='agent')
            groups = [agent]
            path = "/partners/"
            message = 'Partner ' + instance.partner_name + ' Added'
            Notification.objects.create_notification(type=NotificationType.PARTNER_ADDED, path=path,
                                                     groups=groups, message=message)
        else:
            raise ConnectionError('Something went wrong with identity provider')


class PartnerLogoUpdate(BaseMutation):
    class Arguments:
        id = graphene.ID(description="Id of the partner", required=True)
        image = Upload(
            required=True,
            description="Represents an image file in a multipart request.",
        )

    class Meta:
        description = "Update partner logo."
        permissions = (PartnerPermissions.MANAGE_PARTNERS,)
        error_type_class = PartnerError
        error_type_field = "partner_errors"

    @classmethod
    def perform_mutation(cls, _root, info, id, image):
        image_data = info.context.FILES.get(image)
        validate_image_file(image_data, "image")

        _model, partner_pk = graphene.Node.from_global_id(id)
        partner = models.Partner.objects.get(id=partner_pk)
        if partner.logo:
            partner.logo.delete_sized_images()
            partner.logo.delete()
        partner.logo = image_data
        partner.save()

        return PartnerLogoUpdate(partner)


class UpdatePartner(CreatePartner):
    class Arguments:
        id = graphene.ID(required=True, description="ID of the partner to update.")
        input = UpdatePartnerInput(
            description="Fields required to update the partner.", required=True
        )

    class Meta:
        description = "Updating a partner."
        model = models.Partner
        exclude = ["partner_id", "partner_oidc_id", "secret", "logo", "partner_app"]
        permissions = (PartnerPermissions.MANAGE_PARTNERS,)
        error_type_class = PartnerError
        error_type_field = "partner_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data["input"]["id"] = data["id"]
        return super().perform_mutation(root, info, **data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        data = {
            "redirectUris": ast.literal_eval(instance.redirect_urls),
            "consentRequired": instance.consent_required,
            "directAccessGrantsEnabled": instance.direct_access_grant_enabled,
            "enabled": instance.enabled,
            "fullScopeAllowed": instance.full_scope_allowed,
            "implicitFlowEnabled": instance.implicit_flow_enabled,
            "name": instance.partner_name,
            "publicClient": instance.public_client,
            "rootUrl": instance.root_url,
            "serviceAccountsEnabled": instance.service_account_enabled,
            "standardFlowEnabled": instance.standard_flow_enabled,
            "description": instance.description,
            "baseUrl": instance.base_url
        }

        if cleaned_input.get('web_origins') or instance.web_origins:
            data['webOrigins'] = ast.literal_eval(instance.web_origins)
        else:
            data['webOrigins'] = []

        if cleaned_input.get("address"):
            instance.address = cleaned_input["address"]

        oidc_id = instance.partner_oidc_id
        default_scopes_data = instance.default_scopes

        if default_scopes_data:
            existing_partner = models.Partner.objects.get(id=instance.id)
            existing_default_scopes = ast.literal_eval(existing_partner.default_scopes)
            all_client_scopes = admin_connector.get_client_scopes()

            for client_scope in all_client_scopes:
                scope_name = client_scope['name']
                scope_id = client_scope['id']
                if scope_name in existing_default_scopes and scope_name not in default_scopes_data:
                    admin_connector.delete_default_client_scope(oidc_id, scope_id)
                elif scope_name not in existing_default_scopes and scope_name in default_scopes_data:
                    admin_connector.add_default_client_scope(oidc_id, scope_id)

        client_details = admin_connector.update_partner(data, instance.partner_oidc_id)

        if client_details:
            models.Partner.objects.update_partner(instance, client_details)
        else:
            raise ConnectionError('Something went wrong with identity provider')
