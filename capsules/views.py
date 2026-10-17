import json
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import Capsule


def index(request):
    return render(request, "capsules/index.html", {"title": settings.APP_TITLE})


@require_GET
def health(request):
    """Reports whether the backend can reach PostgreSQL."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            db_version = cursor.fetchone()[0]
        return JsonResponse({"status": "ok", "database": db_version})
    except Exception as exc:
        return JsonResponse({"status": "error", "detail": str(exc)}, status=503)


@require_GET
def stats(request):
    now = timezone.now()
    total = Capsule.objects.count()
    locked = Capsule.objects.filter(unlock_at__gt=now).count()
    next_capsule = Capsule.objects.filter(unlock_at__gt=now).order_by("unlock_at").first()
    return JsonResponse(
        {
            "total": total,
            "locked": locked,
            "unlocked": total - locked,
            "total_opens": Capsule.objects.aggregate(s=Sum("open_count"))["s"] or 0,
            "next_unlock": next_capsule.to_dict() if next_capsule else None,
        }
    )


def _parse_unlock_at(payload):
    """Accepts either `unlock_at` (ISO datetime) or `unlock_in_seconds` (int)."""
    if payload.get("unlock_at"):
        unlock_at = parse_datetime(str(payload["unlock_at"]))
        if unlock_at is None:
            raise ValueError("unlock_at must be an ISO 8601 datetime")
        if timezone.is_naive(unlock_at):
            unlock_at = timezone.make_aware(unlock_at)
        return unlock_at
    if payload.get("unlock_in_seconds") is not None:
        seconds = int(payload["unlock_in_seconds"])
        return timezone.now() + timedelta(seconds=seconds)
    raise ValueError("provide unlock_at or unlock_in_seconds")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def capsule_list(request):
    if request.method == "GET":
        capsules = Capsule.objects.all()
        status = request.GET.get("status")
        if status == "locked":
            capsules = capsules.filter(unlock_at__gt=timezone.now())
        elif status == "unlocked":
            capsules = capsules.filter(unlock_at__lte=timezone.now())
        return JsonResponse({"capsules": [c.to_dict() for c in capsules]})

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    errors = {}
    author = str(payload.get("author", "")).strip()
    title = str(payload.get("title", "")).strip()
    message = str(payload.get("message", "")).strip()
    if not author or len(author) > 60:
        errors["author"] = "required, max 60 characters"
    if not title or len(title) > 100:
        errors["title"] = "required, max 100 characters"
    if not message or len(message) > 2000:
        errors["message"] = "required, max 2000 characters"
    try:
        unlock_at = _parse_unlock_at(payload)
        if unlock_at <= timezone.now():
            errors["unlock_at"] = "must be in the future"
        elif unlock_at > timezone.now() + timedelta(days=settings.MAX_LOCK_DAYS):
            errors["unlock_at"] = f"cannot be more than {settings.MAX_LOCK_DAYS} days away"
    except (ValueError, TypeError) as exc:
        errors["unlock_at"] = str(exc)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    capsule = Capsule.objects.create(author=author, title=title, message=message, unlock_at=unlock_at)
    return JsonResponse(capsule.to_dict(), status=201)


@require_GET
def capsule_detail(request, pk):
    try:
        capsule = Capsule.objects.get(pk=pk)
    except Capsule.DoesNotExist:
        return JsonResponse({"error": "capsule not found"}, status=404)

    if capsule.is_locked:
        # 423 Locked: the capsule exists but is still sealed.
        return JsonResponse({**capsule.to_dict(), "error": "this capsule is still sealed"}, status=423)

    Capsule.objects.filter(pk=pk).update(open_count=F("open_count") + 1)
    capsule.refresh_from_db()
    return JsonResponse(capsule.to_dict(reveal=True))
