class NotificationTarget:
    USER = "user"
    SEGMENT = "segment"

    CHOICES = [
        (USER, "user"),
        (SEGMENT, "segment"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class NotificationType:
    AGENT_REQUEST_SUBMITTED = "agent_request_submitted"  # user's dco / cm
    AGENT_REQUEST_PROCESSED = "agent_request_processed"  # user's self(agent)\
    KYC_SUBMITTED = "kyc_submitted"
    KYC_PROCESSED = "kyc_processed"
    PARTNER_ADDED = "partner_added"  # agent group
    TARGET_SET = "target_set"  # user
    TARGET_UPDATED = "target_updated"  # user
    RULE_SET = "rule_set"
    RULE_UPDATED = "rule_updated"
    USER_CORRECTION_REQUEST_SUBMITTED = "user_correction_request_submitted"  # user's cm
    USER_CORRECTION_REQUEST_PROCESSED = "user_correction_request_processed"  # who submitted
    NOTICE_CREATED = "notice_created"  # all
    ORDER_CREATED = "order_created"  # agent who created the order
    CHOICES = [
        (AGENT_REQUEST_SUBMITTED, "Agent request submitted"),
        (AGENT_REQUEST_PROCESSED, "Agent request processed"),
        (KYC_SUBMITTED, "KYC submitted"),
        (KYC_PROCESSED, "KYC processed"),
        (PARTNER_ADDED, "Partner added"),
        (TARGET_SET, "Target set"),
        (TARGET_UPDATED, "Target updated"),
        (RULE_SET, "Rule set"),
        (RULE_UPDATED, "Rule updated"),
        (USER_CORRECTION_REQUEST_SUBMITTED, "User correction request submitted"),
        (USER_CORRECTION_REQUEST_PROCESSED, "User correction request processed"),
        (NOTICE_CREATED, "Notice created"),
        (ORDER_CREATED, "Order created"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys
