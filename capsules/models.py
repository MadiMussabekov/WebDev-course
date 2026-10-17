from django.db import models
from django.utils import timezone


class Capsule(models.Model):
    """A message sealed until `unlock_at`. Its content is hidden by the API until then."""

    author = models.CharField(max_length=60)
    title = models.CharField(max_length=100)
    message = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    unlock_at = models.DateTimeField()
    open_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["unlock_at"]

    @property
    def is_locked(self):
        return timezone.now() < self.unlock_at

    def to_dict(self, reveal=False):
        data = {
            "id": self.id,
            "author": self.author,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "unlock_at": self.unlock_at.isoformat(),
            "locked": self.is_locked,
            "seconds_left": max(0, int((self.unlock_at - timezone.now()).total_seconds())),
            "open_count": self.open_count,
        }
        if reveal and not self.is_locked:
            data["message"] = self.message
        return data

    def __str__(self):
        return f"{self.title} by {self.author}"
