import re
from collections import deque, defaultdict

from typing import Union

from auditlog.registry import auditlog
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import models as auth_models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin, Group, Permission,
)
from django.contrib.postgres.fields import JSONField
from django.core.validators import RegexValidator, FileExtensionValidator
from django.db import models
from django.db.models import Q, Value, Sum, Count
from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.timezone import make_aware
from django_countries.fields import Country, CountryField
from phonenumber_field.modelfields import PhoneNumber, PhoneNumberField
from versatileimagefield.fields import VersatileImageField

from . import CustomerEvents, UserApproval, DocumentType, UserApprovalRequest, group_hierarchy
from .validators import validate_possible_number
from ..core.models import ModelWithMetadata
from ..core.permissions import AccountPermissions, BasePermissionEnum
from ..core.utils.json_serializer import CustomJsonEncoder

from softdelete.models import SoftDeleteModel
from softdelete.managers import SoftDeleteManager

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

from itertools import groupby, chain
from datetime import datetime, timedelta
from time import time

class PossiblePhoneNumberField(PhoneNumberField):
    """Less strict field for phone numbers written to database."""

    default_validators = [validate_possible_number]


class AddressQueryset(models.QuerySet):
    def annotate_default(self, user):
        # Set default shipping/billing address pk to None
        # if default shipping/billing address doesn't exist
        default_shipping_address_pk, default_billing_address_pk = None, None
        if user.default_shipping_address:
            default_shipping_address_pk = user.default_shipping_address.pk
        if user.default_billing_address:
            default_billing_address_pk = user.default_billing_address.pk

        return user.addresses.annotate(
            user_default_shipping_address_pk=Value(
                default_shipping_address_pk, models.IntegerField()
            ),
            user_default_billing_address_pk=Value(
                default_billing_address_pk, models.IntegerField()
            ),
        )


class Address(models.Model):
    first_name = models.CharField(max_length=256, blank=True)
    last_name = models.CharField(max_length=256, blank=True)
    company_name = models.CharField(max_length=256, blank=True)
    street_address_1 = models.CharField(max_length=256, blank=True)
    street_address_2 = models.CharField(max_length=256, blank=True)
    city = models.CharField(max_length=256, blank=True)
    city_area = models.CharField(max_length=128, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = CountryField()
    country_area = models.CharField(max_length=128, blank=True)
    phone = PossiblePhoneNumberField(blank=True, default="")

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    objects = AddressQueryset.as_manager()

    class Meta:
        ordering = ("pk",)

    @property
    def full_name(self):
        return "%s %s" % (self.first_name, self.last_name)

    def __str__(self):
        return "%s - %s - %s" % (self.city_area, self.city, self.street_address_1)

    def __eq__(self, other):
        if not isinstance(other, Address):
            return False
        return self.as_data() == other.as_data()

    __hash__ = models.Model.__hash__

    def as_data(self):
        """Return the address as a dict suitable for passing as kwargs.

        Result does not contain the primary key or an associated user.
        """
        data = model_to_dict(self, exclude=["id", "user"])
        if isinstance(data["country"], Country):
            data["country"] = data["country"].code
        if isinstance(data["phone"], PhoneNumber):
            data["phone"] = str(data["phone"])
            #  data["phone"] = data["phone"].as_e164
        return data

    def get_copy(self):
        """Return a new instance of the same address."""
        return Address.objects.create(**self.as_data())


class District(models.Model):
    name = models.CharField(max_length=256, blank=False, unique=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def as_data(self):
        data = model_to_dict(self)
        return data


class Thana(models.Model):
    name = models.CharField(max_length=256, blank=False)
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ("name",)
        unique_together = [['name', 'district']]

    def __str__(self):
        return self.name + ", District: " + self.district.name

    def as_data(self):
        data = model_to_dict(self)
        return data


class Region(models.Model):
    thana = models.ForeignKey(Thana, on_delete=models.CASCADE)
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ("pk",)
        unique_together = [['thana', 'district']]

    def __str__(self):
        return "Thana: " + self.thana.name + ", District: " + self.district.name

    def as_data(self):
        data = model_to_dict(self)
        return data


class Document(models.Model):
    mimetype = models.CharField(max_length=128, blank=True)
    content_file = models.FileField(
        upload_to="documents", blank=True,
        validators=[FileExtensionValidator(allowed_extensions=dict(DocumentType.CHOICES))]
    )
    file_tag = models.CharField(max_length=64, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ("pk",)
        app_label = "account"

    def save(self, *args, **kwargs):      
        *_ , extension = self.content_file.name.split('.')
        if extension.lower() in ["jpg",'jpeg']:
            compresed_img = resize_compress(self.content_file)
            file_name = self.content_file.name
            self.content_file.delete(save=False) 
            self.content_file.save(
                file_name,
                content = compresed_img,
                save = False,
                )        
        super(Document, self).save(*args, **kwargs)


def resize_compress(img_stream, quality = 60, size =(1000,1000)):     
        with Image.open(img_stream) as pil_image_obj:
            new_image_io = BytesIO()
            pil_image_obj.thumbnail(size)
            pil_image_obj.save(new_image_io,quality=10, optimize=True, format='JPEG')
            img_content = ContentFile(new_image_io.getvalue())
        return img_content


class UserManager(BaseUserManager, SoftDeleteManager):

    @staticmethod
    def email_available(email):
        if email is None or not User.objects.filter(email__iexact=email).exists():
            return True
        else:
            return False

    @staticmethod
    def phone_available(phone):
        phone_valid = re.search("^01[3-9][0-9]{8}$", phone)
        if phone_valid and not User.objects.filter(phone=phone).exists():
            return True
        else:
            return False

    @staticmethod
    def get_dco(district_id, thana_id):
        users = User.objects.filter(regions__district_id=district_id, regions__thana_id=thana_id, groups__name="dco")
        if len(users) > 0:
            return users[0]
        return None

    @staticmethod
    def get_dcm(district_id, thana_id):
        users = User.objects.filter(regions__district_id=district_id, regions__thana_id=thana_id, groups__name="dcm")
        if len(users) > 0:
            return users[0]
        return None

    @staticmethod
    def get_cm_by_region(region):
        users = User.objects.filter(regions__in=[region], groups__name="cm")
        if len(users) > 0:
            return users[0]
        return None

    @staticmethod
    def get_dcm_by_region(region):
        users = User.objects.filter(regions__in=[region], groups__name="dcm")
        if len(users) > 0:
            return users[0]
        return None

    @staticmethod
    def get_dco_by_region(region):
        users = User.objects.filter(regions__in=[region], groups__name="dco")
        if len(users) > 0:
            return users[0]
        return None

    def create_user(
            self, phone, email=None, password=None, is_staff=True, is_active=True, user=None, **extra_fields
    ):
        group = extra_fields.pop("user_group", "agent")
        if extra_fields.get("approval_status", UserApproval.INITIAL_SUBMISSION) not in \
                UserApproval.get_keys():
            extra_fields["approval_status"] = UserApproval.INITIAL_SUBMISSION

        keycloak_user_id = extra_fields.pop("keycloak_user_id")
        if keycloak_user_id:
            extra_fields["oidc_id"] = keycloak_user_id
        else:
            raise ConnectionError('Something went wrong with identity provider')

        store_name = extra_fields.pop("store_name", None)
        if store_name:
            extra_fields["metadata"] = {
                "store_name": store_name,
            }
        given_user_address = extra_fields.pop("address", None)
        if email:
            email = email.lower()
            email = UserManager.normalize_email(email)
        # Google OAuth2 backend send unnecessary username field
        extra_fields.pop("username", None)
        district = extra_fields.pop("district", None)
        thana = extra_fields.pop("thana", None)

        if user is None:
            user = self.model(
                phone=phone, email=email, is_active=is_active, is_staff=is_staff, **extra_fields
            )
        else:
            user.oidc_id = keycloak_user_id
            user.is_staff = is_staff
            user.is_active = is_active
            user.approval_status = extra_fields.get("approval_status", UserApproval.INITIAL_SUBMISSION)
            user.parent = extra_fields.get("parent", None)
            user.metadata = extra_fields.get("metadata", {})

        if password:
            user.set_password(password)
        user.save()

        self.set_group(user, group)

        if district and thana:
            self.set_region(district, thana, user)

        if given_user_address:
            user_address = Address.objects.create(
                first_name=user.first_name if user.first_name else '',
                last_name=user.last_name if user.last_name else '',
                street_address_1=given_user_address,
                phone=user.phone,
                city=user.regions.first().district.name,
                city_area=user.regions.first().thana.name,
                country="BD",
            )
            user.addresses.add(user_address)
            user.default_billing_address = user_address
            user.default_shipping_address = user_address
            user.save()

        return user

    def set_region(self, district, thana, user):
        user_region, _ = Region.objects.get_or_create(
            district=district,
            thana=thana
        )
        user.regions.add(user_region.pk)
        user.save()

    def create_superuser(self, email, password=None, **extra_fields):
        return self.create_user(
            email, password, is_staff=True, is_superuser=True, **extra_fields
        )

    def customers(self):
        return self.get_queryset().filter(
            Q(is_staff=False) | (Q(is_staff=True) & Q(orders__isnull=False))
        )

    def staff(self):
        return self.get_queryset().filter(is_staff=True)

    def set_group(self, user, group_name):
        user_group = auth_models.Group.objects.get(name=group_name)
        user_group.user_set.add(user)


class User(PermissionsMixin, ModelWithMetadata, AbstractBaseUser, SoftDeleteModel):
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=256, blank=True)
    last_name = models.CharField(max_length=256, blank=True)
    phone = models.CharField(max_length=11, blank=False, validators=[
        RegexValidator(regex='^01[3-9][0-9]{8}$', message='Please give correct phone number like 01811111111',
                       code='wrong_phone')])
    oidc_id = models.CharField(max_length=256, blank=True, null=True)
    addresses = models.ManyToManyField(
        Address, blank=True, related_name="user_addresses"
    )
    documents = models.ManyToManyField(
        Document, blank=True, related_name="user_documents"
    )
    transaction_receipts = models.ManyToManyField(
        Document, blank=True, related_name="user_transaction_receipts"
    )
    regions = models.ManyToManyField(
        Region, blank=True, related_name="user_regions"
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey(
        'self', related_name="+", null=True, blank=True, on_delete=models.SET_NULL
    )

    approval_status = models.CharField(
        max_length=20,
        choices=UserApproval.CHOICES,
        default=UserApproval.INITIAL_SUBMISSION,
    )
    note = models.TextField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)
    default_shipping_address = models.ForeignKey(
        Address, related_name="+", null=True, blank=True, on_delete=models.SET_NULL
    )
    default_billing_address = models.ForeignKey(
        Address, related_name="+", null=True, blank=True, on_delete=models.SET_NULL
    )

    avatar = VersatileImageField(upload_to="user-avatars", blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    USERNAME_FIELD = "phone"

    objects = UserManager()

    class Meta:
        ordering = ("phone",)
        permissions = (
            (AccountPermissions.MANAGE_USERS.codename, "Manage customers."),
            (AccountPermissions.MANAGE_STAFF.codename, "Manage staff."),
            (AccountPermissions.VIEW_STAFF.codename, "View staff."),
            (AccountPermissions.REMOVE_STAFF.codename, "Delete staff."),
            (AccountPermissions.MANAGE_REQUESTS.codename, "Manage requests."),
            (AccountPermissions.MANAGE_CONFIGURATION.codename, "Manage configuration."),
            (AccountPermissions.UPDATE_KYC.codename, "Update KYC."),
            (AccountPermissions.UPLOAD_DOCUMENT.codename, "Upload document."),
            (AccountPermissions.MANAGE_REPORTS.codename, "Manage reports."),
            (AccountPermissions.UPDATE_PROFILE.codename, "Update profile")
        )
        constraints = [
            models.UniqueConstraint(
                name="unique_email",
                fields=["email"],
                condition=Q(deleted_at=None)
            ),
            models.UniqueConstraint(
                name="unique_phone",
                fields=["phone"],
                condition=Q(deleted_at=None)
            ),
            models.UniqueConstraint(
                name="unique_oidc",
                fields=["oidc_id"],
                condition=Q(deleted_at=None)
            ),
            models.UniqueConstraint(
                name="unique_phone_email",
                fields=["phone", "email"],
                condition=Q(deleted_at=None)
            )
        ]

    def get_full_name(self):
        if self.first_name or self.last_name:
            return ("%s %s" % (self.first_name, self.last_name)).strip()
        if self.default_billing_address:
            first_name = self.default_billing_address.first_name
            last_name = self.default_billing_address.last_name
            if first_name or last_name:
                return ("%s %s" % (first_name, last_name)).strip()
        return "N/A"

    def get_short_name(self):
        return self.phone

    def has_perm(self, perm: Union[BasePermissionEnum, str], obj=None):  # type: ignore
        # This method is overridden to accept perm as BasePermissionEnum
        perm_value = perm.value if hasattr(perm, "value") else perm  # type: ignore
        return super().has_perm(perm_value, obj)

    def get_children_query_filter(self, include_self=True):
        parents = list()
        group = self.groups.first().name
        while group:
            parents.append('parent')
            group = group_hierarchy.get(group)
        if len(parents) > 0:
            q = Q(**{'parent': self})
            for i in range(1, len(parents) + 1):
                q |= Q(**{'__'.join(parents[:i]): self})
        else:
            q = Q(pk=0)

        if include_self:
            q |= Q(pk=self.pk)

        return q

    def get_children(self, include_self=True):
        start_time = time()
        # all_users = User.objects.all()

        group_children = get_hierarchy(group_id=self.groups.first().id)

        if len(group_children) == 1 and group_children[0] == self.groups.first().id:
            if GroupHierarchy.objects.filter(
                    child_id=self.groups.first().id, has_txn=True
            ).exists():
                return [self.pk]

        group_children = group_children[1:]

        qf = Q()
        if len(group_children) > 0:
            qf &= Q(groups__in=group_children)
            # all_users = all_users.filter(groups__in=group_children)

        if self.regions.count() > 0:
            result = []
            parent_regions = self.regions.all().values_list('id', flat=True)
            qf &= Q(regions__in=parent_regions)

            # parent_regions = self.regions.all()
            # result = all_users.filter(regions__in=parent_regions)

            # for user in all_users:
            #     child_regions = user.regions.all().values_list('id', flat=True)
            #     # if set(list(child_regions)).issubset(set(list(parent_regions))):
            #     if all(item in list(parent_regions) for item in list(child_regions)):
            #         result.append(user)
            #
            # all_users = result
        all_users = User.objects.filter(qf)

        child_list = []

        for user in all_users:
            child_list.append(user.id)

        if include_self:
            child_list.append(self.pk)

        print("--- get_children() %s seconds ---" % (time() - start_time))

        return child_list

    def get_profile(self):
        monthly_totals = dict()

        from ..commission.models import UserProfile
        all_profiles = UserProfile.objects.all().order_by('-priority_order')

        for profile in all_profiles:
            if monthly_totals.get(profile.period, None):
                result = check_profile_matches(monthly_totals[profile.period], profile)
            else:
                to_date = make_aware(datetime.today().replace(day=1) - timedelta(days=1))
                from_date = to_date + relativedelta(months=-profile.period) + timedelta(days=1)
                orders_list = self.orders.filter(created__range=[from_date, to_date]).distinct()
                monthly_totals[profile.period] = [sum(x.total_net_amount for x in orders_list), len(orders_list)]
                result = check_profile_matches(monthly_totals[profile.period], profile)
            if result:
                return result

    def get_parents(self, include_self=True, transaction_enabled=True):
        result_users = []
        all_users = User.objects.all()

        group_parents = get_hierarchy(group_id=self.groups.first().id, parent=True)

        group_parents = group_parents[1:]

        if transaction_enabled:
            groups_with_transactions = Group.objects.filter(
                parent_group__parent_id__in=group_parents, parent_group__has_txn=True
            ).values_list('id', flat=True)

            group_parents = groups_with_transactions

        if self.regions.count() > 0:
            user_regions = self.regions.all()
            all_users = all_users.filter(regions__in=user_regions)

        if len(group_parents) > 0:
            result_users = all_users.filter(groups__in=group_parents)

        parent_list = []

        for user in result_users:
            parent_list.append(user)

        if include_self:
            parent_list.append(self)

        return parent_list


class UserCorrection(ModelWithMetadata):
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=256, blank=True)
    last_name = models.CharField(max_length=256, blank=True)
    phone = models.CharField(max_length=11, blank=False, validators=[
        RegexValidator(regex='^01[3-9][0-9]{8}$', message='Please give correct phone number like 01811111111',
                       code='wrong_phone')])
    addresses = models.ManyToManyField(
        Address, blank=True, related_name="user_correction_addresses"
    )
    documents = models.ManyToManyField(
        Document, blank=True, related_name="user_correction_documents"
    )
    note = models.TextField(null=True, blank=True)
    avatar = VersatileImageField(upload_to="user-avatars", blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    USERNAME_FIELD = "phone"

    class Meta:
        ordering = ("phone",)
        permissions = (
            (AccountPermissions.REQUEST_USERCORRECTION.codename, "Manage user correction requests."),
            (AccountPermissions.PROCESS_USERCORRECTION.codename, "Process user correction requests."),
        )


class UserRequest(models.Model):
    user = models.ForeignKey(
        User,
        related_name="user_requests",
        on_delete=models.CASCADE,
    )
    assigned = models.ForeignKey(
        User,
        related_name="+",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=UserApprovalRequest.CHOICES,
        default="pending",
    )
    rejection_reason = models.CharField(max_length=256, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return "%s - %s" % (self.status, self.user)


class UserCorrectionRequest(models.Model):
    user = models.ForeignKey(
        User,
        related_name="user_correction_requests",
        on_delete=models.CASCADE,
    )
    user_correction = models.ForeignKey(
        UserCorrection,
        related_name="user_correction_requests",
        on_delete=models.CASCADE,
    )
    assigned = models.ForeignKey(
        User,
        related_name="+",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=UserApprovalRequest.CHOICES,
        default="pending",
    )
    rejection_reason = models.CharField(max_length=256, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return "%s - %s" % (self.status, self.user)


class CustomerNote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL
    )
    date = models.DateTimeField(db_index=True, auto_now_add=True)
    content = models.TextField()
    is_public = models.BooleanField(default=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="notes", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ("date",)


class CustomerEvent(models.Model):
    """Model used to store events that happened during the customer lifecycle."""

    date = models.DateTimeField(default=timezone.now, editable=False)
    type = models.CharField(
        max_length=255,
        choices=[
            (type_name.upper(), type_name) for type_name, _ in CustomerEvents.CHOICES
        ],
    )

    order = models.ForeignKey("order.Order", on_delete=models.SET_NULL, null=True)
    parameters = JSONField(blank=True, default=dict, encoder=CustomJsonEncoder)

    user = models.ForeignKey(User, related_name="events", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ("date",)

    def __repr__(self):
        return f"{self.__class__.__name__}(type={self.type!r}, user={self.user!r})"


class StaffNotificationRecipient(models.Model):
    user = models.OneToOneField(
        User,
        related_name="staff_notification",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    staff_email = models.EmailField(unique=True, blank=True, null=True)
    active = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ("staff_email",)

    def get_email(self):
        return self.user.email if self.user else self.staff_email


class MFSAccountType(models.Model):
    name = models.CharField(max_length=63, null=False)
    code = models.CharField(max_length=15, null=False, unique=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)


class SessionLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='user_sessions', null=True,
                             on_delete=models.SET_NULL)

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)


def check_profile_matches(total, profile):
    total_orders = total[1]
    total_transaction = total[0]
    if total_orders >= profile.total_orders and total_transaction >= profile.total_transaction:
        return profile
    else:
        return None


class GroupHierarchy(models.Model):
    parent = models.OneToOneField(Group, related_name='parent_group', null=True, on_delete=models.CASCADE)
    child = models.ForeignKey(
        Group, blank=True, related_name="child_group", null=True, on_delete=models.CASCADE
    )
    has_txn = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return "%s > %s" % (self.parent, self.child)

    class Meta:
        ordering = ('-created',)


def dfs(visited, graph, node):
    if node not in visited:
        visited.append(node)
        for neighbour in graph[node]:
            dfs(visited, graph, neighbour)


def get_hierarchy(group_id, parent=False):
    graph = {}
    visited = []
    all_groups = Group.objects.all()
    records = GroupHierarchy.objects.all()

    if parent:
        for group in all_groups:
            parent_map = []
            group_records = records.filter(child=group)
            if group_records:
                for gr in group_records:
                    parent_map.append(gr.parent.id)
                graph[gr.child.id] = parent_map
            else:
                graph[group.id] = parent_map

    else:
        for group in all_groups:
            child_map = []
            group_records = records.filter(parent=group)
            if group_records:
                for gr in group_records:
                    if gr.child_id:
                        child_map.append(gr.child_id)
                graph[gr.parent.id] = child_map
            else:
                graph[group.id] = child_map

    dfs(visited, graph, group_id)

    return visited


auditlog.register(User, exclude_fields=['password'])
auditlog.register(Address)
auditlog.register(UserRequest)
auditlog.register(Group)
auditlog.register(GroupHierarchy)
