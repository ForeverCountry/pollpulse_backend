from django.urls import path
from polls.consumers import PollResultsConsumer

websocket_urlpatterns = [
    path("ws/polls/<int:poll_id>/results/", PollResultsConsumer.as_asgi()),
]
