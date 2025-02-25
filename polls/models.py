from django.db import models


class Poll(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        help_text="Expiration date and time of the poll"
    )

    def __str__(self):
        return self.title


class Option(models.Model):
    poll = models.ForeignKey(
        Poll, related_name="options", on_delete=models.CASCADE
    )
    text = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.poll.title} - {self.text}"


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    option = models.ForeignKey(Option, on_delete=models.CASCADE)
    voter_identifier = models.CharField(
        max_length=255,
        help_text="Unique identifier for the voter (e.g., user ID or IP address)",
    )
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "poll",
            "voter_identifier",
        )  # Prevent duplicate votes per poll

    def __str__(self):
        return f"Vote on '{self.poll.title}' for '{self.option.text}' by {self.voter_identifier}"
