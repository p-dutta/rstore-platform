from enum import Enum


class NotificationErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    UNIQUE = "unique"
    TARGET_REQUIRED = "target_required"
    RECIPIENT_REQUIRED = "recipient_required"
    NOT_FOUND = "not_found"


class AnnouncementErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    UNIQUE = "unique"
    TARGET_REQUIRED = "target_required"
    RECIPIENT_REQUIRED = "recipient_required"
    NOT_FOUND = "not_found"


class SegmentErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    UNIQUE = "unique"


class NotificationMetaErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    UNIQUE = "unique"
