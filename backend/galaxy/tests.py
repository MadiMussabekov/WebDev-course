from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Climate, Person, Planet


class SeededGalaxyTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_galaxy", verbosity=0)


class SeedTests(SeededGalaxyTestCase):
    def test_seed_loads_relations(self):
        tatooine = Planet.objects.get(slug="tatooine")
        self.assertEqual(tatooine.grid_square, "R-16")
        self.assertIn("Luke Skywalker", tatooine.residents.values_list("name", flat=True))
        self.assertEqual(Person.objects.get(slug="luke-skywalker").species.get().name, "Human")

    def test_seed_is_idempotent(self):
        before = Planet.objects.count()
        call_command("seed_galaxy", verbosity=0)
        self.assertEqual(Planet.objects.count(), before)


class PlanetLookupTests(SeededGalaxyTestCase):
    def test_lookup_by_id_slug_and_name(self):
        for identifier in ("3", "yavin-iv", "Yavin IV", "YAVIN iv"):
            response = self.client.get(f"/api/planets/{identifier}/")
            self.assertEqual(response.status_code, 200, identifier)
            self.assertEqual(response.data["name"], "Yavin IV")

    def test_unknown_planet_is_404(self):
        self.assertEqual(self.client.get("/api/planets/jakku/").status_code, 404)

    def test_filter_by_climate(self):
        response = self.client.get("/api/planets/", {"climate": "arid", "page_size": 100})
        names = {p["name"] for p in response.data["results"]}
        self.assertIn("Tatooine", names)
        self.assertNotIn("Hoth", names)

    def test_species_and_people_subresources(self):
        species = self.client.get("/api/planets/naboo/species/").data
        self.assertIn("Gungan", [s["name"] for s in species["native_species"]])
        people = self.client.get("/api/planets/naboo/people/").data
        self.assertIn("Padmé Amidala", [p["name"] for p in people])


class PlanetCrudTests(SeededGalaxyTestCase):
    def test_full_crud_cycle(self):
        payload = {
            "name": "Jakku", "grid_square": "M-21", "climates": ["arid", "scorching"],
            "terrains": ["desert"], "population": 2000, "region": 7,
        }
        created = self.client.post("/api/planets/", payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data["slug"], "jakku")
        self.assertEqual((created.data["grid_x"], created.data["grid_y"]), (13, 21))
        self.assertTrue(Climate.objects.filter(name="scorching").exists())

        patched = self.client.patch("/api/planets/jakku/", {"population": 5000}, format="json")
        self.assertEqual(patched.data["population"], 5000)
        self.assertEqual(patched.data["climates"], ["arid", "scorching"])

        self.assertEqual(self.client.delete("/api/planets/jakku/").status_code, 204)
        self.assertEqual(self.client.get("/api/planets/jakku/").status_code, 404)

    def test_invalid_grid_square_rejected(self):
        response = self.client.post("/api/planets/", {"name": "Nowhere", "grid_square": "99"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("grid_square", response.data)


class NavigationTests(SeededGalaxyTestCase):
    def test_distance_with_starship(self):
        response = self.client.get(
            "/api/planets/distance/", {"from": "tatooine", "to": "hoth", "starship": "millennium-falcon"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.data["distance"]["grid_squares"], 7.28, places=2)
        self.assertEqual(response.data["travel"]["estimated_hours"], 21.8)

    def test_distance_requires_parameters(self):
        self.assertEqual(self.client.get("/api/planets/distance/", {"from": "tatooine"}).status_code, 400)

    def test_uncharted_planet_is_unprocessable(self):
        response = self.client.get("/api/planets/distance/", {"from": "tatooine", "to": "stewjon"})
        self.assertEqual(response.status_code, 422)

    def test_nearest_is_sorted_by_distance(self):
        response = self.client.get("/api/planets/coruscant/nearest/", {"limit": 5})
        distances = [p["grid_distance"] for p in response.data]
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(response.data[0]["name"], "Chandrila")
