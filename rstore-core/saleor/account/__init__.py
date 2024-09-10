class CustomerEvents:
    """The different customer event types."""

    # Account related events
    ACCOUNT_CREATED = "account_created"
    PASSWORD_RESET_LINK_SENT = "password_reset_link_sent"
    PASSWORD_RESET = "password_reset"
    PASSWORD_CHANGED = "password_changed"
    EMAIL_CHANGE_REQUEST = "email_changed_request"
    EMAIL_CHANGED = "email_changed"

    # Order related events
    PLACED_ORDER = "placed_order"  # created an order
    NOTE_ADDED_TO_ORDER = "note_added_to_order"  # added a note to one of their orders
    DIGITAL_LINK_DOWNLOADED = "digital_link_downloaded"  # downloaded a digital good

    # Staff actions over customers events
    CUSTOMER_DELETED = "customer_deleted"  # staff user deleted a customer
    EMAIL_ASSIGNED = "email_assigned"  # the staff user assigned a email to the customer
    NAME_ASSIGNED = "name_assigned"  # the staff user added set a name to the customer
    NOTE_ADDED = "note_added"  # the staff user added a note to the customer

    CHOICES = [
        (ACCOUNT_CREATED, "The account was created"),
        (PASSWORD_RESET_LINK_SENT, "Password reset link was sent to the customer"),
        (PASSWORD_RESET, "The account password was reset"),
        (
            EMAIL_CHANGE_REQUEST,
            "The user requested to change the account's email address.",
        ),
        (PASSWORD_CHANGED, "The account password was changed"),
        (EMAIL_CHANGED, "The account email address was changed"),
        (PLACED_ORDER, "An order was placed"),
        (NOTE_ADDED_TO_ORDER, "A note was added"),
        (DIGITAL_LINK_DOWNLOADED, "A digital good was downloaded"),
        (CUSTOMER_DELETED, "A customer was deleted"),
        (NAME_ASSIGNED, "A customer's name was edited"),
        (EMAIL_ASSIGNED, "A customer's email address was edited"),
        (NOTE_ADDED, "A note was added to the customer"),
    ]


class Qualification:
    BELOW_SSC = "below_ssc"
    SSC = "ssc"
    HSC = "hsc"
    GRADUATE = "graduate"
    POST_GRADUATE = "post_graduate"
    DIPLOMA = "diploma"

    CHOICES = [
        (BELOW_SSC, "Below SSC"),
        (SSC, "SSC"),
        (HSC, "HSC"),
        (GRADUATE, "Graduate"),
        (POST_GRADUATE, "Post Graduate or Higher"),
        (DIPLOMA, "Diploma"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class ShopSize:
    LESS_THAN_50 = "less_than_50"
    BETWEEN_50_100 = "between_50_100"
    BETWEEN_100_200 = "between_100_200"
    GREATER_THAN_200 = "greater_than_200"

    CHOICES = [
        (LESS_THAN_50, "Less than 50 sq.ft"),
        (BETWEEN_50_100, "50-100 sq.ft"),
        (BETWEEN_100_200, "100-200 sq.ft"),
        (GREATER_THAN_200, "Over 200 Sq.ft")
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class ShopType:
    STRUCTURED = "structured"
    SEMI_STRUCTURED = "semi_structured"
    UNSTRUCTURED = "unstructured"

    CHOICES = [
        (STRUCTURED, "Structured"),
        (SEMI_STRUCTURED, "Semi-structured"),
        (UNSTRUCTURED, "Unstructured"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class EmployeeCount:
    ZERO = "0"
    ONE = "1"
    TWO = "2"
    TWO_PLUS = "2_plus"

    CHOICES = [
        (ZERO, "0"),
        (ONE, "1"),
        (TWO, "2"),
        (TWO_PLUS, "More than 2"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class Gender:
    M = "m"
    F = "f"

    CHOICES = [
        (M, "Male"),
        (F, "Female"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class UserApprovalRequest:
    REJECTED = "rejected"
    PENDING = "pending"
    APPROVED = "approved"

    CHOICES = [
        (REJECTED, "Rejected"),
        (PENDING, "Pending"),
        (APPROVED, "approved"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class UserApproval:
    INITIAL_SUBMISSION = "initial_submission"
    PENDING_KYC = "pending_kyc"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"

    CHOICES = [
        (INITIAL_SUBMISSION, "Initial Submission"),
        (PENDING_KYC, "Pending KYC"),
        (PENDING_APPROVAL, "Pending Approval"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class DocumentType:
    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"

    CHOICES = [
        (PDF, "pdf"),
        (PNG, "png"),
        (JPG, "jpg"),
        (JPEG, "jpeg"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class DocumentFileTag:
    AVATAR = "avatar"
    NID_FRONT = "nid_front"
    NID_BACK = "nid_back"
    SHOP_INSIDE = "shop_inside"
    SHOP_FRONT = "shop_front"
    TRADE_LICENCE_PHOTO = "trade_license_photo"

    CHOICES = [
        (AVATAR, "avatar"),
        (NID_FRONT, "nid_front"),
        (NID_BACK, "nid_back"),
        (SHOP_INSIDE, "shop_inside"),
        (SHOP_FRONT, "shop_front"),
        (TRADE_LICENCE_PHOTO, "trade_license_photo"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


group_hierarchy = {
    'admin': 'cm',
    'cm': 'dcm',
    'dcm': 'dco',
    'dco': 'agent'
}

GROUP_SEQUENCE = ("agent", "dco", "dcm", "cm", "admin")

