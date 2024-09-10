from enum import Enum


class NoticeErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    UNIQUE = "unique"
    NAME_REQUIRED = "name_required"
    RECIPIENT_REQUIRED = "recipient_required"
    NOT_FOUND = "not_found"


class NoticeDocumentErrorCode(Enum):
    INVALID = "invalid"
    REQUIRED = "required"
