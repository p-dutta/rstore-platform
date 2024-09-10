from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from ....account.utils import create_superuser, create_managers, import_managers, add_replace_managers, \
    replace_removed_managers, create_opmanagers
from ...utils.random_data import (
    create_permission_groups,
    create_shipping_zones,
    create_warehouses, create_product_types,
    rename_permission_start_names
)


class Command(BaseCommand):
    help = "Populate database with test objects"
    placeholders_dir = "saleor/static/placeholders/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--createsuperuser",
            action="store_true",
            dest="createsuperuser",
            default=False,
            help="Create admin account",
        )
        parser.add_argument(
            "--createopmanagers",
            action="store_true",
            dest="createopmanagers",
            default=False,
            help="Create operational manager accounts",
        )
        parser.add_argument(
            "--createmanagers",
            action="store_true",
            dest="createmanagers",
            default=False,
            help="Create manager accounts",
        )
        parser.add_argument(
            "--importmanagers",
            action="store_true",
            dest="importmanagers",
            default=False,
            help="Import manager accounts",
        )
        parser.add_argument(
            "--addreplacemanagers",
            action="store_true",
            dest="addreplacemanagers",
            default=False,
            help="Import manager accounts",
        )
        parser.add_argument(
            "--replaceremovedmanagers",
            action="store_true",
            dest="replaceremovedmanagers",
            default=False,
            help="Import manager accounts",
        )
        parser.add_argument(
            "--skipsequencereset",
            action="store_true",
            dest="skipsequencereset",
            default=False,
            help="Don't reset SQL sequences that are out of sync.",
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

    def sequence_reset(self):
        """Run a SQL sequence reset on all saleor.* apps.

        When a value is manually assigned to an auto-incrementing field
        it doesn't update the field's sequence, which might cause a conflict
        later on.
        """
        commands = StringIO()
        for app in apps.get_app_configs():
            if "saleor" in app.name:
                call_command(
                    "sqlsequencereset", app.label, stdout=commands, no_color=True
                )
        with connection.cursor() as cursor:
            cursor.execute(commands.getvalue())

    def handle(self, *args, **options):
        self.make_database_faster()
        for msg in create_shipping_zones():
            self.stdout.write(msg)
        create_warehouses()
        self.stdout.write("Created warehouses")
        create_product_types()
        self.stdout.write("Created default product type")
        for msg in create_permission_groups():
            self.stdout.write(msg)

        if options["createsuperuser"]:
            for msg in create_superuser():
                self.stdout.write(msg)

        if options["importmanagers"]:
            for msg in import_managers():
                self.stdout.write(msg)

        if options["createmanagers"]:
            for msg in create_managers():
                self.stdout.write(msg)

        if options["createopmanagers"]:
            for msg in create_opmanagers():
                self.stdout.write(msg)

        if options["addreplacemanagers"]:
            for msg in add_replace_managers():
                self.stdout.write(msg)

        if options["replaceremovedmanagers"]:
            for msg in replace_removed_managers():
                self.stdout.write(msg)

        if not options["skipsequencereset"]:
            self.sequence_reset()

        permissions_updated = rename_permission_start_names()
        self.stdout.write("Updated " + str(permissions_updated) + " permission names")
