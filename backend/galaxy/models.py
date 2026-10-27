"""Relational model of the Star Wars galaxy.

SWAPI stores many values as free text ("arid, temperate", "1,000", "unknown").
Here they are normalised: comma-separated lists become many-to-many lookup
tables, numbers become nullable numeric columns, and "unknown" becomes NULL.
"""
import math
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

# The galactic map is a grid of lettered columns (A-Z) and numbered rows (1-25).
GRID_MAX_COLUMN = 26
GRID_MAX_ROW = 25


class SluggedModel(models.Model):
    """Gives a model a unique, URL-friendly slug generated from its name."""

    slug_source = "name"

    slug = models.SlugField(max_length=120, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(getattr(self, self.slug_source))[:110] or "item"
        slug, n = base, 2
        manager = type(self)._default_manager
        while manager.filter(slug=slug).exclude(pk=self.pk).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug


class Region(models.Model):
    """A galactic region, ordered from the Deep Core outwards."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0, help_text="Distance rank from the galactic core.")

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Climate(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Terrain(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Planet(SluggedModel):
    name = models.CharField(max_length=100, unique=True)
    rotation_period = models.PositiveIntegerField(null=True, blank=True, help_text="Hours per day.")
    orbital_period = models.PositiveIntegerField(null=True, blank=True, help_text="Days per year.")
    diameter = models.PositiveIntegerField(null=True, blank=True, help_text="Kilometres.")
    gravity = models.CharField(max_length=60, blank=True)
    surface_water = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of the surface covered by water.",
    )
    population = models.PositiveBigIntegerField(null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name="planets")
    # Galactic grid position (e.g. "R-16" -> x=18, y=16). NULL when the location is uncharted.
    grid_x = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(GRID_MAX_COLUMN)]
    )
    grid_y = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(GRID_MAX_ROW)]
    )
    climates = models.ManyToManyField(Climate, blank=True, related_name="planets")
    terrains = models.ManyToManyField(Terrain, blank=True, related_name="planets")

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["grid_x", "grid_y"])]
        constraints = [
            # A planet is either fully charted or not charted at all.
            models.CheckConstraint(
                condition=models.Q(grid_x__isnull=True, grid_y__isnull=True)
                | models.Q(grid_x__isnull=False, grid_y__isnull=False),
                name="planet_grid_both_or_neither",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_charted(self):
        return self.grid_x is not None and self.grid_y is not None

    @property
    def grid_square(self):
        if not self.is_charted:
            return None
        return f"{chr(ord('A') + self.grid_x - 1)}-{self.grid_y}"

    def grid_distance_to(self, other):
        """Euclidean distance in grid squares, or None if either planet is uncharted."""
        if not (self.is_charted and other.is_charted):
            return None
        return math.hypot(self.grid_x - other.grid_x, self.grid_y - other.grid_y)


class Species(SluggedModel):
    name = models.CharField(max_length=100, unique=True)
    classification = models.CharField(max_length=60, blank=True)
    designation = models.CharField(max_length=60, blank=True)
    average_height = models.PositiveIntegerField(null=True, blank=True, help_text="Centimetres.")
    average_lifespan = models.PositiveIntegerField(null=True, blank=True, help_text="Years.")
    language = models.CharField(max_length=100, blank=True)
    skin_colors = models.CharField(max_length=200, blank=True)
    hair_colors = models.CharField(max_length=200, blank=True)
    eye_colors = models.CharField(max_length=200, blank=True)
    homeworld = models.ForeignKey(
        Planet, on_delete=models.SET_NULL, null=True, blank=True, related_name="native_species"
    )

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "species"

    def __str__(self):
        return self.name


class Person(SluggedModel):
    name = models.CharField(max_length=100)
    height = models.PositiveIntegerField(null=True, blank=True, help_text="Centimetres.")
    mass = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Kilograms.")
    hair_color = models.CharField(max_length=60, blank=True)
    skin_color = models.CharField(max_length=60, blank=True)
    eye_color = models.CharField(max_length=60, blank=True)
    birth_year = models.CharField(max_length=20, blank=True, help_text="BBY/ABY relative to the Battle of Yavin.")
    gender = models.CharField(max_length=30, blank=True)
    homeworld = models.ForeignKey(
        Planet, on_delete=models.SET_NULL, null=True, blank=True, related_name="residents"
    )
    species = models.ManyToManyField(Species, blank=True, related_name="members")

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "people"

    def __str__(self):
        return self.name


class Starship(SluggedModel):
    name = models.CharField(max_length=100)
    model = models.CharField(max_length=150, blank=True)
    manufacturer = models.CharField(max_length=200, blank=True)
    starship_class = models.CharField(max_length=60, blank=True)
    cost_in_credits = models.PositiveBigIntegerField(null=True, blank=True)
    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Metres.")
    max_atmosphering_speed = models.PositiveIntegerField(null=True, blank=True)
    crew = models.CharField(max_length=60, blank=True)
    passengers = models.CharField(max_length=60, blank=True)
    cargo_capacity = models.PositiveBigIntegerField(null=True, blank=True, help_text="Kilograms.")
    consumables = models.CharField(max_length=60, blank=True)
    hyperdrive_rating = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.1"))],
        help_text="Hyperdrive class - lower is faster (the Millennium Falcon is 0.5).",
    )
    mglt = models.PositiveIntegerField(null=True, blank=True, help_text="Megalights per hour.")
    pilots = models.ManyToManyField(Person, blank=True, related_name="starships")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Film(SluggedModel):
    slug_source = "title"

    title = models.CharField(max_length=100, unique=True)
    episode_id = models.PositiveSmallIntegerField(unique=True)
    opening_crawl = models.TextField(blank=True)
    director = models.CharField(max_length=100, blank=True)
    producer = models.CharField(max_length=200, blank=True)
    release_date = models.DateField(null=True, blank=True)
    planets = models.ManyToManyField(Planet, blank=True, related_name="films")
    characters = models.ManyToManyField(Person, blank=True, related_name="films")
    species = models.ManyToManyField(Species, blank=True, related_name="films")
    starships = models.ManyToManyField(Starship, blank=True, related_name="films")

    class Meta:
        ordering = ["episode_id"]

    def __str__(self):
        return f"Episode {self.episode_id}: {self.title}"
