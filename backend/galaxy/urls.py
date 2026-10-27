from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("planets", views.PlanetViewSet, basename="planet")
router.register("species", views.SpeciesViewSet, basename="species")
router.register("people", views.PersonViewSet, basename="person")
router.register("starships", views.StarshipViewSet, basename="starship")
router.register("films", views.FilmViewSet, basename="film")
router.register("regions", views.RegionViewSet, basename="region")
router.register("climates", views.ClimateViewSet, basename="climate")
router.register("terrains", views.TerrainViewSet, basename="terrain")

urlpatterns = [
    path("stats/", views.galaxy_stats, name="stats"),
    path("health/", views.health, name="health"),
    *router.urls,
]
