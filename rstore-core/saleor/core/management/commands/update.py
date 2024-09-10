from django.core.management.base import BaseCommand
from ...utils.store_data import update_phone


class Command(BaseCommand):
    help = "Update phone number"

    def handle(self, *args, **options):
        for msg in update_phone():
            self.stdout.write(msg)