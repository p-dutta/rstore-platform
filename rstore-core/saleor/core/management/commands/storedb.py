from django.core.management.base import BaseCommand
from ...utils.store_data import create_districts, create_thanas, create_mfs


class Command(BaseCommand):
    help = "Populate District and Thana"

    def handle(self, *args, **options):

        for msg in create_districts():
            self.stdout.write(msg)

        for msg in create_thanas():
            self.stdout.write(msg)

        for msg in create_mfs():
            self.stdout.write(msg)
