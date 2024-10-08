from enum import Enum


class AccountErrorCode(Enum):
    ACTIVATE_OWN_ACCOUNT = "activate_own_account"
    ACTIVATE_SUPERUSER_ACCOUNT = "activate_superuser_account"
    DUPLICATED_INPUT_ITEM = "duplicated_input_item"
    DEACTIVATE_OWN_ACCOUNT = "deactivate_own_account"
    DEACTIVATE_SUPERUSER_ACCOUNT = "deactivate_superuser_account"
    DELETE_NON_STAFF_USER = "delete_non_staff_user"
    DELETE_OWN_ACCOUNT = "delete_own_account"
    DELETE_STAFF_ACCOUNT = "delete_staff_account"
    DELETE_SUPERUSER_ACCOUNT = "delete_superuser_account"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    INVALID_PASSWORD = "invalid_password"
    LEFT_NOT_MANAGEABLE_PERMISSION = "left_not_manageable_permission"
    INVALID_CREDENTIALS = "invalid_credentials"
    NOT_FOUND = "not_found"
    OUT_OF_SCOPE_SERVICE_ACCOUNT = "out_of_scope_service_account"
    OUT_OF_SCOPE_USER = "out_of_scope_user"
    OUT_OF_SCOPE_GROUP = "out_of_scope_group"
    OUT_OF_SCOPE_PERMISSION = "out_of_scope_permission"
    PASSWORD_ENTIRELY_NUMERIC = "password_entirely_numeric"
    PASSWORD_TOO_COMMON = "password_too_common"
    PASSWORD_TOO_SHORT = "password_too_short"
    PASSWORD_TOO_SIMILAR = "password_too_similar"
    REQUIRED = "required"
    UNIQUE = "unique"


class RequestErrorCode(Enum):
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REJECTED_REQUEST = "rejected_request"
    WRONG_APPROVER = "wrong_approver"
    REJECTION_TEXT = "rejection_reason_needed"


class PermissionGroupErrorCode(Enum):
    ASSIGN_NON_STAFF_MEMBER = "assign_non_staff_member"
    DUPLICATED_INPUT_ITEM = "duplicated_input_item"
    CANNOT_REMOVE_FROM_LAST_GROUP = "cannot_remove_from_last_group"
    LEFT_NOT_MANAGEABLE_PERMISSION = "left_not_manageable_permission"
    OUT_OF_SCOPE_PERMISSION = "out_of_scope_permission"
    OUT_OF_SCOPE_USER = "out_of_scope_user"
    REQUIRED = "required"
    UNIQUE = "unique"


class UserPermissionUpdateErrorCode(Enum):
    REMOTE_UPDATE_FAILED = "can_not_update_in_remote_server"
