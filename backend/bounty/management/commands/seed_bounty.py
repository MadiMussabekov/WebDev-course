from django.core.management.base import BaseCommand
from django.db import transaction

from bounty.models import HuntLog, WantedCriminal

CRIMINALS = [
    {"name": "Vicious", "nickname": "The Snake", "reward": 25000000, "difficulty": 10,
     "last_known_latitude": 40.7128, "last_known_longitude": -74.0060,
     "last_known_note": "Red Dragon syndicate tower, Mars", "armed": True, "has_crew": True, "escape_master": True},
    {"name": "Asimov Solensan", "nickname": "Red Eye", "reward": 2500000, "difficulty": 6,
     "last_known_latitude": 12.5, "last_known_longitude": 45.2,
     "last_known_note": "", "armed": True, "has_crew": False, "escape_master": False},
    {"name": None, "nickname": "Mad Pierrot", "reward": 50000000, "difficulty": 9,
     "last_known_latitude": None, "last_known_longitude": None,
     "last_known_note": "Seen near the Space Land amusement park", "armed": True, "has_crew": False,
     "escape_master": True},
    {"name": "Abdul Hakim", "nickname": "The Pickpocket", "reward": 2500, "difficulty": 4,
     "last_known_latitude": -33.8688, "last_known_longitude": 151.2093,
     "last_known_note": "Bar district, Ganymede", "armed": False, "has_crew": False, "escape_master": True},
    {"name": "Udai Taxim", "nickname": "Blackhole", "reward": 8000, "difficulty": 7,
     "last_known_latitude": 51.5074, "last_known_longitude": -0.1278,
     "last_known_note": "", "armed": True, "has_crew": True, "escape_master": False},
    {"name": None, "nickname": "Teddy Bomber", "reward": 3000000, "difficulty": 8,
     "last_known_latitude": None, "last_known_longitude": None,
     "last_known_note": "Last bomb went off at a Titan spaceport", "armed": True, "has_crew": False,
     "escape_master": True},
    {"name": "Katerina Solensan", "nickname": "Kat", "reward": 1500, "difficulty": 2,
     "last_known_latitude": 35.6762, "last_known_longitude": 139.6503,
     "last_known_note": "", "armed": False, "has_crew": True, "escape_master": False},
]

# (criminal nickname, success, notes)
HUNTS = [
    ("The Snake", False, "Ambushed at the cathedral. Barely made it out."),
    ("The Snake", False, "Syndicate guards everywhere, aborted the approach."),
    ("Red Eye", False, "Target used Red Eye and outran us on the highway."),
    ("Red Eye", True, "Captured at a gas station on the Mars-Earth gate route."),
    ("Mad Pierrot", False, "Bullets bounced off his shield. Retreated."),
    ("Mad Pierrot", False, "Lost him in the amusement park crowd."),
    ("The Pickpocket", False, "He stole my wallet and disappeared in the bar."),
    ("The Pickpocket", True, "Caught him while he was trying to sell a stolen ship part."),
    ("Blackhole", False, "Target escaped through an asteroid field."),
    ("Blackhole", False, "His crew jammed our radar."),
    ("Teddy Bomber", False, "Defused one bomb, the target got away."),
    ("Kat", True, "Turned herself in after a short chase."),
]


class Command(BaseCommand):
    help = "Fill the database with sample criminals and hunt logs. Skipped if criminals already exist."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Delete existing data and reload.")

    @transaction.atomic
    def handle(self, *args, force=False, **options):
        if WantedCriminal.objects.exists():
            if not force:
                self.stdout.write("Database already has data - skipping seed.")
                return
            WantedCriminal.objects.all().delete()  # hunt logs are removed by CASCADE

        by_nickname = {}
        for data in CRIMINALS:
            criminal = WantedCriminal.objects.create(**data)
            by_nickname[criminal.nickname] = criminal
        for nickname, success, notes in HUNTS:
            HuntLog.objects.create(criminal=by_nickname[nickname], success=success, notes=notes)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {WantedCriminal.objects.count()} criminals and {HuntLog.objects.count()} hunt logs."
        ))
