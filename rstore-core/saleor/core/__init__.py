from cacheout import LRUCache

from saleor.account.adapters import KeycloakTokenAuthorizer, KeyCloakAdminConnector
from saleor.core.sms import SMSManager

admin_connector = KeyCloakAdminConnector()
token_authorizer = KeycloakTokenAuthorizer()
user_cache = LRUCache()

sms_manager = SMSManager()


class JobStatus:
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    DELETED = "deleted"

    CHOICES = [
        (PENDING, "Pending"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
        (DELETED, "Deleted"),
    ]
