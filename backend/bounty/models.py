from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class WantedCriminal(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True, help_text="Real name, may be unknown.")
    nickname = models.CharField(max_length=100)
    reward = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    # Last known location: coordinates and/or a free-text note.
    last_known_latitude = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    last_known_longitude = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    last_known_note = models.TextField(blank=True, default="")
    difficulty = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    armed = models.BooleanField(default=False)
    has_crew = models.BooleanField(default=False)
    escape_master = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(difficulty__gte=1, difficulty__lte=10), name="difficulty_1_to_10"
            ),
            models.CheckConstraint(condition=models.Q(reward__gte=0), name="reward_not_negative"),
        ]

    def __str__(self):
        return self.nickname


class HuntLog(models.Model):
    # One criminal -> many hunt logs.
    criminal = models.ForeignKey(WantedCriminal, on_delete=models.CASCADE, related_name="hunts")
    success = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Hunt #{self.pk} on {self.criminal}"
