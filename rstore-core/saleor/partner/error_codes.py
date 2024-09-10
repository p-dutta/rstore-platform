from enum import Enum


class PartnerErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    DUPLICATED_INPUT_ITEM = "duplicated_input_item"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_LOGO_IMAGE = "not_logo_image"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    UNIQUE = "unique"
    CONNECTION = "connection_error"
