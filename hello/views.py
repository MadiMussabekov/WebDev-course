from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone


def index(request):
    return render(request, "hello/index.html", {"message": settings.APP_MESSAGE})


def hello_api(request):
    return JsonResponse(
        {
            "message": settings.APP_MESSAGE,
            "server_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
