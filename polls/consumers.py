import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Count
from .models import Option


class PollResultsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.poll_id = self.scope["url_route"]["kwargs"]["poll_id"]
        self.poll_results_group_name = f"poll_{self.poll_id}_results"

        await self.channel_layer.group_add(
            self.poll_results_group_name, self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.poll_results_group_name, self.channel_name
        )

    async def send_results_update(self, event):
        """
        Receive results update from channel group and send to WebSocket.
        """
        message = event["message"]
        await self.send(text_data=json.dumps(message))

    @database_sync_to_async
    def get_poll_results_data(self, poll_id):
        """
        Synchronously get poll results data (database query).
        """
        options_with_counts = (
            Option.objects.filter(poll_id=poll_id)
            .annotate(vote_count=Count("votes"))
            .order_by("option_order")
        )

        results = []
        for option in options_with_counts:
            results.append(
                {
                    "option_id": option.id,
                    "option_text": option.option_text,
                    "vote_count": option.vote_count,
                }
            )
        return {"poll_id": poll_id, "results": results}
