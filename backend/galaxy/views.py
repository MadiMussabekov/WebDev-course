from django.db import connection
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import serializers as s
from .filters import PersonFilter, PlanetFilter, SpeciesFilter, StarshipFilter
from .models import Climate, Film, Person, Planet, Region, Species, Starship, Terrain
from .services import navigation

LOOKUP_PARAM = OpenApiParameter(
    "id", str, OpenApiParameter.PATH,
    description="Numeric id, slug (`yavin-iv`) or exact name (`Yavin IV`, case-insensitive).",
)


def find_by_identifier(queryset, identifier, name_field="name"):
    """Resolve a numeric id, a slug or a case-insensitive name to a single object."""
    identifier = str(identifier).strip()
    if identifier.isdigit():
        lookup = Q(pk=int(identifier))
    else:
        lookup = Q(slug__iexact=identifier) | Q(**{f"{name_field}__iexact": identifier})
    obj = queryset.filter(lookup).first()
    if obj is None:
        raise Http404(f"No {queryset.model._meta.verbose_name} matches '{identifier}'.")
    return obj


class FlexibleLookupMixin:
    """Lets /resource/{id}/ accept an id, slug or name."""

    lookup_value_regex = "[^/]+"
    name_field = "name"

    def get_object(self):
        identifier = self.kwargs[self.lookup_url_kwarg or self.lookup_field]
        obj = find_by_identifier(self.get_queryset(), identifier, self.name_field)
        self.check_object_permissions(self.request, obj)
        return obj


def crud_docs(resource, plural):
    """Shared Swagger summaries for the standard CRUD actions."""
    detail = {"parameters": [LOOKUP_PARAM]}
    return extend_schema_view(
        list=extend_schema(summary=f"List {plural}", tags=[plural.title()]),
        create=extend_schema(summary=f"Create a {resource}", tags=[plural.title()]),
        retrieve=extend_schema(summary=f"Get a {resource} by id, slug or name", tags=[plural.title()], **detail),
        update=extend_schema(summary=f"Replace a {resource}", tags=[plural.title()], **detail),
        partial_update=extend_schema(summary=f"Partially update a {resource}", tags=[plural.title()], **detail),
        destroy=extend_schema(summary=f"Delete a {resource}", tags=[plural.title()], **detail),
    )


# --- Planets -------------------------------------------------------------------

@crud_docs("planet", "planets")
class PlanetViewSet(FlexibleLookupMixin, viewsets.ModelViewSet):
    serializer_class = s.PlanetSerializer
    filterset_class = PlanetFilter
    search_fields = ["name", "climates__name", "terrains__name"]
    ordering_fields = ["id", "name", "population", "diameter", "surface_water", "resident_count"]

    def get_queryset(self):
        return (
            Planet.objects.select_related("region")
            .prefetch_related("climates", "terrains")
            .annotate(resident_count=Count("residents", distinct=True))
            .order_by("id")
        )

    @extend_schema(
        summary="Notable people born on a planet", tags=["Planets"], parameters=[LOOKUP_PARAM],
        responses=s.PersonBriefSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def people(self, request, pk=None):
        planet = self.get_object()
        residents = planet.residents.prefetch_related("species").order_by("name")
        return Response(s.PersonBriefSerializer(residents, many=True).data)

    @extend_schema(
        summary="Species native to or living on a planet", tags=["Planets"], parameters=[LOOKUP_PARAM],
        description=(
            "`native_species` are species whose homeworld is this planet. `resident_species` "
            "groups the planet's residents by species, with a head count."
        ),
        responses=s.PlanetSpeciesSerializer,
    )
    @action(detail=True, methods=["get"])
    def species(self, request, pk=None):
        planet = self.get_object()
        native = planet.native_species.order_by("name")
        resident = (
            Species.objects.filter(members__homeworld=planet)
            .annotate(residents=Count("members", filter=Q(members__homeworld=planet), distinct=True))
            .order_by("-residents", "name")
        )
        return Response({
            "planet": {"id": planet.pk, "name": planet.name, "slug": planet.slug},
            "native_species": s.SpeciesBriefSerializer(native, many=True).data,
            "resident_species": [
                {"id": sp.pk, "name": sp.name, "slug": sp.slug, "residents": sp.residents} for sp in resident
            ],
        })

    @extend_schema(
        summary="Films a planet appears in", tags=["Planets"], parameters=[LOOKUP_PARAM],
        responses=s.FilmBriefSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def films(self, request, pk=None):
        planet = self.get_object()
        return Response(s.FilmBriefSerializer(planet.films.all(), many=True).data)

    @extend_schema(
        summary="Closest charted planets", tags=["Navigation"], parameters=[
            LOOKUP_PARAM,
            OpenApiParameter("limit", int, description="How many neighbours to return (1-50, default 5)."),
        ],
        responses={200: s.NearbyPlanetSerializer(many=True), 422: OpenApiResponse(description="Planet is uncharted.")},
    )
    @action(detail=True, methods=["get"])
    def nearest(self, request, pk=None):
        planet = self.get_object()
        try:
            limit = min(max(int(request.query_params.get("limit", 5)), 1), 50)
        except ValueError:
            raise ValidationError({"limit": "Must be an integer."})
        try:
            neighbours = navigation.nearest_planets(planet, Planet.objects.select_related("region"))[:limit]
        except navigation.NavigationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        data = s.NearbyPlanetSerializer(neighbours, many=True, context={"origin": planet}).data
        return Response(data)

    @extend_schema(
        summary="Distance between two planets", tags=["Navigation"],
        description=(
            "Computes the straight-line hyperspace distance between two charted planets using "
            "their galactic grid coordinates. Pass `starship` to also estimate the travel time "
            "based on its hyperdrive rating."
        ),
        parameters=[
            OpenApiParameter("from", str, required=True, description="Origin planet id, slug or name."),
            OpenApiParameter("to", str, required=True, description="Destination planet id, slug or name."),
            OpenApiParameter("starship", str, description="Optional starship id, slug or name."),
        ],
        responses={
            200: s.DistanceSerializer,
            400: OpenApiResponse(description="Missing query parameters."),
            404: OpenApiResponse(description="Planet or starship not found."),
            422: OpenApiResponse(description="Route cannot be plotted (uncharted planet, no hyperdrive...)."),
        },
    )
    @action(detail=False, methods=["get"])
    def distance(self, request):
        missing = [p for p in ("from", "to") if not request.query_params.get(p)]
        if missing:
            raise ValidationError({p: "This query parameter is required." for p in missing})
        planets = Planet.objects.select_related("region")
        origin = find_by_identifier(planets, request.query_params["from"])
        destination = find_by_identifier(planets, request.query_params["to"])
        try:
            route = navigation.plot_route(origin, destination)
            payload = {
                "origin": self._planet_position(origin),
                "destination": self._planet_position(destination),
                "distance": route.as_dict(),
            }
            if ship_id := request.query_params.get("starship"):
                ship = find_by_identifier(Starship.objects.all(), ship_id)
                payload["travel"] = navigation.travel_time(route, ship)
        except navigation.NavigationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(payload)

    @staticmethod
    def _planet_position(planet):
        return {
            "id": planet.pk, "name": planet.name, "slug": planet.slug,
            "region": planet.region.name if planet.region else None, "grid_square": planet.grid_square,
        }


# --- Other resources -----------------------------------------------------------

@crud_docs("species", "species")
class SpeciesViewSet(FlexibleLookupMixin, viewsets.ModelViewSet):
    queryset = Species.objects.select_related("homeworld").order_by("id")
    serializer_class = s.SpeciesSerializer
    filterset_class = SpeciesFilter
    search_fields = ["name", "classification", "language"]
    ordering_fields = ["id", "name", "average_height", "average_lifespan"]

    @extend_schema(
        summary="Known members of a species", tags=["Species"], parameters=[LOOKUP_PARAM],
        responses=s.PersonBriefSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def people(self, request, pk=None):
        species = self.get_object()
        members = species.members.prefetch_related("species").order_by("name")
        return Response(s.PersonBriefSerializer(members, many=True).data)


@crud_docs("person", "people")
class PersonViewSet(FlexibleLookupMixin, viewsets.ModelViewSet):
    queryset = Person.objects.select_related("homeworld").prefetch_related("species", "starships").order_by("id")
    serializer_class = s.PersonSerializer
    filterset_class = PersonFilter
    search_fields = ["name"]
    ordering_fields = ["id", "name", "height", "mass"]


@crud_docs("starship", "starships")
class StarshipViewSet(FlexibleLookupMixin, viewsets.ModelViewSet):
    queryset = Starship.objects.prefetch_related("pilots").order_by("id")
    serializer_class = s.StarshipSerializer
    filterset_class = StarshipFilter
    search_fields = ["name", "model", "manufacturer"]
    ordering_fields = ["id", "name", "hyperdrive_rating", "length", "cost_in_credits"]


@crud_docs("film", "films")
class FilmViewSet(FlexibleLookupMixin, viewsets.ModelViewSet):
    queryset = Film.objects.prefetch_related("planets", "characters", "species", "starships").order_by("episode_id")
    serializer_class = s.FilmSerializer
    name_field = "title"
    filterset_fields = ["director"]
    search_fields = ["title", "director", "opening_crawl"]
    ordering_fields = ["episode_id", "release_date", "title"]


@extend_schema_view(
    list=extend_schema(summary="List galactic regions", tags=["Reference data"]),
    retrieve=extend_schema(summary="Get a region by id or slug", tags=["Reference data"], parameters=[LOOKUP_PARAM]),
)
class RegionViewSet(FlexibleLookupMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.annotate(planet_count=Count("planets")).order_by("order")
    serializer_class = s.RegionSerializer
    pagination_class = None

    @extend_schema(
        summary="Planets in a region", tags=["Reference data"], parameters=[LOOKUP_PARAM],
        responses=s.PlanetSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def planets(self, request, pk=None):
        region = self.get_object()
        planets = (
            region.planets.select_related("region").prefetch_related("climates", "terrains")
            .annotate(resident_count=Count("residents", distinct=True)).order_by("name")
        )
        return Response(s.PlanetSerializer(planets, many=True).data)


class LookupTableViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = None

    def get_object(self):
        queryset = self.get_queryset()
        identifier = self.kwargs["pk"]
        obj = queryset.filter(Q(pk=identifier) if identifier.isdigit() else Q(name__iexact=identifier)).first()
        if obj is None:
            raise Http404
        return obj


@extend_schema_view(
    list=extend_schema(summary="List climates with planet counts", tags=["Reference data"]),
    retrieve=extend_schema(summary="Get a climate", tags=["Reference data"]),
)
class ClimateViewSet(LookupTableViewSet):
    queryset = Climate.objects.annotate(planet_count=Count("planets")).order_by("-planet_count", "name")
    serializer_class = s.ClimateSerializer
    lookup_value_regex = "[^/]+"


@extend_schema_view(
    list=extend_schema(summary="List terrains with planet counts", tags=["Reference data"]),
    retrieve=extend_schema(summary="Get a terrain", tags=["Reference data"]),
)
class TerrainViewSet(LookupTableViewSet):
    queryset = Terrain.objects.annotate(planet_count=Count("planets")).order_by("-planet_count", "name")
    serializer_class = s.TerrainSerializer
    lookup_value_regex = "[^/]+"


# --- Service endpoints -----------------------------------------------------------

@extend_schema(summary="Galaxy-wide statistics", tags=["Service"], responses={200: dict})
@api_view(["GET"])
def galaxy_stats(request):
    planet_totals = Planet.objects.aggregate(
        total_population=Sum("population"), average_diameter=Avg("diameter"), largest_diameter=Max("diameter"),
    )
    most_populous = Planet.objects.filter(population__isnull=False).order_by("-population")[:5]
    fastest = Starship.objects.filter(hyperdrive_rating__isnull=False).order_by("hyperdrive_rating", "name")[:5]
    busiest = Planet.objects.annotate(n=Count("residents")).filter(n__gt=0).order_by("-n", "name")[:5]
    return Response({
        "counts": {
            "planets": Planet.objects.count(),
            "charted_planets": Planet.objects.filter(grid_x__isnull=False).count(),
            "species": Species.objects.count(),
            "people": Person.objects.count(),
            "starships": Starship.objects.count(),
            "films": Film.objects.count(),
        },
        "planets": {
            "total_population": planet_totals["total_population"],
            "average_diameter_km": round(planet_totals["average_diameter"] or 0),
            "largest_diameter_km": planet_totals["largest_diameter"],
            "most_populous": [{"name": p.name, "slug": p.slug, "population": p.population} for p in most_populous],
            "most_notable_residents": [{"name": p.name, "slug": p.slug, "residents": p.n} for p in busiest],
        },
        "fastest_starships": [
            {"name": sh.name, "slug": sh.slug, "hyperdrive_rating": sh.hyperdrive_rating} for sh in fastest
        ],
    })


@extend_schema(summary="Health check (API + database)", tags=["Service"], responses={200: dict, 503: dict})
@api_view(["GET"])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 - any DB failure means unhealthy
        return Response({"status": "error", "database": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"status": "ok", "database": "up"})
