"""Hyperspace navigation maths.

The galaxy is about 120,000 light years across and the galactic map splits it
into a ~20 x 20 grid, so one grid square is roughly 6,000 light years.
Travel time is a fan estimate: a Class 1 hyperdrive crosses one grid square in
about 6 hours, and the hyperdrive class is a multiplier (Class 0.5 is twice as fast).
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import ExpressionWrapper, F, IntegerField

LIGHT_YEARS_PER_GRID_SQUARE = 6_000
LIGHT_YEARS_PER_PARSEC = 3.26
HOURS_PER_SQUARE_CLASS_1 = 6
# Planets in the same grid square are still some distance apart.
MIN_TRIP_SQUARES = 0.25


class NavigationError(Exception):
    """Raised when a route cannot be plotted (e.g. an uncharted planet)."""


@dataclass
class Route:
    grid_squares: float
    light_years: int
    parsecs: int

    def as_dict(self):
        return {
            "grid_squares": round(self.grid_squares, 2),
            "light_years": self.light_years,
            "parsecs": self.parsecs,
        }


def plot_route(origin, destination):
    if origin.pk == destination.pk:
        raise NavigationError("Origin and destination are the same planet.")
    uncharted = [p.name for p in (origin, destination) if not p.is_charted]
    if uncharted:
        raise NavigationError(
            f"No galactic coordinates for: {', '.join(uncharted)}. "
            "Set grid_x/grid_y (or grid_square) on the planet to chart it."
        )
    squares = origin.grid_distance_to(destination)
    light_years = round(max(squares, MIN_TRIP_SQUARES) * LIGHT_YEARS_PER_GRID_SQUARE)
    return Route(squares, light_years, round(light_years / LIGHT_YEARS_PER_PARSEC))


def travel_time(route, starship):
    if starship.hyperdrive_rating is None:
        raise NavigationError(f"{starship.name} has no hyperdrive rating, it cannot jump to hyperspace.")
    rating = float(starship.hyperdrive_rating)
    hours = max(route.grid_squares, MIN_TRIP_SQUARES) * HOURS_PER_SQUARE_CLASS_1 * rating
    return {
        "starship": {"id": starship.pk, "name": starship.name, "slug": starship.slug},
        "hyperdrive_rating": Decimal(starship.hyperdrive_rating),
        "estimated_hours": round(hours, 1),
        "estimated_days": round(hours / 24, 2),
    }


def nearest_planets(planet, queryset):
    """Order charted planets by squared grid distance, computed by the database."""
    if not planet.is_charted:
        raise NavigationError(f"{planet.name} has no galactic coordinates.")
    dx = F("grid_x") - planet.grid_x
    dy = F("grid_y") - planet.grid_y
    return (
        queryset.exclude(pk=planet.pk)
        .filter(grid_x__isnull=False, grid_y__isnull=False)
        .annotate(distance_sq=ExpressionWrapper(dx * dx + dy * dy, output_field=IntegerField()))
        .order_by("distance_sq", "name")
    )
