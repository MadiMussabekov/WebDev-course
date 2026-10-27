from django.core.management import call_command
from django.core.management.base import BaseCommand

from galaxy.models import Planet

FIXTURE = "galaxy_seed"


class Command(BaseCommand):
    help = (
        "Load the SWAPI snapshot (galaxy/fixtures/galaxy_seed.json) into the database. "
        "Skipped when data already exists unless --force is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Reload even if planets already exist.")

    def handle(self, *args, force=False, verbosity=1, **options):
        if Planet.objects.exists() and not force:
            if verbosity:
                self.stdout.write("Galaxy already seeded - skipping.")
            return
        call_command("loaddata", FIXTURE, verbosity=0)
        if verbosity:
            self.stdout.write(self.style.SUCCESS(f"Galaxy seeded: {Planet.objects.count()} planets loaded."))
