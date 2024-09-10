from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Recreate saleor database"

    def recreate_database(self):
        with connection.cursor() as cursor:
            try:
                cursor.execute("DROP SCHEMA public CASCADE;")
            except OperationalError:
                yield "Database does not exist!"
            cursor.execute("CREATE SCHEMA public;")

    def handle(self, *args, **options):
        self.stdout.write("Resetting DB...")
        for msg in self.recreate_database():
            self.stdout.write(msg)
        self.stdout.write("DB has been reset!")
