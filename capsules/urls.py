from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/health/", views.health, name="health"),
    path("api/stats/", views.stats, name="stats"),
    path("api/capsules/", views.capsule_list, name="capsule-list"),
    path("api/capsules/<int:pk>/", views.capsule_detail, name="capsule-detail"),
]
