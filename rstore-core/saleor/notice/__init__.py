class DocumentType:
    PDF = "pdf"

    CHOICES = [
        (PDF, "pdf"),
    ]

    @classmethod
    def get_keys(cls):
        keys = []
        for item in cls.CHOICES:
            keys.append(item[0])
        return keys
