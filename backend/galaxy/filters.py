import django_filters as filters

from .models import Person, Planet, Species, Starship


class PlanetFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    climate = filters.CharFilter(field_name="climates__name", lookup_expr="iexact", distinct=True)
    terrain = filters.CharFilter(field_name="terrains__name", lookup_expr="iexact", distinct=True)
    region = filters.CharFilter(field_name="region__slug", lookup_expr="iexact")
    charted = filters.BooleanFilter(field_name="grid_x", lookup_expr="isnull", exclude=True)
    min_population = filters.NumberFilter(field_name="population", lookup_expr="gte")
    max_population = filters.NumberFilter(field_name="population", lookup_expr="lte")

    class Meta:
        model = Planet
        fields = ["name", "climate", "terrain", "region", "charted", "min_population", "max_population"]


class SpeciesFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    classification = filters.CharFilter(lookup_expr="iexact")
    homeworld = filters.CharFilter(field_name="homeworld__slug", lookup_expr="iexact")

    class Meta:
        model = Species
        fields = ["name", "classification", "designation", "homeworld"]


class PersonFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    gender = filters.CharFilter(lookup_expr="iexact")
    homeworld = filters.CharFilter(field_name="homeworld__slug", lookup_expr="iexact")
    species = filters.CharFilter(field_name="species__slug", lookup_expr="iexact", distinct=True)

    class Meta:
        model = Person
        fields = ["name", "gender", "homeworld", "species"]


class StarshipFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    starship_class = filters.CharFilter(lookup_expr="iexact")
    max_hyperdrive_rating = filters.NumberFilter(field_name="hyperdrive_rating", lookup_expr="lte")

    class Meta:
        model = Starship
        fields = ["name", "starship_class", "max_hyperdrive_rating"]
