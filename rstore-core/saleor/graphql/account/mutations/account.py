import copy
import json
import ast
import os
from traceback import print_exc

import graphene
import re
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission as auth_permission
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from decimal import Decimal

from ...utils import check_if_attempted_from_valid_parent, get_child_group_names
from ....account import Qualification, EmployeeCount, ShopType, ShopSize, Gender, UserApprovalRequest, \
    UserApproval, GROUP_SEQUENCE, DocumentFileTag
from ....account.models import UserCorrectionRequest, UserRequest, get_hierarchy
from ....account.thumbnails import create_user_avatar_thumbnails
from ....account.sms import send_initial_submission_sms, send_kyc_submission_sms, send_rejection_sms, \
    send_initial_approval_sms, send_kyc_approval_sms, send_notification_cm_sms, send_notification_dco_sms
from ....core import admin_connector
from ...core.enums import PermissionEnum
from ...core.types import Upload
from ...core.utils import validate_image_file
from ...meta.mutations import UpdateMetadata
from ...meta.permissions import PUBLIC_META_PERMISSION_MAP
from ....account import emails, events as account_events, models, utils
from ....account.error_codes import AccountErrorCode, RequestErrorCode
from ....account.utils import create_jwt_token, decode_jwt_token
from ....checkout import AddressType
from ....core.permissions import AccountPermissions, get_permissions
from ....core.utils.url import validate_storefront_url
from ...account.enums import AddressTypeEnum
from ...account.types import Address, AddressInput, User, UserRequest, UserCorrection, Document, GroupChildTrxMap
from ...core.mutations import BaseMutation, ModelDeleteMutation, ModelMutation
from ...core.types.common import AccountError, RequestError, UserPermissionUpdateError
from ...meta.deprecated.mutations import UpdateMetaBaseMutation
from ...meta.deprecated.types import MetaInput
from ..i18n import I18nMixin
from .base import (
    INVALID_TOKEN,
    BaseAddressDelete,
    BaseAddressUpdate,
    BaseCustomerCreate,
)
from ....account.emails import (
    send_kyc_approve_email,
    send_kyc_reject_email,
    send_initial_approve_email,
    send_initial_reject_email
)

from keycloak.exceptions import KeycloakError

from ....notification import NotificationType
from ....notification.models import Notification
from ....notification.tasks import notify_on_registration_and_kyc, notify_on_registration_processed

PHONE_VALID_REGEX = r"^01[3-9][0-9]{8}$"
PHONE_VALIDATION_TEXT = "A valid Bangladeshi phone number is required"


class AccountRegisterInput(graphene.InputObjectType):
    email = graphene.String(description="Email address of the user.", required=True)
    phone = graphene.String(description="Phone number of user", required=True)
    password = graphene.String(description="Password of the user", required=True)
    district_id = graphene.ID(description="District id", required=True)
    thana_id = graphene.ID(description="Thana id", required=True)
    store_name = graphene.String(description="Store name", required=True)
    first_name = graphene.String(description="First mame", required=True)
    last_name = graphene.String(description="Last name", required=True)
    address = graphene.String(description="Address", required=True)
    redirect_url = graphene.String(
        description=(
            "Base of frontend URL that will be needed to create confirmation URL."
        ),
        required=False,
    )


class AccountRegister(ModelMutation):
    class Arguments:
        input = AccountRegisterInput(
            description="Fields required to create a user.", required=True
        )

    requires_confirmation = graphene.Boolean(
        description="Informs whether users need to confirm their email address."
    )

    class Meta:
        description = "Register a new user."
        exclude = ["password", "oidc_id", "district_id", "thana_id"]
        model = models.User
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def mutate(cls, root, info, **data):
        response = super().mutate(root, info, **data)
        response.requires_confirmation = settings.ENABLE_ACCOUNT_CONFIRMATION_BY_EMAIL
        return response

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        if not settings.ENABLE_ACCOUNT_CONFIRMATION_BY_EMAIL:
            return super().clean_input(info, instance, data, input_cls=None)
        elif not data.get("redirect_url"):
            raise ValidationError(
                {
                    "redirect_url": ValidationError(
                        "This field is required.", code=AccountErrorCode.REQUIRED
                    )
                }
            )

        try:
            validate_storefront_url(data["redirect_url"])
        except ValidationError as error:
            raise ValidationError(
                {
                    "redirect_url": ValidationError(
                        error.message, code=AccountErrorCode.INVALID
                    )
                }
            )

        password = data["password"]
        try:
            password_validation.validate_password(password, instance)
        except ValidationError as error:
            raise ValidationError({"password": error})
        return super().clean_input(info, instance, data, input_cls=None)

    @classmethod
    def save(cls, info, user, cleaned_input):
        phone = cleaned_input.get("phone")
        email = cleaned_input.get("email")
        password = cleaned_input.get("password")
        district = cleaned_input.get("district_id")
        thana = cleaned_input.get("thana_id")
        store = cleaned_input.get("store_name")
        first_name = cleaned_input.get("first_name", None)
        last_name = cleaned_input.get("last_name", None)
        address = cleaned_input.get("address")

        if not models.User.objects.email_available(email):
            raise ValidationError(
                {
                    "email": ValidationError(
                        "A user already exists with this email",
                        code=AccountErrorCode.UNIQUE
                    )
                }
            )
        if not models.User.objects.phone_available(phone):
            raise ValidationError(
                {
                    "phone": ValidationError(
                        "A user already exists with this mobile number",
                        code=AccountErrorCode.UNIQUE
                    )
                }
            )
        if len(address) > 50:
            raise ValidationError(
                {
                    "address": ValidationError(
                        "Address should be less than 50 character",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        dco = models.User.objects.get_dco(district.pk, thana.pk)
        if dco is None:
            raise ValidationError(
                {
                    "district_id": ValidationError(
                        "No DCO found for given district and/or thana",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        dcm = models.User.objects.get_dcm(district.pk, thana.pk)
        if dcm is None:
            raise ValidationError(
                {
                    "district_id": ValidationError(
                        "No DCM found for given district and/or thana",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        attributes = {
            "approval_status": UserApproval.INITIAL_SUBMISSION,
        }

        keycloak_user_id = admin_connector.create_user(
            phone_number=phone,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_enabled=False,
            password=password,
            temp_password=False,
            groups=["agent"],
            attributes=attributes
        )

        if keycloak_user_id:
            models.User.objects.create_user(
                phone=phone, email=email, is_active=False, password=password,
                district=district, thana=thana, store_name=store, temp_password=False,
                first_name=first_name, last_name=last_name, address=address, parent=dco, user=user,
                keycloak_user_id=keycloak_user_id)
        else:
            raise ValidationError(
                {
                    "": ValidationError(
                        "Something went wrong with identity provider",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        if settings.ENABLE_ACCOUNT_CONFIRMATION_BY_EMAIL:
            user.is_active = False
            user.save()
            emails.send_account_confirmation_email(user, cleaned_input["redirect_url"])
        else:
            user.save()
        user_rqst_ins = models.UserRequest.objects.create(user=user, assigned=dco)
        account_events.customer_account_created_event(user=user)
        info.context.plugins.customer_created(customer=user)

        send_initial_submission_sms.delay(phone)
        send_notification_dco_sms.delay(dco.phone, user.get_full_name(), Site.objects.get_current().domain)
        message = 'Agent Request Submitted'
        notify_on_registration_and_kyc.delay(
            message,
            NotificationType.AGENT_REQUEST_SUBMITTED,
            user_rqst_ins.pk,
            dco.pk
        )


class AgentInput(graphene.InputObjectType):
    assignee_id = graphene.ID(description=" Approver ID ")


class AgentRequestAssigneeUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(required=True, description="Agent Registration ID")
        input = AgentInput(
            required=True,
        )

    class Meta:
        description = "Updates the assignee_id "
        model = models.UserRequest
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def save(cls, info, instance, data):
        instance.assigned = data.get('assignee_id')
        instance.save()


class AccountInput(graphene.InputObjectType):
    first_name = graphene.String(description="Given name.")
    last_name = graphene.String(description="Family name.")
    default_billing_address = AddressInput(
        description="Billing address of the customer."
    )
    default_shipping_address = AddressInput(
        description="Shipping address of the customer."
    )


class AccountUpdate(BaseCustomerCreate):
    class Arguments:
        input = AccountInput(
            description="Fields required to update the account of the logged-in user.",
            required=True,
        )

    class Meta:
        description = "Updates the account of the logged-in user."
        exclude = ["password"]
        model = models.User
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def perform_mutation(cls, root, info, **data):
        user = info.context.user
        data["id"] = graphene.Node.to_global_id("User", user.id)
        return super().perform_mutation(root, info, **data)


class SubmitKycInput(graphene.InputObjectType):
    default_billing_address = AddressInput(
        description="Billing address of the customer."
    )
    default_shipping_address = AddressInput(
        description="Shipping address of the customer."
    )
    other_phone = graphene.String(description="Other phone number of user", required=False)
    dob = graphene.String(description="Date of birth of the user.", required=True)
    gender = graphene.String(description="Gender of user", required=True)
    location = graphene.String(description="Location", required=False)
    country = graphene.String(description="Country", required=True)
    postal_code = graphene.String(description="Postal code", required=True)
    no_of_employees = graphene.String(description="No of employee", required=True)
    laptop = graphene.Boolean(description="Laptop", required=True)
    smartphone = graphene.Boolean(description="Smartphone", required=True)
    printer = graphene.Boolean(description="Printer", required=True)
    biometric_device = graphene.Boolean(description="Biometric device", required=True)
    education = graphene.String(description="Education", required=True)
    nid = graphene.String(description="Nid", required=True)
    trade_license = graphene.String(description="Trade license", required=False)
    mfs_account_type = graphene.String(description="Mfs account", required=True)
    mfs_number = graphene.String(description="Mfs number", required=True)
    bank_account = graphene.Boolean(description="Bank account", required=True)
    bank_account_number = graphene.String(description="Bank account number", required=False)
    bank_account_name = graphene.String(description="Bank account name", required=False)
    bank_name = graphene.String(description="Bank name", required=False)
    branch_name = graphene.String(description="Branch name", required=False)
    monthly_income = graphene.String(description="Monthly income", required=True)
    tin = graphene.String(description="Tin", required=False)
    el_agent = graphene.Boolean(description="El agent", required=True)
    el_msisdn = graphene.String(description="El msisdn", required=False)
    sim_pos = graphene.Boolean(description="Sim pos", required=True)
    sim_pos_code = graphene.String(description="Sim pos code", required=False)
    shop_size = graphene.String(description="Shop size", required=True)
    shop_type = graphene.String(description="Shop type", required=True)
    toc_agree = graphene.Boolean(description="Toc agree", required=True)
    routing_number = graphene.String(description="Routing number", required=False)
    robicash_no = graphene.String(description="Robicash Number", required=False)


class SubmitKyc(BaseCustomerCreate):
    class Arguments:
        input = SubmitKycInput(
            description="Fields required to update the account of the logged-in user.",
            required=True,
        )

    class Meta:
        description = "Submits the KYC of the logged-in user."
        exclude = ["password"]
        model = models.User
        permission_map = PUBLIC_META_PERMISSION_MAP
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context, permissions=None):
        return context.user.has_perm(AccountPermissions.UPDATE_KYC) and \
               context.user.approval_status == UserApproval.PENDING_KYC

    @classmethod
    def clean_input(cls, info, instance, data):
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()

        if not instance.avatar:
            raise ValidationError(
                {
                    "profile_photo": ValidationError(
                        "Profile photo must exist to proceed",
                        code=AccountErrorCode.NOT_FOUND
                    )
                }
            )

        _check_image_exist(instance, "nid_front", "nid_front")
        _check_image_exist(instance, "nid_back", "nid_back")
        _check_image_exist(instance, "shop_inside", "shop_inside")
        _check_image_exist(instance, "shop_front", "shop_front")

        other_phone = data.get("other_phone")
        if other_phone:
            _validate_other_phone(other_phone)
        else:
            data.pop("other_phone", None)

        gender = data.get("gender")
        _validate_gender(gender)

        postal_code = data.get("postal_code")
        _validate_postal_code(postal_code)

        routing_number = data.get("routing_number")
        if routing_number:
            _validate_routing_number(routing_number)

        shop_size = data.get("shop_size")
        _validate_shop_size(shop_size)

        shop_type = data.get("shop_type")
        _validate_shop_type(shop_type)

        no_of_employees = data.get("no_of_employees")
        _validate_no_of_employees(no_of_employees)

        education = data.get("education")
        _validate_education(education)

        nid = data.get("nid")
        _validate_nid(nid)

        trade = data.get("trade_license")
        if trade:
            _validate_trade(trade)
            _check_image_exist(instance, "trade_license_photo", "trade_license_photo")

        mfs_number = data.get("mfs_number")
        _validate_mfs_number(mfs_number)

        bank = data.get("bank_account")
        if bank:
            bank_account_number = data.get("bank_account_number")
            if bank_account_number:
                _validate_bank_account_number(bank_account_number)

            bank_account_name = data.get("bank_account_name")
            if bank_account_name:
                _validate_at_least_2_characters("bank_account_name", bank_account_name)

            bank_name = data.get("bank_name")
            if bank_name:
                _validate_at_least_2_characters("bank_name", bank_name)

            branch_name = data.get("branch_name")
            if branch_name:
                _validate_at_least_2_characters("branch_name", branch_name)

        else:
            data.pop("bank_account_number", None)
            data.pop("bank_account_name", None)
            data.pop("bank_name", None)
            data.pop("branch_name", None)

        monthly_income = data.get("monthly_income")
        _validate_monthly_income(monthly_income)

        tin = data.get("tin")
        if tin:
            _validate_tin(tin)

        el_agent = data.get("el_agent")
        if el_agent:
            el_msisdn = data.get("el_msisdn")
            if not el_msisdn:
                raise ValidationError(
                    {
                        "el_msisdn": ValidationError(
                            f"EL MSISDN is required",
                            code=AccountErrorCode.INVALID
                        )
                    }
                )
            _validate_phone_number("el_msisdn", el_msisdn)
        else:
            data.pop("el_msisdn", None)

        sim_pos = data.get("sim_pos")
        if not sim_pos:
            data.pop("sim_pos_code", None)

        robicash_no = data.get("robicash_no")
        if robicash_no:
            _validate_phone_number("robicash_no", robicash_no)
        else:
            data.pop("robicash_no", None)

        return super().clean_input(info, instance, data)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        user = info.context.user
        data["id"] = graphene.Node.to_global_id("User", user.id)
        return super().perform_mutation(root, info, **data)

    @classmethod
    def clean_system_file(cls, user, file_tag):
        files = user.documents.filter(file_tag=file_tag)
        if files:
            for file in files:
                file.content_file.delete()
            files.delete()

    @classmethod
    def save(cls, info, instance, cleaned_input):
        cm = models.User.objects.get_cm_by_region(instance.regions.first())
        if cm is None:
            raise ValidationError(
                {
                    "": ValidationError(
                        "No CM found for given district and thana",
                        code=AccountErrorCode.INVALID
                    )
                }
            )
        instance.approval_status = UserApproval.PENDING_APPROVAL

        location = cleaned_input.pop("location", None)
        if location is not None:
            location = json.dumps(ast.literal_eval(location))
            cleaned_input["location"] = location

        address_fields = ["postal_code", "country"]
        not_meta_fields = ["email"]
        not_meta_fields.extend(address_fields)
        meta_items = dict([(x, y) for x, y in cleaned_input.items() if x not in not_meta_fields])
        data = {"id": graphene.Node.to_global_id("User", instance.pk)}
        meta_instance = UpdateMetadata.get_instance(info, **data)
        metadata = meta_instance.metadata
        meta_items["store_name"] = metadata["store_name"]

        user_address = instance.addresses.last()
        address_items = dict([(x, y) for x, y in cleaned_input.items() if x in address_fields])
        user_address.postal_code = address_items["postal_code"]
        user_address.country = address_items["country"]
        user_address.save()

        address_items["first_name"] = instance.first_name
        address_items["last_name"] = instance.last_name
        address_items["address"] = user_address.street_address_1
        address_items["district"] = user_address.city
        address_items["thana"] = user_address.city_area
        address_items["phone"] = instance.phone

        # in ideal case user will have single mapping with address but
        # if somehow they have multiple mapping then we need to update
        if instance.default_shipping_address_id is not user_address.id:
            instance.default_shipping_address = user_address
        if instance.default_billing_address is not user_address.id:
            instance.default_billing_address = user_address

        instance_region = instance.regions.first()

        dco = models.User.objects.get_dco_by_region(instance_region)
        dcm = models.User.objects.get_dcm_by_region(instance_region)
        dco_details = {
            "name": dco.first_name + ' ' + dco.last_name,
            "phone": dco.phone,
            "email": dco.email
        }
        dcm_details = {
            "name": dcm.first_name + ' ' + dcm.last_name,
            "phone": dcm.phone,
            "email": dcm.email
        }

        attributes = copy.deepcopy(meta_items)
        attributes["address"] = json.dumps(address_items)
        attributes["phone_number"] = instance.phone
        attributes["approval_status"] = instance.approval_status
        attributes["dco"] = json.dumps(dco_details)
        attributes["dcm"] = json.dumps(dcm_details)

        keycloak_user_params = {
            "firstName": instance.first_name,
            "lastName": instance.last_name,
            "email": instance.email,
            "attributes": attributes,
        }
        if instance.oidc_id:
            try:
                admin_connector.update_user(
                    user_id=instance.oidc_id, params=keycloak_user_params
                )
            except Exception:
                raise ValidationError(
                    {
                        "": ValidationError(
                            "Something went wrong with identity provider",
                            code=AccountErrorCode.INVALID
                        )
                    }
                )
        instance.save()
        user_rqst_ins = models.UserRequest.objects.create(user=instance, assigned=cm)

        if meta_instance:
            meta_instance.store_value_in_metadata(items=meta_items)
            meta_instance.save(update_fields=["metadata"])

        send_kyc_submission_sms.delay(instance.phone)
        send_notification_cm_sms.delay(cm.phone, instance.get_full_name(), Site.objects.get_current().domain)
        message = 'KYC Submitted'
        notify_on_registration_and_kyc.delay(
            message,
            NotificationType.KYC_SUBMITTED,
            user_rqst_ins.pk,
            cm.pk
        )


class SubmitUserCorrectionInput(graphene.InputObjectType):
    agent = graphene.ID(description="ID of agent to be modified", required=True)
    first_name = graphene.String(description="User first name", required=False)
    last_name = graphene.String(description="User last name", required=False)
    email = graphene.String(description="User email", required=False)
    note = graphene.String(description="User note", required=False)

    other_phone = graphene.String(description="Other phone number of user", required=False)
    dob = graphene.String(description="Date of birth of the user.", required=False)
    gender = graphene.String(description="Gender of user", required=False)
    location = graphene.String(description="Location", required=False)
    country = graphene.String(description="Country", required=False)
    postal_code = graphene.String(description="Postal code", required=False)
    no_of_employees = graphene.String(description="No of employee", required=False)
    laptop = graphene.Boolean(description="Laptop", required=False)
    smartphone = graphene.Boolean(description="Smartphone", required=False)
    printer = graphene.Boolean(description="Printer", required=False)
    biometric_device = graphene.Boolean(description="Biometric device", required=False)
    education = graphene.String(description="Education", required=False)
    nid = graphene.String(description="Nid", required=False)
    trade_license = graphene.String(description="Trade license", required=False)
    mfs_account_type = graphene.String(description="Mfs account", required=False)
    mfs_number = graphene.String(description="Mfs number", required=False)
    bank_account = graphene.Boolean(description="Bank account", required=False)
    bank_account_number = graphene.String(description="Bank account number", required=False)
    bank_account_name = graphene.String(description="Bank account name", required=False)
    bank_name = graphene.String(description="Bank name", required=False)
    branch_name = graphene.String(description="Branch name", required=False)
    monthly_income = graphene.String(description="Monthly income", required=False)
    tin = graphene.String(description="Tin", required=False)
    el_agent = graphene.Boolean(description="El agent", required=False)
    el_msisdn = graphene.String(description="El msisdn", required=False)
    sim_pos = graphene.Boolean(description="Sim pos", required=False)
    sim_pos_code = graphene.String(description="Sim pos code", required=False)
    store_name = graphene.String(description="Store name", required=False)
    street_address_1 = graphene.String(description="Store address", required=False)
    shop_size = graphene.String(description="Shop size", required=False)
    shop_type = graphene.String(description="Shop type", required=False)
    toc_agree = graphene.Boolean(description="Toc agree", required=False)
    routing_number = graphene.String(description="Routing number", required=False)
    documents = graphene.List(of_type=graphene.NonNull(graphene.ID), description="Document ids", required=False)

    agent_banking_number = graphene.String(description="Agent banking number information", required=False)
    agent_banking = graphene.Boolean(description="Agent banking information", required=False)
    bdtickets = graphene.Boolean(description="Bdtickets information", required=False)
    robicash = graphene.Boolean(description="Robicash information", required=False)
    robicash_no = graphene.String(description="Robicash Number", required=False)
    insurance = graphene.Boolean(description="Insurance information", required=False)
    collection_point = graphene.Boolean(description="Collection point information", required=False)
    device_accessories = graphene.Boolean(description="Device accessories information", required=False)
    iot_smart_product = graphene.Boolean(description="IOT smart product information", required=False)
    payment_collection = graphene.Boolean(description="Payment collection information", required=False)


class SubmitUserCorrection(ModelMutation):
    class Arguments:
        input = SubmitUserCorrectionInput(
            description="Fields required for request correction of an user.",
            required=True,
        )

    class Meta:
        description = "Submits user correction request for an agent by dco/dcm."
        model = models.UserCorrection
        permission_map = (AccountPermissions.REQUEST_USERCORRECTION,)
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context, permissions=None):
        return context.user.has_perm(AccountPermissions.REQUEST_USERCORRECTION)

    @classmethod
    def clean_input(cls, info, instance, data):
        try:
            agent_user = cls.get_node_or_error(info, data.get("agent"))
            data.pop("agent")
        except Exception:
            raise ValidationError(
                {
                    "agent": ValidationError(
                        f"Please check given agent id.",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        if not agent_user.is_active:
            raise ValidationError(
                {
                    "agent": ValidationError(
                        f"Given user is not active.",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        if not agent_user.approval_status == "approved":
            raise ValidationError(
                {
                    "agent": ValidationError(
                        f"Given user is not approved to use this system.",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        if UserCorrectionRequest.objects.filter(user=agent_user, status="pending").exists():
            raise ValidationError(
                {
                    "agent": ValidationError(
                        f"Given user has existing pending request.",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        location = data.get("location", None)
        if location is not None:
            location = ast.literal_eval(location)
            _validate_location(location)

        remove_fields = []
        data["first_name"] = data.get("first_name", agent_user.first_name)
        data["last_name"] = data.get("last_name", agent_user.last_name)
        data["email"] = data.get("email", agent_user.email)
        data["note"] = data.get("note", agent_user.note)
        data["country"] = data.get("country", "BD")

        if data["email"] != agent_user.email:
            _validate_required("email", data["email"])
            _validate_email(data["email"])
        else:
            data.pop("email")

        if data.get('el_agent', agent_user.metadata.get('el_agent', False)):
            _validate_required('el_msisdn', data.get('el_msisdn', agent_user.metadata.get('el_msisdn', False)))
        else:
            data.pop('el_msisdn', False)
            remove_fields.append('el_msisdn')

        if data.get('robicash', agent_user.metadata.get('robicash', False)):
            _validate_required('robicash_no', data.get('robicash_no', agent_user.metadata.get('robicash_no', False)))
        else:
            data.pop('robicash_no', None)
            remove_fields.append('robicash_no')

        if data.get('sim_pos', agent_user.metadata.get('sim_pos', False)):
            _validate_required('sim_pos_code', data.get('sim_pos_code', agent_user.metadata.get('sim_pos_code', False)))
        else:
            data.pop('sim_pos_code', None)
            remove_fields.append('sim_pos_code')

        if data.get('agent_banking', agent_user.metadata.get('agent_banking', False)):
            _validate_required('agent_banking_number',
                               data.get('agent_banking_number', agent_user.metadata.get('agent_banking_number', False)))
        else:
            data.pop('agent_banking_number', None)
            remove_fields.append('agent_banking_number')

        if data.get('bank_account', agent_user.metadata.get('bank_account', False)):
            _validate_required('bank_account_number',
                               data.get('bank_account_number', agent_user.metadata.get('bank_account_number', False)))
            _validate_required('bank_account_name',
                               data.get('bank_account_name', agent_user.metadata.get('bank_account_name', False)))
            _validate_required('bank_name', data.get('bank_name', agent_user.metadata.get('bank_name', False)))
            _validate_required('branch_name', data.get('branch_name', agent_user.metadata.get('branch_name', False)))
            _validate_required('routing_number',
                               data.get('routing_number', agent_user.metadata.get('routing_number', False)))
        else:
            data.pop('bank_account_number', None)
            remove_fields.append('bank_account_number')

            data.pop('bank_account_name', None)
            remove_fields.append('bank_account_name')

            data.pop('bank_name', None)
            remove_fields.append('bank_name')

            data.pop('branch_name', None)
            remove_fields.append('branch_name')

            data.pop('routing_number', None)
            remove_fields.append('routing_number')

        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
            method = f"_validate_{key}('{data[key]}')"
            try:
                eval(method)
            except NameError:
                pass
            except SyntaxError:
                pass

        cleaned_input = super().clean_input(info, instance, data)
        cleaned_input["phone"] = agent_user.phone
        cleaned_input["agent"] = agent_user
        cleaned_input["removed"] = remove_fields
        cleaned_input["email"] = data.get("email", agent_user.email)

        return cleaned_input

    @classmethod
    def perform_mutation(cls, root, info, **data):
        return super().perform_mutation(root, info, **data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        instance.save()
        documents = cleaned_input.get("documents", None)
        if documents:
            for document in documents:
                if document.file_tag == "avatar":
                    instance.avatar.save(os.path.basename(document.content_file.path),
                                         document.content_file.file.file)
                else:
                    instance.documents.add(document)

        agent = cleaned_input["agent"]
        cm = models.User.objects.get_cm_by_region(agent.regions.first())
        if cm is None:
            raise ValidationError(
                {
                    "": ValidationError(
                        "No CM found for given district and thana",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        location = cleaned_input.pop("location", None)

        if location is not None:
            location = json.dumps(ast.literal_eval(location))
            cleaned_input["location"] = location

        address_fields = ["postal_code", "country", "phone", "first_name", "last_name", "street_address_1"]
        not_meta_fields = ["email", "documents", "agent", "note"]
        not_meta_fields.extend(address_fields)
        meta_items = dict([(x, y) for x, y in cleaned_input.items() if x not in not_meta_fields])
        address_items = dict([(x, y) for x, y in cleaned_input.items() if x in address_fields])

        address_items["city"] = agent.regions.first().district.name
        address_items["city_area"] = agent.regions.first().thana.name
        store_name = cleaned_input.get("store_name", None)
        if store_name:
            address_items["company_name"] = store_name

        instance.addresses.add(models.Address.objects.create(**address_items))
        instance.metadata = meta_items

        super().save(info, instance, cleaned_input)

        try:
            user_correction = models.UserCorrectionRequest.objects.create(user=agent, user_correction=instance,
                                                                          assigned=cm)
        except Exception:
            print_exc()
            raise

        message = 'User Correction Request Submitted for : ' + agent.first_name
        path = '/user-correction-requests/' + str(
            graphene.Node.to_global_id("UserCorrectionRequest", user_correction.id))
        Notification.objects.create_notification(type=NotificationType.USER_CORRECTION_REQUEST_SUBMITTED,
                                                 recipients=[cm], message=message, path=path)

        send_notification_cm_sms.delay(cm.phone, agent.get_full_name(), Site.objects.get_current().domain)


class SaveKycInput(graphene.InputObjectType):
    other_phone = graphene.String(description="Other phone number of user", required=False, blank=True)
    dob = graphene.String(description="Date of birth of the user.", required=False, blank=True)
    gender = graphene.String(description="Gender of user", required=False, blank=True)
    location = graphene.String(description="Location", required=False, blank=True)
    country = graphene.String(description="Country", required=False, blank=True)
    postal_code = graphene.String(description="Postal code", required=False, blank=True)
    no_of_employees = graphene.String(description="No of employee", required=False, blank=True)
    laptop = graphene.Boolean(description="Laptop", required=False, blank=True)
    smartphone = graphene.Boolean(description="Smartphone", required=False, blank=True)
    printer = graphene.Boolean(description="Printer", required=False, blank=True)
    biometric_device = graphene.Boolean(description="Biometric device", required=False, blank=True)
    education = graphene.String(description="Education", required=False, blank=True)
    nid = graphene.String(description="Nid", required=False, blank=True)
    trade_license = graphene.String(description="Trade license", required=False)
    mfs_account_type = graphene.String(description="Mfs account", required=False)
    mfs_number = graphene.String(description="Mfs number", required=False)
    bank_account = graphene.Boolean(description="Bank account", required=False)
    bank_account_number = graphene.String(description="Bank account number", required=False)
    bank_account_name = graphene.String(description="Bank account name", required=False)
    bank_name = graphene.String(description="Bank name", required=False)
    branch_name = graphene.String(description="Branch name", required=False)
    monthly_income = graphene.String(description="Monthly income", required=False)
    tin = graphene.String(description="Tin", required=False)
    el_agent = graphene.Boolean(description="El agent", required=False)
    el_msisdn = graphene.String(description="El msisdn", required=False)
    sim_pos = graphene.Boolean(description="Sim pos", required=False)
    sim_pos_code = graphene.String(description="Sim pos code", required=False)
    shop_size = graphene.String(description="Shop size", required=False)
    shop_type = graphene.String(description="Shop type", required=False)
    toc_agree = graphene.Boolean(description="Toc agree", required=False)
    routing_number = graphene.String(description="Routing number", required=False)
    robicash_no = graphene.String(description="Robicash Number", required=False)


class SaveKyc(BaseCustomerCreate):
    class Arguments:
        input = SaveKycInput(
            description="Fields required to save draft of the account of  logged-in user.",
            required=True,
        )

    class Meta:
        description = "Saves the KYC of the logged-in user as draft."
        exclude = ["password"]
        model = models.User
        permission_map = PUBLIC_META_PERMISSION_MAP
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context, permissions=None):
        return context.user.has_perm(AccountPermissions.UPDATE_KYC) and \
               context.user.approval_status == UserApproval.PENDING_KYC

    @classmethod
    def clean_input(cls, info, instance, data):
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = v.strip()

        other_phone = data.get("other_phone")
        if other_phone:
            _validate_other_phone(other_phone)
        else:
            data.pop("other_phone", None)

        gender = data.get("gender")
        if gender:
            _validate_gender(gender)
        else:
            data.pop("gender", None)

        postal_code = data.get("postal_code")
        if postal_code:
            _validate_postal_code(postal_code)
        else:
            data.pop("postal_code", None)

        routing_number = data.get("routing_number")
        if routing_number:
            _validate_routing_number(routing_number)
        else:
            data.pop("routing_number", None)

        shop_size = data.get("shop_size")
        if shop_size:
            _validate_shop_size(shop_size)
        else:
            data.pop("shop_size", None)

        shop_type = data.get("shop_type")
        if shop_type:
            _validate_shop_type(shop_type)
        else:
            data.pop("shop_type", None)

        no_of_employees = data.get("no_of_employees")
        if no_of_employees:
            _validate_no_of_employees(no_of_employees)
        else:
            data.pop("no_of_employees", None)

        education = data.get("education")
        if education:
            _validate_education(education)
        else:
            data.pop("education", None)

        nid = data.get("nid")
        if nid:
            _validate_nid(nid)
        else:
            data.pop("nid", None)

        trade = data.get("trade_license")
        if trade:
            _validate_trade(trade)
        else:
            data.pop("trade_license", None)

        mfs_number = data.get("mfs_number")
        if mfs_number:
            _validate_mfs_number(mfs_number)
        else:
            data.pop("mfs_number", None)

        bank_account_number = data.get("bank_account_number")
        if bank_account_number:
            _validate_bank_account_number(bank_account_number)
        else:
            data.pop("bank_account_number", None)

        bank_account_name = data.get("bank_account_name")
        if bank_account_name:
            _validate_at_least_2_characters("bank_account_name", bank_account_name)
        else:
            data.pop("bank_account_name", None)

        bank_name = data.get("bank_name")
        if bank_name:
            _validate_at_least_2_characters("bank_name", bank_name)
        else:
            data.pop("bank_name", None)

        branch_name = data.get("branch_name")
        if branch_name:
            _validate_at_least_2_characters("branch_name", branch_name)
        else:
            data.pop("branch_name", None)

        monthly_income = data.get("monthly_income")
        if monthly_income:
            _validate_monthly_income(monthly_income)
        else:
            data.pop("monthly_income", None)

        tin = data.get("tin")
        if tin:
            _validate_tin(tin)
        else:
            data.pop("tin", None)

        el_msisdn = data.get("el_msisdn")
        if el_msisdn:
            _validate_phone_number("el_msisdn", el_msisdn)
        else:
            data.pop("el_msisdn", None)

        robicash_no = data.get("robicash_no")
        if robicash_no:
            _validate_phone_number("robicash_no", robicash_no)
        else:
            data.pop("robicash_no", None)

        return super().clean_input(info, instance, data)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        user = info.context.user
        data["id"] = graphene.Node.to_global_id("User", user.id)
        return super().perform_mutation(root, info, **data)

    @classmethod
    def save(cls, info, instance, cleaned_input):

        location = cleaned_input.pop("location", None)
        if location is not None:
            location = json.dumps(ast.literal_eval(location))
            cleaned_input["location"] = location

        user_address = instance.addresses.last()
        user_address.postal_code = cleaned_input.get("postal_code", "")
        user_address.country = cleaned_input.get("country", "")
        user_address.save()

        address_fields = ["postal_code", "country"]

        meta_items = dict()
        meta_items["store_name"] = instance.metadata.get("store_name", "")
        meta_items.update(dict([(x, y) for x, y in cleaned_input.items() if x not in address_fields]))

        data = {"id": graphene.Node.to_global_id("User", instance.pk)}

        meta_instance = UpdateMetadata.get_instance(info, **data)

        if meta_instance:
            meta_instance.store_value_in_metadata(items=meta_items)
            meta_instance.save(update_fields=["metadata"])

        instance.metadata = meta_items
        instance.save()


class RequestApprovalInput(graphene.InputObjectType):
    request_id = graphene.ID(description="User request id", required=True)
    is_approved = graphene.Boolean(description="Approved/Rejected from dco", required=True)
    rejection_reason = graphene.String(description="Why user is rejected", required=False)


class RequestApproval(ModelMutation):
    class Arguments:
        input = RequestApprovalInput(
            required=True,
            description="Agent id and rejection reason is required"
        )

    class Meta:
        description = (
            "Change approval status of an agent to approved or rejected by dco"
        )
        model = models.UserRequest
        exclude = ["user", "assigned"]
        permissions = (AccountPermissions.MANAGE_REQUESTS,)
        error_type_class = RequestError
        error_type_field = "request_errors"

    @classmethod
    def check_permissions(cls, context, permissions=None):
        return context.user.has_perm(AccountPermissions.MANAGE_REQUESTS)

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        is_approved = data.get("is_approved")

        if not is_approved:
            reject_reason = data.get("rejection_reason")
            if not reject_reason:
                raise ValidationError(
                    {
                        "rejection_reason": ValidationError(
                            "Rejection reason is required", code=RequestErrorCode.REJECTION_TEXT
                        )
                    }
                )

        user_request = models.UserRequest.objects.get(id=graphene.Node.from_global_id(data["request_id"])[-1])
        if user_request.assigned_id != info.context.user.pk:
            raise ValidationError(
                {
                    "assigned": ValidationError(
                        "You are not assigned to process this request", code=RequestErrorCode.WRONG_APPROVER
                    )
                }
            )

        if user_request.status == UserApproval.REJECTED:
            raise ValidationError(
                {
                    "status": ValidationError(
                        "The selected request can not be modified", code=RequestErrorCode.REJECTED_REQUEST
                    )
                }
            )
        return super().clean_input(info, instance, data)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data["id"] = data["input"]["request_id"]
        return super().perform_mutation(root, info, **data)

    @classmethod
    def update_status_keycloak(cls, approval_status, oidc_id, enabled, rejection_reason=None):
        key_user = admin_connector.get_user_by_id(user_id=oidc_id)
        attributes = copy.deepcopy(key_user["attributes"])
        attributes["approval_status"] = approval_status
        if approval_status == UserApproval.REJECTED:
            attributes["rejection_reason"] = rejection_reason

        admin_connector.update_user(
            user_id=oidc_id, params={"enabled": enabled, "attributes": attributes}
        )

    @classmethod
    def delete_user_from_keycloak(cls, oidc_id):
        admin_connector.delete_user(user_id=oidc_id)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        agent = models.User.objects.get(id=instance.user_id)
        existing_approval_status = agent.approval_status
        assigned_user_email = instance.assigned.email
        approved = cleaned_input["is_approved"]

        if agent.oidc_id:
            updated_approval_state = UserApproval.INITIAL_SUBMISSION
            active = False
            delete_user = False
            if approved:
                request_status = UserApprovalRequest.APPROVED
                rejection_reason = None
                if existing_approval_status == UserApproval.INITIAL_SUBMISSION:
                    updated_approval_state = UserApproval.PENDING_KYC
                    active = True
                elif existing_approval_status == UserApproval.PENDING_APPROVAL:
                    updated_approval_state = UserApproval.APPROVED
                    active = True
            else:
                request_status = UserApprovalRequest.REJECTED
                rejection_reason = cleaned_input.get("rejection_reason", None)
                if existing_approval_status == UserApproval.INITIAL_SUBMISSION:
                    updated_approval_state = UserApproval.REJECTED
                    active = False
                    delete_user = True
                elif existing_approval_status == UserApproval.PENDING_APPROVAL:
                    updated_approval_state = UserApproval.PENDING_KYC
                    active = True

            instance.status = request_status
            instance.rejection_reason = rejection_reason
            instance.save()

            agent.approval_status = updated_approval_state
            agent.is_active = active
            agent.save()

            if delete_user:
                cls.delete_user_from_keycloak(agent.oidc_id)
                agent.delete()
            else:
                cls.update_status_keycloak(updated_approval_state, agent.oidc_id, active,
                                           cleaned_input.get("rejection_reason", None))

            if updated_approval_state == UserApproval.REJECTED:
                if existing_approval_status == UserApproval.PENDING_APPROVAL:
                    send_kyc_reject_email(assigned_user_email, (agent.email,), instance, rejection_reason)
                elif agent.email:
                    send_initial_reject_email(assigned_user_email, (agent.email,), instance, rejection_reason)
                send_rejection_sms.delay(agent.phone, rejection_reason)

            elif updated_approval_state == UserApproval.PENDING_KYC:
                if agent.email:
                    send_initial_approve_email(assigned_user_email, (agent.email,), instance)
                send_initial_approval_sms.delay(agent.phone, Site.objects.get_current().domain)
                message = 'Agent Request Processed'
                notify_on_registration_processed.delay(
                    message,
                    NotificationType.AGENT_REQUEST_PROCESSED,
                    instance.user.pk
                )
            elif updated_approval_state == UserApproval.APPROVED:
                send_kyc_approve_email(assigned_user_email, (agent.email,), instance)
                send_kyc_approval_sms.delay(agent.phone, Site.objects.get_current().domain)
                message = 'KYC Processed'
                notify_on_registration_processed.delay(
                    message,
                    NotificationType.KYC_PROCESSED,
                    instance.user.pk
                )


class ProcessUserCorrectionRequest(ModelMutation):
    class Arguments:
        input = RequestApprovalInput(
            required=True,
            description="User correction request id and rejection reason is required"
        )

    class Meta:
        description = (
            "Change approval status of a DCO/DCM to approved or rejected by CM"
        )
        model = models.UserCorrectionRequest
        permissions = (AccountPermissions.PROCESS_USERCORRECTION,)
        error_type_class = RequestError
        error_type_field = "request_errors"

    @classmethod
    def check_permissions(cls, context, permissions=None):
        return context.user.has_perm(AccountPermissions.PROCESS_USERCORRECTION)

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        is_approved = data.get("is_approved")
        if not is_approved:
            reject_reason = data.get("rejection_reason")
            if not reject_reason:
                raise ValidationError(
                    {
                        "rejection_reason": ValidationError(
                            "Rejection reason is required", code=RequestErrorCode.REJECTION_TEXT
                        )
                    }
                )

        user_request = models.UserCorrectionRequest.objects.get(id=graphene.Node.from_global_id(data["request_id"])[-1])
        if user_request.assigned_id != info.context.user.pk:
            raise ValidationError(
                {
                    "assigned": ValidationError(
                        "You are not assigned to process this request", code=RequestErrorCode.WRONG_APPROVER
                    )
                }
            )

        return super().clean_input(info, instance, data)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data["id"] = data["input"]["request_id"]
        return super().perform_mutation(root, info, **data)

    @classmethod
    def update_agent_info_keycloak(cls, oidc_id, user_address, remove_metas, user_params=None):
        key_user = admin_connector.get_user_by_id(user_id=oidc_id)
        key_attributes = copy.deepcopy(key_user["attributes"])

        address = {}
        if user_address:
            for key, value in user_address.items():
                if value:
                    if key == "street_address_1":
                        address["address"] = value
                    elif key == "city":
                        address["district"] = value
                    elif key == "city_area":
                        address["thana"] = value
                    else:
                        address[key] = value

        if remove_metas:
            for item in remove_metas:
                if key_attributes.get(item, False):
                    key_attributes.pop(item)

        key_attributes["address"] = json.dumps(address)
        key_attributes.update(user_params["attributes"])
        user_params["attributes"] = key_attributes

        try:
            admin_connector.update_user(
                user_id=oidc_id, params=user_params
            )
        except Exception:
            raise ValidationError(
                {
                    "": ValidationError(
                        "Something went wrong with identity provider",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

    @classmethod
    def save(cls, info, instance, cleaned_input):
        agent = models.User.objects.get(id=instance.user_id)
        correction = models.UserCorrection.objects.get(id=instance.user_correction_id)
        approved = cleaned_input["is_approved"]

        if approved:
            request_status = UserApprovalRequest.APPROVED
            rejection_reason = None
            remove_fields = correction.metadata.pop("removed", None)
            remove_keycloak_meta = []

            if remove_fields:
                for item in remove_fields:
                    if agent.metadata.get(item, False):
                        agent.metadata.pop(item)
                        remove_keycloak_meta.append(item)

            if correction.metadata:
                agent.metadata.update(correction.metadata)
            try:
                correction_address = correction.addresses.first().as_data()
                correction_address = {k: v for k, v in correction_address.items() if v}
                models.Address.objects.filter(id=agent.addresses.first().id).update(**correction_address)
            except AttributeError:
                pass

            agent.email = correction.email if correction.email else agent.email
            agent.first_name = correction.first_name if correction.first_name else agent.first_name
            agent.last_name = correction.last_name if correction.last_name else agent.last_name
            agent.note = correction.note if correction.note else agent.note
            if correction.avatar:
                agent.avatar.delete_sized_images()
                agent.avatar.delete()
                agent.avatar = correction.avatar
                create_user_avatar_thumbnails.delay(user_id=agent.pk)

            documents = correction.documents.all()
            if documents:
                for document in documents:
                    if document.file_tag != "avatar":
                        files = agent.documents.filter(file_tag=document.file_tag)
                        for file in files:
                            if file:
                                file.content_file.delete()
                                file.delete()
                        agent.documents.add(document)
            address_items = agent.addresses.first().as_data()
            attributes = copy.deepcopy(agent.metadata)
            keycloak_user_params = {
                "firstName": agent.first_name,
                "lastName": agent.last_name,
                "email": agent.email,
                "attributes": attributes,
            }
            cls.update_agent_info_keycloak(agent.oidc_id, address_items, remove_keycloak_meta,
                                           user_params=keycloak_user_params)
            agent.save()
        else:
            request_status = UserApprovalRequest.REJECTED
            rejection_reason = cleaned_input.get("rejection_reason", None)

        instance.status = request_status
        instance.rejection_reason = rejection_reason
        instance.save()

        message = 'Correction Request has been Processed'
        path = '/profile/'
        Notification.objects.create_notification(type=NotificationType.USER_CORRECTION_REQUEST_PROCESSED,
                                                 recipients=[agent], message=message, path=path)


class ProfileUpdateInput(graphene.InputObjectType):
    location = graphene.String(description="Latitude and Longitude of agent's location")


class ProfileUpdate(ModelMutation):
    class Arguments:
        input = ProfileUpdateInput()

    class Meta:
        description = (
            "Change location meta of an agent"
        )
        model = models.User
        permissions = (AccountPermissions.UPDATE_PROFILE,)
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context, permissions=None):
        return context.user.has_perm(AccountPermissions.UPDATE_PROFILE)

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):

        try:
            location = ast.literal_eval(data.get("location", None))
            latitude = ast.literal_eval(str(location.get("latitude")))
            longitude = ast.literal_eval(str(location.get("longitude")))
        except Exception:
            raise ValidationError(
                {
                    "location": ValidationError(
                        f"Location should have latitude and longitude value in correct format",
                        code=AccountErrorCode.INVALID
                    )
                }
            )
        if latitude < 20.2 or latitude > 26.4:
            raise ValidationError(
                {
                    "location": ValidationError(
                        f"Latitude of Bangladesh is between 20°34' to 26°38'",
                        code=AccountErrorCode.INVALID
                    )
                }
            )
        if longitude < 88.0 or longitude > 92.45:
            raise ValidationError(
                {
                    "location": ValidationError(
                        f"Longitude of Bangladesh is between 88°01' to 92°41'",
                        code=AccountErrorCode.INVALID
                    )
                }
            )
        data["location"] = f"{{\"latitude\": {latitude}, \"longitude\": {longitude}}}"

        return super().clean_input(info, instance, data)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        data["id"] = graphene.Node.to_global_id("User", info.context.user.id)
        return super().perform_mutation(root, info, **data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        location = cleaned_input.pop("location", None)
        instance.metadata.update({"location": location})
        key_user = admin_connector.get_user_by_id(user_id=instance.oidc_id)
        key_attributes = copy.deepcopy(key_user["attributes"])

        key_attributes["location"] = json.dumps(location)
        try:
            pass
            admin_connector.update_user(
                user_id=instance.oidc_id, params={"attributes": key_attributes}
            )
        except Exception:
            raise ValidationError(
                {
                    "": ValidationError(
                        "Something went wrong with identity provider",
                        code=AccountErrorCode.INVALID
                    )
                }
            )
        instance.save()


class AccountRequestDeletion(BaseMutation):
    class Arguments:
        redirect_url = graphene.String(
            required=True,
            description=(
                "URL of a view where users should be redirected to "
                "delete their account. URL in RFC 1808 format."
            ),
        )

    class Meta:
        description = (
            "Sends an email with the account removal link for the logged-in user."
        )
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def perform_mutation(cls, root, info, **data):
        user = info.context.user
        redirect_url = data["redirect_url"]
        try:
            validate_storefront_url(redirect_url)
        except ValidationError as error:
            raise ValidationError(
                {"redirect_url": error}, code=AccountErrorCode.INVALID
            )
        emails.send_account_delete_confirmation_email_with_url(redirect_url, user)
        return AccountRequestDeletion()


class AccountDelete(ModelDeleteMutation):
    class Arguments:
        token = graphene.String(
            description=(
                "A one-time token required to remove account. "
                "Sent by email using AccountRequestDeletion mutation."
            ),
            required=True,
        )

    class Meta:
        description = "Remove user account."
        model = models.User
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def clean_instance(cls, info, instance):
        super().clean_instance(info, instance)
        if instance.is_staff:
            raise ValidationError(
                "Cannot delete a staff account.",
                code=AccountErrorCode.DELETE_STAFF_ACCOUNT,
            )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        cls.clean_instance(info, user)

        token = data.pop("token")
        if not default_token_generator.check_token(user, token):
            raise ValidationError(
                {"token": ValidationError(INVALID_TOKEN, code=AccountErrorCode.INVALID)}
            )

        db_id = user.id

        user.delete()
        # After the instance is deleted, set its ID to the original database's
        # ID so that the success response contains ID of the deleted object.
        user.id = db_id
        return cls.success_response(user)


class AccountAddressCreate(ModelMutation, I18nMixin):
    user = graphene.Field(
        User, description="A user instance for which the address was created."
    )

    class Arguments:
        input = AddressInput(
            description="Fields required to create address.", required=True
        )
        type = AddressTypeEnum(
            required=False,
            description=(
                "A type of address. If provided, the new address will be "
                "automatically assigned as the customer's default address "
                "of that type."
            ),
        )

    class Meta:
        description = "Create a new address for the customer."
        model = models.Address
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def perform_mutation(cls, root, info, **data):
        address_type = data.get("type", None)
        user = info.context.user
        cleaned_input = cls.clean_input(
            info=info, instance=Address(), data=data.get("input")
        )
        address = cls.validate_address(cleaned_input)
        cls.clean_instance(info, address)
        cls.save(info, address, cleaned_input)
        cls._save_m2m(info, address, cleaned_input)
        if address_type:
            utils.change_user_default_address(user, address, address_type)
        return AccountAddressCreate(user=user, address=address)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        super().save(info, instance, cleaned_input)
        user = info.context.user
        instance.user_addresses.add(user)


class AccountAddressUpdate(BaseAddressUpdate):
    class Meta:
        description = "Updates an address of the logged-in user."
        model = models.Address
        error_type_class = AccountError
        error_type_field = "account_errors"


class AccountAddressDelete(BaseAddressDelete):
    class Meta:
        description = "Delete an address of the logged-in user."
        model = models.Address
        error_type_class = AccountError
        error_type_field = "account_errors"


class AccountSetDefaultAddress(BaseMutation):
    user = graphene.Field(User, description="An updated user instance.")

    class Arguments:
        id = graphene.ID(
            required=True, description="ID of the address to set as default."
        )
        type = AddressTypeEnum(required=True, description="The type of address.")

    class Meta:
        description = "Sets a default address for the authenticated user."
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        address = cls.get_node_or_error(info, data.get("id"), Address)
        user = info.context.user

        if not user.addresses.filter(pk=address.pk).exists():
            raise ValidationError(
                {
                    "id": ValidationError(
                        "The address doesn't belong to that user.",
                        code=AccountErrorCode.INVALID,
                    )
                }
            )

        if data.get("type") == AddressTypeEnum.BILLING.value:
            address_type = AddressType.BILLING
        else:
            address_type = AddressType.SHIPPING

        utils.change_user_default_address(user, address, address_type)
        return cls(user=user)


class AccountUpdateMeta(UpdateMetaBaseMutation):
    class Meta:
        description = "Updates metadata of the logged-in user."
        model = models.User
        public = True
        error_type_class = AccountError
        error_type_field = "account_errors"

    class Arguments:
        input = MetaInput(
            description="Fields required to update new or stored metadata item.",
            required=True,
        )

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def get_instance(cls, info, **data):
        return info.context.user


class RequestEmailChange(BaseMutation):
    user = graphene.Field(User, description="A user instance.")

    class Arguments:
        password = graphene.String(required=True, description="User password.")
        new_email = graphene.String(required=True, description="New user email.")
        redirect_url = graphene.String(
            required=True,
            description=(
                "URL of a view where users should be redirected to "
                "update the email address. URL in RFC 1808 format."
            ),
        )

    class Meta:
        description = "Request email change of the logged in user."
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        password = data["password"]
        new_email = data["new_email"]
        redirect_url = data["redirect_url"]

        if not user.check_password(password):
            raise ValidationError(
                {
                    "password": ValidationError(
                        "Password isn't valid.",
                        code=AccountErrorCode.INVALID_CREDENTIALS,
                    )
                }
            )
        if models.User.objects.filter(email=new_email).exists():
            raise ValidationError(
                {
                    "new_email": ValidationError(
                        "Email is used by other user.", code=AccountErrorCode.UNIQUE
                    )
                }
            )
        try:
            validate_storefront_url(redirect_url)
        except ValidationError as error:
            raise ValidationError(
                {"redirect_url": error}, code=AccountErrorCode.INVALID
            )
        token_kwargs = {
            "old_email": user.email,
            "new_email": new_email,
            "user_pk": user.pk,
        }
        token = create_jwt_token(token_kwargs)
        emails.send_user_change_email_url(redirect_url, user, new_email, token)
        return RequestEmailChange(user=user)


class ConfirmEmailChange(BaseMutation):
    user = graphene.Field(User, description="A user instance with a new email.")

    class Arguments:
        token = graphene.String(
            description="A one-time token required to change the email.", required=True
        )

    class Meta:
        description = "Confirm the email change of the logged-in user."
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        user = info.context.user
        token = data["token"]
        decoded_token = decode_jwt_token(token)
        new_email = decoded_token["new_email"]
        old_email = decoded_token["old_email"]

        if models.User.objects.filter(email=new_email).exists():
            raise ValidationError(
                {
                    "new_email": ValidationError(
                        "Email is used by other user.", code=AccountErrorCode.UNIQUE
                    )
                }
            )

        user.email = new_email
        user.save(update_fields=["email"])
        emails.send_user_change_email_notification(old_email)
        event_parameters = {"old_email": old_email, "new_email": new_email}

        account_events.customer_email_changed_event(
            user=user, parameters=event_parameters
        )
        return ConfirmEmailChange(user=user)


class UpdateUserPermissionInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    add_permissions = graphene.List(
        graphene.NonNull(PermissionEnum),
        description="List of permission code names to assign to this user.",
        required=True,
    )


class UpdateUserPermission(BaseMutation):
    user = graphene.Field(User, description="A user instance.")

    class Arguments:
        input = UpdateUserPermissionInput(
            description="Input fields add new permission to user.", required=True
        )

    class Meta:
        description = "User's individual permissions"
        error_type_class = UserPermissionUpdateError
        error_type_field = "permission_update_errors"
        permissions = (AccountPermissions.MANAGE_STAFF,)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        _model, id = graphene.Node.from_global_id(data["input"]["id"])
        user = get_object_or_404(models.User, pk=id)
        groups = user.groups.all()
        requested_permissions_list = data["input"]["add_permissions"]

        requested_permissions = get_permissions(requested_permissions_list)
        user_specific_permissions = user.user_permissions.all()
        user_group_related_permissions = auth_permission.objects.filter(group__in=groups)
        requested_permissions = requested_permissions.difference(user_group_related_permissions)

        remove_individual_permissions_from_user(user, user_specific_permissions)
        add_individual_permissions_to_user(user, requested_permissions)

        for perm in user_specific_permissions:
            user.user_permissions.remove(perm)

        for perm in requested_permissions:
            user.user_permissions.add(perm)

        user.save()

        return UpdateUserPermission(user=user)


class AssignApproverToUser(BaseMutation):
    user_request = graphene.Field(UserRequest, description="A user request instance.")

    class Arguments:
        request = graphene.ID(required=True, description="Request ID")
        assignee = graphene.ID(required=True, description="Approver ID")

    class Meta:
        description = (
            "Add a approver to  user request"
        )
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AccountPermissions.MANAGE_STAFF,)

    @classmethod
    def check_permissions(cls, context, permissions=None):
        permissions = permissions or cls._meta.permissions
        if not permissions:
            return True
        if context.user.has_perms(permissions) or context.user.has_perm(AccountPermissions.CHANGE_USER):
            return True
        app = getattr(context, "app", None)
        if app:
            # for now MANAGE_STAFF permission for app is not supported
            if AccountPermissions.MANAGE_STAFF in permissions:
                return False
            return app.has_perms(permissions)
        return False

    @classmethod
    def perform_mutation(cls, root, info, **data):

        try:
            _model, request_pk = graphene.Node.from_global_id(data["request"])
            user_request = models.UserRequest.objects.get(id=request_pk)
        except:
            raise ValidationError(
                {
                    "user": ValidationError(
                        "User Request  not found! Check given id",
                        code=AccountErrorCode.NOT_FOUND
                    )
                }
            )

        try:
            _model, assignee_pk = graphene.Node.from_global_id(data["assignee"])
            assigned = models.User.objects.get(id=assignee_pk)
        except:
            raise ValidationError(
                {
                    "user": ValidationError(
                        "User not found! Check given id",
                        code=AccountErrorCode.NOT_FOUND
                    )
                }
            )
        user_request.assigned = assigned
        user_request.save()

        return AssignApproverToUser(user_request=user_request)


class AssignParentToUser(BaseMutation):
    user = graphene.Field(User, description="A user instance.")

    class Arguments:
        user = graphene.ID(required=True, description="User ID")
        parent = graphene.ID(required=True, description="Parent ID")

    class Meta:
        description = (
            "Add a parent to a user"
        )
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AccountPermissions.MANAGE_STAFF,)

    @classmethod
    def check_permissions(cls, context, permissions=None):
        permissions = permissions or cls._meta.permissions
        if not permissions:
            return True
        if context.user.has_perms(permissions) or context.user.has_perm(AccountPermissions.CHANGE_USER):
            return True
        app = getattr(context, "app", None)
        if app:
            # for now MANAGE_STAFF permission for app is not supported
            if AccountPermissions.MANAGE_STAFF in permissions:
                return False
            return app.has_perms(permissions)
        return False

    @classmethod
    def perform_mutation(cls, root, info, **data):
        try:
            user = cls.get_node_or_error(info, data["user"])
        except:
            raise ValidationError(
                {
                    "user": ValidationError(
                        "User not found! Check given id",
                        code=AccountErrorCode.NOT_FOUND
                    )
                }
            )
        try:
            parent = cls.get_node_or_error(info, data["parent"])
        except:
            raise ValidationError(
                {
                    "user": ValidationError(
                        "Parent not found! Check given id",
                        code=AccountErrorCode.NOT_FOUND
                    )
                }
            )

        requestor = info.context.user
        group = requestor.groups.first()
        user_groups_allowed_to_be_managed = get_child_group_names(group)
        if group.name == "cm":
            check_if_attempted_from_valid_parent(requestor, user)

        if check_if_attempted_from_valid_parent(parent, user):
            if user.groups.first().name == "agent":
                user_userrequest = models.UserRequest.objects.filter(user=user, assigned=user.parent,
                                                                     status=UserApprovalRequest.PENDING)
                if len(user_userrequest) > 0:
                    user_userrequest = user_userrequest[0]
                    user_userrequest.assigned = parent
                    user_userrequest.save()
            elif user.groups.first().name in user_groups_allowed_to_be_managed:
                agents = get_all_agents(user)
                old_cm = get_cm(copy.deepcopy(user))
                new_cm = get_cm(copy.deepcopy(parent))
                for agent in agents:
                    user_userrequest = models.UserRequest.objects.filter(user=agent, assigned=old_cm,
                                                                         status=UserApprovalRequest.PENDING)
                    if len(user_userrequest) > 0:
                        user_userrequest = user_userrequest[0]
                        user_userrequest.assigned = new_cm
                        user_userrequest.save()
            user.parent = parent
            user.save()
        else:
            raise ValidationError(
                {
                    "parent": ValidationError(
                        "Given parent can not be assigned with given user.",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        return AssignParentToUser(user=user)


def get_cm(user):
    while user.groups.first().name != "cm":
        user = user.parent
    return user


# def get_all_agents(user):
#     agents = list()
#     for child in models.User.objects.filter(parent=user):
#         if child.groups.first().name == "agent":
#             agents.append(child.pk)
#         else:
#             agents.extend(get_all_agents(child))
#     return agents


def get_all_agents(parent_user):
    agents = []
    all_users = models.User.objects.all()

    if parent_user.regions.count() > 0:
        user_regions = parent_user.regions.all()
        all_users = all_users.filter(regions__in=user_regions, groups__name="agent")

    for user in all_users:
        agents.append(user.id)

    return agents


def parent_is_valid(user, parent):
    groups = GROUP_SEQUENCE
    user_group = groups.index(user.groups.first().name)
    parent_group = groups.index(parent.groups.first().name)
    return parent_group == user_group + 1


def remove_individual_permissions_from_user(user, permissions):
    oidc_id = user.oidc_id
    client_id = admin_connector.get_client_id("rstore-dashboard")

    role_names_from_keycloak = admin_connector.get_realm_roles()

    permissions_codenames = []
    for perm in permissions:
        permissions_codenames.append(perm.codename)

    roles = []
    for perm in role_names_from_keycloak:
        if perm["name"] in permissions_codenames:
            roles.append({'id': perm["id"], "name": perm["name"]})

    try:
        admin_connector.remove_realm_roles(oidc_id, client_id, roles)
    except KeycloakError as e:
        raise e


def add_individual_permissions_to_user(user, permissions):
    oidc_id = user.oidc_id
    client_id = admin_connector.get_client_id("rstore-dashboard")

    role_names_from_keycloak = admin_connector.get_realm_roles()

    permissions_codenames = []
    for perm in permissions:
        permissions_codenames.append(perm.codename)

    roles = []
    for perm in role_names_from_keycloak:
        if perm["name"] in permissions_codenames:
            roles.append({'id': perm["id"], "name": perm["name"]})

    try:
        admin_connector.assign_realm_roles(oidc_id, client_id, roles)
    except KeycloakError as e:
        raise e


class UploadDocument(BaseMutation):
    user = graphene.Field(User, description="A user instance.")

    class Arguments:
        image = Upload(
            required=True,
            description="Represents an image file in a multipart request.",
        )
        file_tag = graphene.String("Tag name of the file.", required=True)

    class Meta:
        description = "Upload user document."
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AccountPermissions.UPLOAD_DOCUMENT,)

    @classmethod
    def clean_system_file(cls, user, file_tag):
        files = user.documents.filter(file_tag=file_tag)
        if files:
            for file in files:
                file.content_file.delete()
            files.delete()

    @classmethod
    def perform_mutation(cls, _root, info, image, file_tag):
        user = info.context.user
        image_data = info.context.FILES.get(image)
        validate_image_file(image_data, "image")

        cls.clean_system_file(user, file_tag)
        the_image_file = models.Document.objects.create(
            content_file=image_data,
            mimetype=image_data.content_type,
            file_tag=file_tag
        )
        user.documents.add(the_image_file)

        return UploadDocument(user=user)


class UploadUserCorrectionDocument(BaseMutation):
    document = graphene.Field(Document, description="Document object")

    class Arguments:
        image = Upload(
            required=True,
            description="Represents a document file in a multipart request.",
        )
        file_tag = graphene.String("Tag name of the file.", required=True)

    class Meta:
        description = "Upload user correction document."
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AccountPermissions.REQUEST_USERCORRECTION,)

    @classmethod
    def clean_system_file(cls, user, file_tag):
        files = user.documents.filter(file_tag=file_tag)
        if files:
            for file in files:
                file.content_file.delete()
            files.delete()

    @classmethod
    def perform_mutation(cls, _root, info, image, file_tag):
        image_data = info.context.FILES.get(image)
        validate_image_file(image_data, "image")
        _validate_file_tag(file_tag)
        image_file = models.Document.objects.create(
            content_file=image_data,
            mimetype=image_data.content_type,
            file_tag=file_tag
        )

        return UploadUserCorrectionDocument(document=image_file)


class AddRegionToUser(BaseMutation):
    user = graphene.Field(User, description="A user instance.")

    class Arguments:
        user = graphene.ID(
            required=True,
            description='User id'
        )
        district = graphene.ID(
            required=True,
            description='District id'
        )
        thana = graphene.ID(
            required=True,
            description='Thana id'
        )

    class Meta:
        description = (
            "Add a region to a user"
        )
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AccountPermissions.MANAGE_STAFF, AccountPermissions.CHANGE_USER)

    @classmethod
    def check_permissions(cls, context, permissions=None):
        permissions = permissions or cls._meta.permissions
        return check_region_change_permissions(context, permissions)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        try:
            user = cls.get_node_or_error(info, data["user"])
        except Exception:
            raise ValidationError(
                {
                    "user": ValidationError("User with id does not exist")
                }
            )

        district = None
        thana = None
        try:
            district = cls.get_node_or_error(info, data["district"])
            thana = cls.get_node_or_error(info, data["thana"])

            models.District.objects.get(thana__pk=thana.id)
        except Exception:
            field_name = "district"
            error_message = "District with thana does not exist"
            if not district:
                error_message = "Invalid district"
            elif not thana:
                error_message = "Invalid thana"
                field_name: "thana"
            raise ValidationError(
                {
                    field_name: ValidationError(error_message)
                }
            )

        parent = info.context.user
        if parent.groups.first().name == "cm":
            check_parent_valid(parent, user)
        region = models.Region.objects.get_or_create(thana=thana, district=district)[0]

        user.regions.add(region)
        return AddRegionToUser(user=user)


class RemoveRegionFromUser(BaseMutation):
    user = graphene.Field(User, description="A user instance.")

    class Arguments:
        user = graphene.ID(
            required=True,
            description='User id'
        )
        region = graphene.ID(
            required=True,
            description='District id'
        )

    class Meta:
        description = (
            "Remove a region from a user"
        )
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AccountPermissions.MANAGE_STAFF, AccountPermissions.CHANGE_USER)

    @classmethod
    def check_permissions(cls, context, permissions=None):
        permissions = permissions or cls._meta.permissions
        return check_region_change_permissions(context, permissions)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        try:
            user = cls.get_node_or_error(info, data["user"])
        except Exception:
            raise ValidationError(
                {
                    "user": ValidationError("User with id does not exist")
                }
            )
        region = None
        parent = info.context.user
        if parent.groups.first().name == "cm":
            check_parent_valid(parent, user)
        try:
            region = cls.get_node_or_error(info, data["region"])
            models.User.objects.get(id=user.id, regions__id=region.id)
            user.regions.remove(region)
            return RemoveRegionFromUser(user=user)
        except Exception:
            message = "District with thana does not exist"
            if region is not None:
                message = "Thana in district does not exist for user"

            raise ValidationError(
                {
                    "region": ValidationError(message)
                }
            )


class CreateGroupChildMappingInput(graphene.InputObjectType):
    group_id = graphene.ID(description="Parent Group ID", required=True)
    child_id = graphene.ID(description="Child Group ID", required=True)
    has_txn = graphene.Boolean(required=True, description="Determines if a group "
                                                          "is present in transactional hierarchy")


class CreateGroupChildMapping(BaseMutation):
    group_child_map = graphene.List(GroupChildTrxMap)

    class Arguments:
        input = graphene.List(
            of_type=CreateGroupChildMappingInput,
            required=True,
            description="List of group child mapping object"
        )

    class Meta:
        description = "Creates a mapping between parent group, it's child and trx."
        permissions = (AccountPermissions.MANAGE_USERS,)
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def clean_input(cls, info, instance, data):

        seen_data = set()
        new_list = []
        for obj in data:
            if obj.child_id != "0":
                _, group_id = graphene.Node.from_global_id(obj.group_id)
                _, child_id = graphene.Node.from_global_id(obj.child_id)

                parent_group = models.Group.objects.get(id=group_id)
                child_group = models.Group.objects.get(id=child_id)

                obj["parent_group_name"] = parent_group.name
                obj["child_group_name"] = child_group.name

                obj["group_id"] = group_id
                obj["child_id"] = child_id

                if models.GroupHierarchy.objects.filter(child_id=child_id, has_txn=True).exists():
                    if obj.has_txn is not False:
                        raise ValidationError(
                            {
                                "group_id": ValidationError(
                                    f'Another transactional group with child "{child_group.name}" already exists',
                                    code=AccountErrorCode.UNIQUE,
                                )
                            }
                        )

            else:
                _, group_id = graphene.Node.from_global_id(obj.group_id)

                parent_group = models.Group.objects.get(id=group_id)

                obj["parent_group_name"] = parent_group.name

                obj["group_id"] = group_id

            if group_id not in seen_data:
                new_list.append(obj)
                seen_data.add(group_id)
            else:
                raise ValidationError(
                    {
                        "group_id": ValidationError(
                            f'Multiple entry provided for group "{parent_group.name}"',
                            code=AccountErrorCode.INVALID,
                        )
                    }
                )

            if models.GroupHierarchy.objects.filter(parent_id=group_id).exists():
                raise ValidationError(
                    {
                        "group_id": ValidationError(
                            f'An entry for group "{parent_group.name}" already exists',
                            code=AccountErrorCode.UNIQUE,
                        )
                    }
                )

        return data

    @classmethod
    def perform_mutation(cls, _root, info, **data):

        group_child_map_list = []
        group_hierarchy = models.GroupHierarchy()

        cleaned_input = cls.clean_input(info, group_hierarchy, data.get("input"))

        group_hierarchy_ins_list = []

        try:
            with transaction.atomic():
                for obj in cleaned_input:
                    group_child_map_dict = {}

                    if obj.child_id != "0":

                        group_hierarchy_instance = models.GroupHierarchy(
                            parent_id=obj.get("group_id"),
                            child_id=obj.get("child_id"),
                            has_txn=obj.get("has_txn")
                        )
                        group_hierarchy_ins_list.append(group_hierarchy_instance)

                        group_child_map_dict["group_name"] = obj.get("parent_group_name")
                        group_child_map_dict["child_name"] = obj.get("child_group_name")
                        group_child_map_dict["has_txn"] = obj.has_txn

                    else:

                        group_hierarchy_instance = models.GroupHierarchy(
                            parent_id=obj.get("group_id"),
                            child_id=None,
                            has_txn=obj.get("has_txn")
                        )
                        group_hierarchy_ins_list.append(group_hierarchy_instance)

                        group_child_map_dict["group_name"] = obj.get("parent_group_name")
                        group_child_map_dict["child_name"] = None
                        group_child_map_dict["has_txn"] = obj.has_txn

                    group_child_map_list.append(group_child_map_dict)

                models.GroupHierarchy.objects.bulk_create(group_hierarchy_ins_list)

        except IntegrityError:
            raise ValidationError(
                {
                    "group_id": ValidationError(
                        "Something went wrong. Please contact support",
                        code=AccountErrorCode.INVALID,
                    )
                }
            )

        return CreateGroupChildMapping(group_child_map=group_child_map_list)


def check_region_change_permissions(context, permissions=None):
    if not permissions:
        return True
    if context.user.has_perm(AccountPermissions.CHANGE_USER) or context.user.has_perm(
            AccountPermissions.MANAGE_STAFF):
        return True
    app = getattr(context, "app", None)
    if app:
        # for now MANAGE_STAFF permission for app is not supported
        if AccountPermissions.MANAGE_STAFF in permissions:
            return False
        return app.has_perms(permissions)
    return False


def check_parent_valid(parent, user):
    all_user = set(models.User.get_children(parent, True))
    if user not in all_user:
        raise ValidationError(
            {
                "user": ValidationError(
                    "You cannot perform this operation for this user",
                    code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_other_phone(other_phone):
    _validate_phone_number("other_phone", other_phone)
    if models.User.objects.filter(phone=other_phone).exists():
        raise ValidationError(
            {
                "other_phone": ValidationError(
                    "Phone number is not available", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_el_msisdn(el_msisdn):
    _validate_phone_number("el_msisdn", el_msisdn)


def _validate_robicash_no(robicash_no):
    _validate_phone_number("robicash_no", robicash_no)


def _validate_agent_banking_number(agent_banking_number):
    _validate_phone_number("agent_banking_number", agent_banking_number)


def _validate_phone_number(field_name, phone_number):
    phone_valid = re.search(r"^01[3-9][0-9]{8}$", phone_number)
    if not phone_valid:
        raise ValidationError(
            {
                field_name: ValidationError(
                    PHONE_VALIDATION_TEXT, code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_required(field_name, field_value):
    if not field_value:
        raise ValidationError(
            {
                field_name: ValidationError(
                    f"Field {field_name} is required",
                    code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_gender(gender):
    if gender not in Gender.get_keys():
        raise ValidationError(
            {
                "gender": ValidationError(
                    "Selected gender type is not valid", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_postal_code(postal_code):
    postal_code_valid = re.search(r"^[1-9]\d{3}$", postal_code)
    if not postal_code_valid:
        raise ValidationError(
            {
                "postal_code": ValidationError(
                    "Please provide a valid Bangladeshi postal code", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_routing_number(routing_number):
    valid_routing_number = re.search(r"^[0-9]{3,}$", routing_number)
    if not valid_routing_number:
        raise ValidationError(
            {
                "routing_number": ValidationError(
                    "Valid routing number should be 3 or more digits only",
                    code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_shop_size(shop_size):
    if shop_size not in ShopSize.get_keys():
        raise ValidationError(
            {
                "shop_size": ValidationError(
                    "Shop size is not valid", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_shop_type(shop_type):
    if shop_type not in ShopType.get_keys():
        raise ValidationError(
            {
                "shop_type": ValidationError(
                    "Shop type is not valid", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_no_of_employees(no_of_employees):
    if no_of_employees not in EmployeeCount.get_keys():
        raise ValidationError(
            {
                "no_of_employees": ValidationError(
                    "Given employee number is not valid", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_education(education):
    if education not in Qualification.get_keys():
        raise ValidationError(
            {
                "education": ValidationError(
                    "Given educational info is not valid", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_nid(nid):
    nid_valid = re.search(r"^\d{10}$|\d{13}$|\d{17}$", nid)
    if not nid_valid:
        raise ValidationError(
            {
                "nid": ValidationError(
                    "A valid NID should be 10, 13 or 17 digits in length", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_trade(trade):
    if not re.search(r"\d{1,4}$", trade):
        raise ValidationError(
            {
                "trade_license": ValidationError(
                    "Trade license number has to be a positive number", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_trade_license(trade):
    if not re.search(r"\d{1,4}$", trade):
        raise ValidationError(
            {
                "trade_license": ValidationError(
                    "Trade license number has to be a positive number", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_mfs_number(mfs_number):
    mfs_number_valid = re.search(r"^01[3-9][0-9]{8}[0-9]?$", mfs_number)
    if not mfs_number_valid:
        raise ValidationError(
            {
                "mfs_number": ValidationError(
                    "A valid mobile banking phone number is required", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_bank_account_number(bank_account_number):
    err_msg = None
    if len(bank_account_number) < 3 or len(bank_account_number) > 24:
        err_msg = "Bank account number must have at least 3 characters and at most 24 characters"
    else:
        bank_account_number_valid = re.search(r"^\d+((\.\d+)|(-\d+))*$", bank_account_number)
        if not bank_account_number_valid:
            err_msg = "Bank account number must contain numbers or numbers with . or - only"

    if err_msg:
        raise ValidationError(
            {
                "bank_account_number": ValidationError(
                    err_msg,
                    code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_bank_account_name(field_value, field_name="bank_account_name"):
    _validate_at_least_2_characters(field_name, field_value)


def _validate_bank_name(field_value, field_name="bank_name"):
    _validate_at_least_2_characters(field_name, field_value)


def _validate_store_name(field_value, field_name="store_name"):
    _validate_at_least_2_characters(field_name, field_value)


def _validate_branch_name(field_value, field_name="branch_name"):
    _validate_at_least_2_characters(field_name, field_value)


def _validate_street_address_1(field_value):
    if len(field_value) > 50:
        raise ValidationError(
            {
                "street_address_1": ValidationError(
                    f"Street Address must have less than 50 characters"
                )
            }
        )
    if len(field_value) == 0:
        raise ValidationError(
            {
                "street_address_1": ValidationError(
                    f"Street Address must have values"
                )
            }
        )


def _validate_at_least_2_characters(field_name, field_value):
    if len(field_value) < 2:
        raise ValidationError(
            {
                field_name: ValidationError(
                    f"{field_name} must have at least 2 characters"
                )
            }
        )


def _validate_monthly_income(monthly_income):
    try:
        monthly_income = Decimal(monthly_income.replace(',', ''))
    except:
        raise ValidationError(
            {
                "monthly_income": ValidationError(
                    "Please enter a valid number",
                    code=AccountErrorCode.INVALID
                )
            }
        )
    if monthly_income < 1000 or monthly_income > 1000000:
        raise ValidationError(
            {
                "monthly_income": ValidationError(
                    "Monthly income must be a positive number between 1000 and 1000000, inclusive",
                    code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_tin(tin):
    if len(tin) < 1 or len(tin) > 24:
        raise ValidationError(
            {
                "tin": ValidationError(
                    "TIN certificate must have at least 1 character and at most 24 characters",
                    code=AccountErrorCode.INVALID
                )
            }
        )


def _check_image_exist(user, field_name, file_tag):
    document = user.documents.filter(file_tag=file_tag).exists()
    if not document:
        raise ValidationError(
            {
                field_name: ValidationError(
                    f"{file_tag} must exist to proceed",
                    code=AccountErrorCode.NOT_FOUND
                )
            }
        )


def _validate_file_tag(file_tag):
    if file_tag not in DocumentFileTag.get_keys():
        raise ValidationError(
            {
                "file_tag": ValidationError(
                    "Given file tag is not valid", code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_location(location):
    if type(location) != 'dict':
        return

    latitude = location['latitude']
    longitude = location['longitude']

    if latitude == 0 or longitude == 0:
        raise ValidationError(
            {
                "location": ValidationError(
                    "Provide a valid latitude and longitude",
                    code=AccountErrorCode.INVALID
                )
            }
        )


def _validate_email(email):
    email = email.lower()
    if models.User.objects.filter(email=email).exists():
        raise ValidationError(
            {
                "email": ValidationError(
                    "Email is not available",
                    code=AccountErrorCode.INVALID
                )
            }
        )


class CreateManagerInput(graphene.InputObjectType):
    email = graphene.String(description="Email address of the user.", required=True)
    group = graphene.String(description="group of the user.", required=True)
    phone = graphene.String(description="Phone number of user", required=True)
    password = graphene.String(description="Password of the user", required=True)
    first_name = graphene.String(description="First mame", required=True)
    last_name = graphene.String(description="Last name", required=True)
    address = graphene.String(description="Address", required=True)


class CreateManager(ModelMutation):
    class Arguments:
        input = CreateManagerInput(
            description="Fields required to create a user.", required=True
        )

    class Meta:
        description = "Register a new manager."
        exclude = ["password", "oidc_id", "district_id", "thana_id"]
        model = models.User
        permissions = (AccountPermissions.MANAGE_USERS,)
        error_type_class = AccountError
        error_type_field = "account_errors"

    @classmethod
    def mutate(cls, root, info, **data):
        response = super().mutate(root, info, **data)
        return response

    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        password = data["password"]
        try:
            password_validation.validate_password(password, instance)
        except ValidationError as error:
            raise ValidationError({"password": error})
        return super().clean_input(info, instance, data, input_cls=None)

    @classmethod
    def save(cls, info, user, cleaned_input):
        phone = cleaned_input.get("phone")
        email = cleaned_input.get("email")
        password = cleaned_input.get("password")
        first_name = cleaned_input.get("first_name", None)
        last_name = cleaned_input.get("last_name", None)
        address = cleaned_input.get("address")
        group = cleaned_input.get("group")

        if not models.User.objects.email_available(email):
            raise ValidationError(
                {
                    "email": ValidationError(
                        "A user already exists with this email",
                        code=AccountErrorCode.UNIQUE
                    )
                }
            )
        if not models.User.objects.phone_available(phone):
            raise ValidationError(
                {
                    "phone": ValidationError(
                        "A user already exists with this mobile number",
                        code=AccountErrorCode.UNIQUE
                    )
                }
            )
        if len(address) > 50:
            raise ValidationError(
                {
                    "address": ValidationError(
                        "Address should be less than 50 character",
                        code=AccountErrorCode.INVALID
                    )
                }
            )

        keycloak_user_id = admin_connector.create_user(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            email=email,
            is_enabled=True,
            password=password,
            temp_password=True,
            groups=[group],
            attributes={}
        )
        if keycloak_user_id:
            models.User.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                password=password,
                user_group=group,
                approval_status='approved',
                keycloak_user_id=keycloak_user_id,
            )
        else:
            raise ValidationError(
                {
                    "": ValidationError(
                        "Something went wrong with identity provider",
                        code=AccountErrorCode.INVALID
                    )
                }
            )


class GroupMapDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a map to delete.")

    class Meta:
        description = "Deletes a group map."
        model = models.GroupHierarchy
        permissions = (AccountPermissions.MANAGE_USERS,)
        error_type_class = AccountError
        error_type_field = "account_errors"
