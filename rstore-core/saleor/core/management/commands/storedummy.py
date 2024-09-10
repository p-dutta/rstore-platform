from django.core.management.base import BaseCommand
from django.db import connection

from saleor.account.utils import create_dummy_users, create_dummy_sessions, create_dummy_orders, create_dummy_products


class Command(BaseCommand):
    help = "Store dummy data in database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--createdummyusers",
            action="store_true",
            dest="createdummyusers",
            default=False,
            help="Create dummy user accounts",
        )
        parser.add_argument(
            "--createdummysessions",
            action="store_true",
            dest="createdummysessions",
            default=False,
            help="Create dummy sessions",
        )
        parser.add_argument(
            "--createdummyproducts",
            action="store_true",
            dest="createdummyproducts",
            default=False,
            help="Create dummy products",
        )
        parser.add_argument(
            "--createdummyorders",
            action="store_true",
            dest="createdummyorders",
            default=False,
            help="Create dummy orders",
        )

    def make_database_faster(self):
        """Sacrifice some of the safeguards of sqlite3 for speed.

        Users are not likely to run this command in a production environment.
        They are even less likely to run it in production while using sqlite3.
        """
        if "sqlite3" in connection.settings_dict["ENGINE"]:
            cursor = connection.cursor()
            cursor.execute("PRAGMA temp_store = MEMORY;")
            cursor.execute("PRAGMA synchronous = OFF;")

    def handle(self, *args, **options):
        self.make_database_faster()

        if options["createdummyusers"]:
            for msg in create_dummy_users():
                self.stdout.write(msg)
        if options["createdummysessions"]:
            for msg in create_dummy_sessions():
                self.stdout.write(msg)
        if options["createdummyproducts"]:
            for msg in create_dummy_products():
                self.stdout.write(msg)
        if options["createdummyorders"]:
            for msg in create_dummy_orders():
                self.stdout.write(msg)
