from django.contrib import admin

from .models import Climate, Film, Person, Planet, Region, Species, Starship, Terrain


@admin.register(Planet)
class PlanetAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "grid_square", "population"]
    list_filter = ["region", "climates"]
    search_fields = ["name"]
    filter_horizontal = ["climates", "terrains"]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "homeworld", "birth_year", "gender"]
    search_fields = ["name"]
    filter_horizontal = ["species"]


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ["name", "classification", "homeworld"]
    search_fields = ["name"]


@admin.register(Starship)
class StarshipAdmin(admin.ModelAdmin):
    list_display = ["name", "starship_class", "hyperdrive_rating"]
    search_fields = ["name", "model"]
    filter_horizontal = ["pilots"]


@admin.register(Film)
class FilmAdmin(admin.ModelAdmin):
    list_display = ["episode_id", "title", "release_date"]
    filter_horizontal = ["planets", "characters", "species", "starships"]


admin.site.register([Region, Climate, Terrain])
