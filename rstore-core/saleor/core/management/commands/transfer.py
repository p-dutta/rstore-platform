from django.core.management.base import BaseCommand

from saleor.account.utils import transfer_responsibility, revoke_access


class Command(BaseCommand):
    help = "Populate database with test objects"
    placeholders_dir = "saleor/static/placeholders/"

    def add_arguments(self, parser):

        parser.add_argument('--old_email', action='store', type=str, help='Enter Old account email address', )
        parser.add_argument('--email', action='store', type=str, help='Enter new email', )
        parser.add_argument('--phone', action='store', type=str, help='Enter new Phone', )
        parser.add_argument('--group', action='store', type=str, help='Enter Account group', )
        parser.add_argument('--first_name', action='store', type=str, help='Enter First Name', )
        parser.add_argument('--last_name', action='store', type=str, help='Enter Last Name', )
        parser.add_argument('--thana', action='store', type=str, help='Enter Thana Name', )

        parser.add_argument(
            "--revoke",
            action="store_true",
            dest="revoke",
            default=False,
            help="Revoke access from old account",
        )

    def handle(self, *args, **options):
        old_email = options['old_email']
        email = options['email']
        phone = options['phone']
        group = options['group']
        first_name = options['first_name']
        last_name = options['last_name']
        thana = options['thana']

        for msg in transfer_responsibility(email, phone, group, thana, first_name, last_name, old_email):
            self.stdout.write(msg)

        if options["revoke"]:
            for msg in revoke_access(old_email):
                self.stdout.write(msg)
