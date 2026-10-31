from decimal import Decimal, InvalidOperation

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from .models import HuntLog, WantedCriminal
from .serializers import HuntLogSerializer, WantedCriminalDetailSerializer, WantedCriminalSerializer

TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no"}
SORT_OPTIONS = {"reward", "-reward"}


def parse_bool(name, value):
    value = value.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValidationError({name: "Must be true or false."})


def parse_decimal(name, value):
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValidationError({name: "Must be a number."})
    if not number.is_finite():
        raise ValidationError({name: "Must be a number."})
    return number


@extend_schema_view(
    list=extend_schema(parameters=[
        OpenApiParameter("min_reward", OpenApiTypes.NUMBER, description="Minimum bounty."),
        OpenApiParameter("max_reward", OpenApiTypes.NUMBER, description="Maximum bounty."),
        OpenApiParameter("armed", OpenApiTypes.BOOL),
        OpenApiParameter("has_crew", OpenApiTypes.BOOL),
        OpenApiParameter("escape_master", OpenApiTypes.BOOL),
        OpenApiParameter("sort", OpenApiTypes.STR, enum=["reward", "-reward"]),
    ])
)
class WantedCriminalViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/criminals/ and GET /api/criminals/{id}/"""

    queryset = WantedCriminal.objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WantedCriminalDetailSerializer
        return WantedCriminalSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action != "list":
            return qs.prefetch_related("hunts")

        params = self.request.query_params
        if "min_reward" in params:
            qs = qs.filter(reward__gte=parse_decimal("min_reward", params["min_reward"]))
        if "max_reward" in params:
            qs = qs.filter(reward__lte=parse_decimal("max_reward", params["max_reward"]))
        for field in ("armed", "has_crew", "escape_master"):
            if field in params:
                qs = qs.filter(**{field: parse_bool(field, params[field])})

        sort = params.get("sort")
        if sort is not None:
            if sort not in SORT_OPTIONS:
                raise ValidationError({"sort": "Must be one of: reward, -reward."})
            qs = qs.order_by(sort, "id")
        return qs


@extend_schema_view(
    list=extend_schema(parameters=[
        OpenApiParameter("criminal_id", OpenApiTypes.INT, description="Filter by criminal."),
    ])
)
class HuntLogViewSet(viewsets.ModelViewSet):
    """Full CRUD for the hunting journal. PUT is disabled; use PATCH to update."""

    queryset = HuntLog.objects.all()
    serializer_class = HuntLogSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        criminal_id = self.request.query_params.get("criminal_id")
        if self.action == "list" and criminal_id is not None:
            if not criminal_id.isdigit():
                raise ValidationError({"criminal_id": "Must be a positive integer."})
            qs = qs.filter(criminal_id=int(criminal_id))
        return qs
