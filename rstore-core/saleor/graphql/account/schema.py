import graphene
from graphene_django.filter import DjangoFilterConnectionField

from ...core.permissions import AccountPermissions, AppPermission
from ..core.fields import FilterInputConnectionField
from ..core.types import FilterInputObjectType, Permission
from ..decorators import one_of_permissions_required, permission_required
from .bulk_mutations import CustomerBulkDelete, StaffBulkDelete, UserBulkSetActive
from .deprecated.mutations_service_account import (
    ServiceAccountClearPrivateMeta,
    ServiceAccountCreate,
    ServiceAccountDelete,
    ServiceAccountTokenCreate,
    ServiceAccountTokenDelete,
    ServiceAccountUpdate,
    ServiceAccountUpdatePrivateMeta,
)
from .deprecated.resolvers import resolve_service_accounts
from .deprecated.sorters import ServiceAccountSortingInput
from .deprecated.types import ServiceAccount, ServiceAccountFilterInput
from .enums import CountryCodeEnum
from .filters import CustomerFilter, PermissionGroupFilter, StaffUserFilter, ThanaFilter, AgentRequestSearchFilter, UserCorrectionRequestSearchFilter

from .mutations.account import (
    AccountAddressCreate,
    AccountAddressDelete,
    AccountAddressUpdate,
    AccountDelete,
    AccountRegister,
    AccountRequestDeletion,
    AccountSetDefaultAddress,
    AccountUpdate,
    AccountUpdateMeta,
    ConfirmEmailChange,
    RequestEmailChange,
    SubmitKyc,
    SubmitUserCorrection,
    SaveKyc,
    RequestApproval,
    UpdateUserPermission,
    UploadDocument,
    AddRegionToUser,
    RemoveRegionFromUser,
    UploadUserCorrectionDocument, ProcessUserCorrectionRequest,
    AssignParentToUser,
    AssignApproverToUser,
    ProfileUpdate,
    CreateGroupChildMapping, CreateManager, GroupMapDelete, AgentRequestAssigneeUpdate
)
from .mutations.base import (
    ConfirmAccount,
    PasswordChange,
    RequestPasswordReset,
    SetPassword,
    UserClearMeta,
    UserUpdateMeta,
)
from .mutations.permission_group import (
    PermissionGroupCreate,
    PermissionGroupDelete,
    PermissionGroupUpdate,
)
from .mutations.staff import (
    AddressCreate,
    AddressDelete,
    AddressSetDefault,
    AddressUpdate,
    CustomerCreate,
    CustomerDelete,
    CustomerUpdate,
    StaffCreate,
    StaffDelete,
    StaffUpdate,
    UserAvatarDelete,
    UserAvatarUpdate,
    UserClearPrivateMeta,
    UserUpdatePrivateMeta,
)
from .resolvers import (
    resolve_address,
    resolve_address_validation_rules,
    resolve_customers,
    resolve_permission_groups,
    resolve_staff_users,
    resolve_user,
    resolve_districts,
    resolve_thanas,
    resolve_all_thanas,
    resolve_tuple,
    resolve_mfs_account_types,
    resolve_agent_requests,
    resolve_requested_agent,
    resolve_all_permissions,
    resolve_stores,
    resolve_user_correction_requests, resolve_user_correction_request, resolve_group_map, resolve_groups,
    resolve_user_manageable_groups, resolve_agent_request_search, resolve_user_correction_request_search
)
from .sorters import PermissionGroupSortingInput, UserSortingInput
from .types import Address, AddressValidationData, Group, User, District, Thana, TupleValue, MFSAccountType, \
    AgentRequest, UserStoreInfo, UserCorrectionRequest, GroupMap

from ...account import Qualification, ShopSize, ShopType, Gender, EmployeeCount


class CustomerFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CustomerFilter


class PermissionGroupFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = PermissionGroupFilter


class StaffUserInput(FilterInputObjectType):
    class Meta:
        filterset_class = StaffUserFilter


class AgentRequestSearchInput(FilterInputObjectType):
    class Meta:
        filterset_class = AgentRequestSearchFilter


class UserCorrectionRequestSearchInput(FilterInputObjectType):
    class Meta:
        filterset_class = UserCorrectionRequestSearchFilter


class AccountQueries(graphene.ObjectType):
    address_validation_rules = graphene.Field(
        AddressValidationData,
        description="Returns address validation rules.",
        country_code=graphene.Argument(
            CountryCodeEnum,
            description="Two-letter ISO 3166-1 country code.",
            required=True,
        ),
        country_area=graphene.Argument(
            graphene.String, description="Designation of a region, province or state."
        ),
        city=graphene.Argument(graphene.String, description="City or a town name."),
        city_area=graphene.Argument(
            graphene.String, description="Sublocality like a district."
        ),
    )
    address = graphene.Field(
        Address,
        id=graphene.Argument(
            graphene.ID, description="ID of an address.", required=True
        ),
        description="Look up an address by ID.",
    )
    customers = FilterInputConnectionField(
        User,
        filter=CustomerFilterInput(description="Filtering options for customers."),
        sort_by=UserSortingInput(description="Sort customers."),
        description="List of the shop's customers.",
    )
    permission_groups = FilterInputConnectionField(
        Group,
        filter=PermissionGroupFilterInput(
            description="Filtering options for permission groups."
        ),
        sort_by=PermissionGroupSortingInput(description="Sort permission groups."),
        description="List of permission groups.",
    )
    permission_group = graphene.Field(
        Group,
        id=graphene.Argument(
            graphene.ID, description="ID of the group.", required=True
        ),
        description="Look up permission group by ID.",
    )
    me = graphene.Field(User, description="Return the currently authenticated user.")
    staff_users = FilterInputConnectionField(
        User,
        group=graphene.String(description="Name of a specific group for staff users.", required=False),
        filter=StaffUserInput(description="Filtering options for staff users."),
        sort_by=UserSortingInput(description="Sort staff users."),
        description="List of the shop's staff users.",
    )
    service_accounts = FilterInputConnectionField(
        ServiceAccount,
        filter=ServiceAccountFilterInput(
            description="Filtering options for service accounts."
        ),
        sort_by=ServiceAccountSortingInput(description="Sort service accounts."),
        description="List of the service accounts.",
        deprecation_reason=(
            "Use the `apps` query instead. This field will be removed after 2020-07-31."
        ),
    )
    service_account = graphene.Field(
        ServiceAccount,
        id=graphene.Argument(
            graphene.ID, description="ID of the service account.", required=True
        ),
        description="Look up a service account by ID.",
        deprecation_reason=(
            "Use the `app` query instead. This field will be removed after 2020-07-31."
        ),
    )

    user = graphene.Field(
        User,
        id=graphene.Argument(graphene.ID, description="ID of the user.", required=True),
        description="Look up a user by ID.",
    )

    districts = graphene.List(
        District,
        description="Returns a list of districts"
    )

    thanas = graphene.List(
        Thana,
        district_id=graphene.Argument(graphene.ID, description="ID of the district.", required=True),
        description="Returns list of thanas under a specific district"
    )

    all_thanas = graphene.List(
        Thana,
        description="Returns list of all thanas"
    )

    mfs_account_types = graphene.List(
        MFSAccountType,
        description='List of mfs account types'
    )

    agent_requests = DjangoFilterConnectionField(
        AgentRequest,
        description="List of the agents requests.",
    )

    agent_request_search = FilterInputConnectionField(
        AgentRequest,
        filter=AgentRequestSearchInput(description="Filtering options for agent requests."),
        description="List of filtered agent requests",
    )


    requested_agent = graphene.Field(
        AgentRequest,
        id=graphene.Argument(graphene.ID, required=True),
        description="Look up an agent request by ID."
    )

    all_permissions = graphene.List(
        Permission,
        description="List of all usable permissions."
    )

    stores = FilterInputConnectionField(
        UserStoreInfo,
        district=graphene.Argument(graphene.ID, required=False),
        thana=graphene.Argument(graphene.ID, required=False),
        description="List user store details"
    )

    groups = graphene.List(
        Group,
        description="Returns a list of groups"
    )

    user_manageable_groups = graphene.List(
        Group,
        description="Returns a list of groups that can be managed by the logged in user"
    )

    def resolve_address_validation_rules(
            self, info, country_code, country_area=None, city=None, city_area=None
    ):
        return resolve_address_validation_rules(
            info,
            country_code,
            country_area=country_area,
            city=city,
            city_area=city_area,
        )

    @permission_required(AppPermission.MANAGE_APPS)
    def resolve_service_accounts(self, info, **kwargs):
        return resolve_service_accounts(info, **kwargs)

    @permission_required(AppPermission.MANAGE_APPS)
    def resolve_service_account(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, ServiceAccount)

    @permission_required(AccountPermissions.VIEW_USER)
    def resolve_customers(self, info, query=None, **kwargs):
        return resolve_customers(info, query=query, **kwargs)

    @permission_required(AccountPermissions.VIEW_STAFF)
    def resolve_permission_groups(self, info, query=None, **kwargs):
        return resolve_permission_groups(info, query=query, **kwargs)

    @permission_required(AccountPermissions.VIEW_STAFF)
    def resolve_permission_group(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, Group)

    def resolve_me(self, info):
        user = info.context.user
        return user if user.is_authenticated else None

    @permission_required(AccountPermissions.VIEW_STAFF)
    def resolve_staff_users(self, info, query=None, **kwargs):
        return resolve_staff_users(info, query=query, **kwargs)

    @permission_required(AccountPermissions.VIEW_STAFF)
    def resolve_user(self, info, id):
        return resolve_user(info, id)

    def resolve_address(self, info, id):
        return resolve_address(info, id)

    def resolve_districts(self, info):
        return resolve_districts(info)

    def resolve_thanas(self, info, district_id):
        return resolve_thanas(info, district_id)

    def resolve_all_thanas(self, info, **kwargs):
        return resolve_all_thanas(info)

    def resolve_mfs_account_types(self, info):
        return resolve_mfs_account_types()

    @one_of_permissions_required(
        [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_REQUESTS]
    )
    def resolve_agent_requests(self, info, query=None, **kwargs):
        return resolve_agent_requests(info, query=query, **kwargs)

    @one_of_permissions_required(
        [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_REQUESTS]
    )
    def resolve_agent_request_search(self, info, query=None, **kwargs):
        return resolve_agent_request_search(info, query=query, **kwargs)



    @one_of_permissions_required(
        [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_REQUESTS]
    )
    def resolve_requested_agent(self, info, query=None, **kwargs):
        return resolve_requested_agent(info, query=query, **kwargs)

    @one_of_permissions_required(
        [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_USERS]
    )
    def resolve_all_permissions(self, info):
        return resolve_all_permissions(info)

    @staticmethod
    def resolve_stores(self, info, district=None, thana=None, **kwargs):
        return resolve_stores(info, district, thana)

    @permission_required(AccountPermissions.VIEW_STAFF)
    def resolve_groups(self, info):
        return resolve_groups(info)

    @staticmethod
    def resolve_user_manageable_groups(self, info):
        return resolve_user_manageable_groups(info)


class AccountDataQueries(graphene.ObjectType):
    qualifications = graphene.List(
        TupleValue,
        description='Education qualifications'
    )

    shop_sizes = graphene.List(
        TupleValue,
        description='Shop size options'
    )

    shop_types = graphene.List(
        TupleValue,
        description='Shop types'
    )

    number_of_employees = graphene.List(
        TupleValue,
        description='Number of employees to be selected'
    )

    genders = graphene.List(
        TupleValue,
        description='Gender types'
    )

    def resolve_qualifications(self, *args):
        return resolve_tuple(Qualification.CHOICES)

    def resolve_shop_sizes(self, *args):
        return resolve_tuple(ShopSize.CHOICES)

    def resolve_shop_types(self, *args):
        return resolve_tuple(ShopType.CHOICES)

    def resolve_number_of_employees(self, *args):
        return resolve_tuple(EmployeeCount.CHOICES)

    def resolve_genders(self, *args):
        return resolve_tuple(Gender.CHOICES)


class AccountMutations(graphene.ObjectType):
    # Base mutations
    request_password_reset = RequestPasswordReset.Field()
    confirm_account = ConfirmAccount.Field()
    set_password = SetPassword.Field()
    password_change = PasswordChange.Field()
    request_email_change = RequestEmailChange.Field()
    confirm_email_change = ConfirmEmailChange.Field()

    # Account mutations
    account_address_create = AccountAddressCreate.Field()
    account_address_update = AccountAddressUpdate.Field()
    account_address_delete = AccountAddressDelete.Field()
    account_set_default_address = AccountSetDefaultAddress.Field()

    account_register = AccountRegister.Field()
    account_update = AccountUpdate.Field()
    agent_assignee_update = AgentRequestAssigneeUpdate.Field()

    create_manager = CreateManager.Field()

    profile_update = ProfileUpdate.Field()
    submit_kyc = SubmitKyc.Field()
    save_kyc = SaveKyc.Field()
    submit_user_correction = SubmitUserCorrection.Field()

    request_approval = RequestApproval.Field()
    process_user_correction_request = ProcessUserCorrectionRequest.Field()

    account_request_deletion = AccountRequestDeletion.Field()
    account_delete = AccountDelete.Field()
    assign_parent_to_user = AssignParentToUser.Field()
    assign_approver_to_user = AssignApproverToUser.Field()

    account_update_meta = AccountUpdateMeta.Field(
        deprecation_reason=(
            "Use the `updateMetadata` mutation. This field will be removed after "
            "2020-07-31."
        )
    )

    # Staff mutations
    address_create = AddressCreate.Field()
    address_update = AddressUpdate.Field()
    address_delete = AddressDelete.Field()
    address_set_default = AddressSetDefault.Field()

    customer_create = CustomerCreate.Field()
    customer_update = CustomerUpdate.Field()
    customer_delete = CustomerDelete.Field()
    customer_bulk_delete = CustomerBulkDelete.Field()

    staff_create = StaffCreate.Field()
    staff_update = StaffUpdate.Field()
    staff_delete = StaffDelete.Field()
    staff_bulk_delete = StaffBulkDelete.Field()

    user_avatar_update = UserAvatarUpdate.Field()
    user_avatar_delete = UserAvatarDelete.Field()
    user_bulk_set_active = UserBulkSetActive.Field()

    update_user_permissions = UpdateUserPermission.Field()

    user_update_metadata = UserUpdateMeta.Field(
        deprecation_reason=(
            "Use the `updateMetadata` mutation. This field will be removed after "
            "2020-07-31."
        )
    )
    user_clear_metadata = UserClearMeta.Field(
        deprecation_reason=(
            "Use the `deleteMetadata` mutation. This field will be removed after "
            "2020-07-31."
        )
    )

    user_update_private_metadata = UserUpdatePrivateMeta.Field(
        deprecation_reason=(
            "Use the `updatePrivateMetadata` mutation. This field will be removed "
            "after 2020-07-31."
        )
    )
    user_clear_private_metadata = UserClearPrivateMeta.Field(
        deprecation_reason=(
            "Use the `deletePrivateMetadata` mutation. This field will be removed "
            "after 2020-07-31."
        )
    )

    service_account_create = ServiceAccountCreate.Field(
        deprecation_reason=(
            "Use the `appCreate` mutation instead. This field will be removed after "
            "2020-07-31."
        )
    )
    service_account_update = ServiceAccountUpdate.Field(
        deprecation_reason=(
            "Use the `appUpdate` mutation instead. This field will be removed after "
            "2020-07-31."
        )
    )
    service_account_delete = ServiceAccountDelete.Field(
        deprecation_reason=(
            "Use the `appDelete` mutation instead. This field will be removed after "
            "2020-07-31."
        )
    )

    service_account_update_private_metadata = ServiceAccountUpdatePrivateMeta.Field(
        deprecation_reason=(
            "Use the `updatePrivateMetadata` mutation with App instead."
            "This field will be removed after 2020-07-31."
        )
    )
    service_account_clear_private_metadata = ServiceAccountClearPrivateMeta.Field(
        deprecation_reason=(
            "Use the `deletePrivateMetadata` mutation with App instead."
            "This field will be removed after 2020-07-31."
        )
    )

    service_account_token_create = ServiceAccountTokenCreate.Field(
        deprecation_reason=(
            "Use the `appTokenCreate` mutation instead. This field will be removed "
            "after 2020-07-31."
        )
    )
    service_account_token_delete = ServiceAccountTokenDelete.Field(
        deprecation_reason=(
            "Use the `appTokenDelete` mutation instead. This field will be removed "
            "after 2020-07-31."
        )
    )

    # Permission group mutations
    permission_group_create = PermissionGroupCreate.Field()
    permission_group_update = PermissionGroupUpdate.Field()
    permission_group_delete = PermissionGroupDelete.Field()

    # Document mutations
    upload_document = UploadDocument.Field()
    upload_user_correction_document = UploadUserCorrectionDocument.Field()

    add_user_region = AddRegionToUser.Field()
    remove_user_region = RemoveRegionFromUser.Field()

    # Group Child Mapping
    create_group_child_mapping = CreateGroupChildMapping.Field()
    delete_group_map = GroupMapDelete.Field()


class UserCorrectionQueries(graphene.ObjectType):
    user_correction_requests = FilterInputConnectionField(
        UserCorrectionRequest,
        description='List of user correction requests'
    )

    user_correction_request = graphene.Field(
        UserCorrectionRequest,
        id=graphene.ID(description="User correction request id"),
        description='A user correction requests'
    )

    
    user_correction_request_search = FilterInputConnectionField(
        UserCorrectionRequest,
        filter=UserCorrectionRequestSearchInput(description="Filtering options for User requests Correction."),
        description="List of filtered User Correction requests",
    ) 

    @permission_required(AccountPermissions.VIEW_USERCORRECTION)
    def resolve_user_correction_requests(self, info, **kwargs):
        return resolve_user_correction_requests(info, **kwargs)

    @permission_required(AccountPermissions.VIEW_USERCORRECTION)
    def resolve_user_correction_request(self, info, id, **kwargs):
        return resolve_user_correction_request(id)

    @one_of_permissions_required(
    [AccountPermissions.MANAGE_STAFF, AccountPermissions.MANAGE_REQUESTS]
    )
    def resolve_user_request_correction_search(self, info, query=None, **kwargs):
        return resolve_user_correction_request_search(info, query=query, **kwargs)

class GroupMapQueries(graphene.ObjectType):
    group_map = graphene.List(
        GroupMap,
        description="Get group map with Txn "
    )

    @permission_required(AccountPermissions.MANAGE_USERS)
    def resolve_group_map(self, info, **kwargs):
        return resolve_group_map()
