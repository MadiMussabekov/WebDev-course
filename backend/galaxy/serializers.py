import re

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import GRID_MAX_COLUMN, GRID_MAX_ROW, Climate, Film, Person, Planet, Region, Species, Starship, Terrain

GRID_SQUARE_RE = re.compile(r"^\s*([A-Za-z])\s*-?\s*(\d{1,2})\s*$")


# --- Relation fields ---------------------------------------------------------

@extend_schema_field(
    {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "name": {"type": "string"}, "slug": {"type": "string"}},
        "description": "Written as an integer id, read back as a summary object.",
    }
)
class SummaryRelatedField(serializers.PrimaryKeyRelatedField):
    """Accepts a primary key on write and returns {id, name, slug} on read."""

    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        name = getattr(value, "name", None) or getattr(value, "title", "")
        return {"id": value.pk, "name": name, "slug": value.slug}


@extend_schema_field({"type": "string"})
class GetOrCreateNameField(serializers.SlugRelatedField):
    """Lookup-table value written by name; unknown names are created on the fly."""

    def __init__(self, **kwargs):
        super().__init__(slug_field="name", **kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, str) or not data.strip():
            self.fail("invalid")
        obj, _ = self.get_queryset().get_or_create(name=data.strip().lower())
        return obj


@extend_schema_field(OpenApiTypes.STR)
class GridSquareField(serializers.Field):
    """Galactic grid square such as "R-16", stored as grid_x / grid_y."""

    default_error_messages = {
        "invalid": f'Use a grid square like "R-16": column A-{chr(64 + GRID_MAX_COLUMN)}, row 1-{GRID_MAX_ROW}.',
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("source", "*")
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def to_representation(self, planet):
        return planet.grid_square

    def to_internal_value(self, data):
        if data in (None, ""):
            return {"grid_x": None, "grid_y": None}
        match = GRID_SQUARE_RE.match(str(data))
        if not match:
            self.fail("invalid")
        x, y = ord(match.group(1).upper()) - 64, int(match.group(2))
        if not (1 <= y <= GRID_MAX_ROW):
            self.fail("invalid")
        return {"grid_x": x, "grid_y": y}

    def validate_empty_values(self, data):
        # null is a meaningful value here ("uncharted"), so let it reach to_internal_value.
        if data is None:
            return False, data
        return super().validate_empty_values(data)


# --- Lookup tables -----------------------------------------------------------

class RegionSerializer(serializers.ModelSerializer):
    planet_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Region
        fields = ["id", "name", "slug", "description", "order", "planet_count"]


class ClimateSerializer(serializers.ModelSerializer):
    planet_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Climate
        fields = ["id", "name", "planet_count"]


class TerrainSerializer(serializers.ModelSerializer):
    planet_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Terrain
        fields = ["id", "name", "planet_count"]


# --- Main resources ----------------------------------------------------------

class PlanetSerializer(serializers.ModelSerializer):
    region = SummaryRelatedField(queryset=Region.objects.all(), required=False, allow_null=True)
    climates = GetOrCreateNameField(many=True, queryset=Climate.objects.all(), required=False)
    terrains = GetOrCreateNameField(many=True, queryset=Terrain.objects.all(), required=False)
    grid_square = GridSquareField(help_text='Galactic grid square, e.g. "R-16". null = uncharted.')
    resident_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Planet
        fields = [
            "id", "name", "slug", "region", "grid_square", "grid_x", "grid_y",
            "climates", "terrains", "rotation_period", "orbital_period", "diameter",
            "gravity", "surface_water", "population", "resident_count", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "grid_x", "grid_y", "created_at", "updated_at"]


class SpeciesSerializer(serializers.ModelSerializer):
    homeworld = SummaryRelatedField(queryset=Planet.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Species
        fields = [
            "id", "name", "slug", "classification", "designation", "average_height",
            "average_lifespan", "language", "skin_colors", "hair_colors", "eye_colors",
            "homeworld", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


class PersonSerializer(serializers.ModelSerializer):
    homeworld = SummaryRelatedField(queryset=Planet.objects.all(), required=False, allow_null=True)
    species = SummaryRelatedField(many=True, queryset=Species.objects.all(), required=False)
    starships = SummaryRelatedField(many=True, queryset=Starship.objects.all(), required=False)

    class Meta:
        model = Person
        fields = [
            "id", "name", "slug", "birth_year", "gender", "height", "mass", "hair_color",
            "skin_color", "eye_color", "homeworld", "species", "starships", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


class StarshipSerializer(serializers.ModelSerializer):
    pilots = SummaryRelatedField(many=True, queryset=Person.objects.all(), required=False)

    class Meta:
        model = Starship
        fields = [
            "id", "name", "slug", "model", "manufacturer", "starship_class", "hyperdrive_rating",
            "mglt", "max_atmosphering_speed", "length", "crew", "passengers", "cargo_capacity",
            "consumables", "cost_in_credits", "pilots", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


class FilmSerializer(serializers.ModelSerializer):
    planets = SummaryRelatedField(many=True, queryset=Planet.objects.all(), required=False)
    characters = SummaryRelatedField(many=True, queryset=Person.objects.all(), required=False)
    species = SummaryRelatedField(many=True, queryset=Species.objects.all(), required=False)
    starships = SummaryRelatedField(many=True, queryset=Starship.objects.all(), required=False)

    class Meta:
        model = Film
        fields = [
            "id", "title", "slug", "episode_id", "director", "producer", "release_date",
            "opening_crawl", "planets", "characters", "species", "starships", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


# --- Lightweight list items for nested planet endpoints ----------------------

class PersonBriefSerializer(serializers.ModelSerializer):
    species = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")

    class Meta:
        model = Person
        fields = ["id", "name", "slug", "birth_year", "gender", "species"]


class SpeciesBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = ["id", "name", "slug", "classification", "language"]


class FilmBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Film
        fields = ["id", "title", "slug", "episode_id", "release_date"]


class NearbyPlanetSerializer(serializers.ModelSerializer):
    grid_square = serializers.CharField(read_only=True)
    region = serializers.CharField(source="region.name", default=None, read_only=True)
    grid_distance = serializers.SerializerMethodField()
    light_years = serializers.SerializerMethodField()

    class Meta:
        model = Planet
        fields = ["id", "name", "slug", "region", "grid_square", "grid_distance", "light_years"]

    def _route(self, planet):
        from .services.navigation import plot_route

        return plot_route(self.context["origin"], planet)

    def get_grid_distance(self, planet) -> float:
        return self._route(planet).as_dict()["grid_squares"]

    def get_light_years(self, planet) -> int:
        return self._route(planet).light_years


class PlanetSpeciesSerializer(serializers.Serializer):
    planet = serializers.DictField()
    native_species = SpeciesBriefSerializer(many=True)
    resident_species = serializers.ListField(child=serializers.DictField())


class DistanceSerializer(serializers.Serializer):
    origin = serializers.DictField()
    destination = serializers.DictField()
    distance = serializers.DictField()
    travel = serializers.DictField(required=False)
