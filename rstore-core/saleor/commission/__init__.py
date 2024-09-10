class RuleType:
    REGULAR = "regular"
    CAMPAIGN = "campaign"

    CHOICES = [
        (REGULAR, "Regular"),
        (CAMPAIGN, "Campaign"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class RuleCategory:
    REALTIME = "realtime"
    CONSOLIDATE = "consolidate"

    CHOICES = [
        (REALTIME, "Realtime"),
        (CONSOLIDATE, "Consolidate"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class CommissionType:
    ABSOLUTE = "absolute"
    PERCENTAGE = "percentage"

    CHOICES = [
        (ABSOLUTE, "Absolute"),
        (PERCENTAGE, "Percentage"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class CommissionCategory:
    FIXED = "fixed"
    RANGE = "range"
    PRODUCT = "product"

    CHOICES = [
        (FIXED, "Fixed"),
        (RANGE, "Range"),
        (PRODUCT, "Product"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys


class CommissionStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DONE = "done"

    CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (DONE, "Done"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys
