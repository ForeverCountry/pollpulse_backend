from django.db import models
from django.contrib.auth.models import AbstractUser


# User model
class User(AbstractUser):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


# Poll model
class Poll(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="polls"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# Option model
class Option(models.Model):
    poll = models.ForeignKey(
        Poll, related_name="options", on_delete=models.CASCADE
    )
    option_text = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.poll.title} - {self.option_text}"


# Vote model
class Vote(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="votes"
    )
    poll = models.ForeignKey(
        Poll, on_delete=models.CASCADE, related_name="votes"
    )
    option = models.ForeignKey(
        Option, on_delete=models.CASCADE, related_name="votes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "poll")  # Prevent duplicate votes per poll

    def __str__(self):
        return f"{self.user.username} voted on '{self.poll.title}' for '{self.option.option_text}'"
