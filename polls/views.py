from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from .models import Poll, Vote, Option
from .serializers import PollSerializer, VoteSerializer
from drf_yasg.utils import swagger_auto_schema
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from .serializers import UserSerializer
from django.shortcuts import render
from asgiref.sync import (
    async_to_sync,
)


# Channels imports
from channels.layers import get_channel_layer
from django.db.models import Count


def count_sse_view(request, poll_id):
    return render(request, "index.html", {"poll_id": poll_id})


@swagger_auto_schema(
    method="post",
    request_body=UserSerializer,
    responses={201: UserSerializer()},
)
@api_view(["POST"])
@permission_classes([])
def register(request):
    """User registration"""
    if request.user.is_authenticated:
        return Response(
            {"detail": "Already logged in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    request_body=UserSerializer,
    responses={200: UserSerializer()},
)
@api_view(["POST"])
@permission_classes([])
def login(request):
    """User login"""
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(username=username, password=password)
    if user:
        token, created = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data}
        )
    return Response(
        {"error": "Invalid Credentials"}, status=status.HTTP_400_BAD_REQUEST
    )


class PollViewSet(viewsets.ModelViewSet):
    """
    API endpoint for creating and managing polls.
    """

    queryset = Poll.objects.all()
    serializer_class = PollSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class VoteCreateView(generics.CreateAPIView):
    """
    API endpoint for casting votes.
    """

    serializer_class = VoteSerializer

    @swagger_auto_schema(
        operation_summary="Cast a vote", responses={201: VoteSerializer()}
    )
    def create(self, request, *args, **kwargs):
        poll_id = request.data.get("poll")
        option_id = request.data.get("option")
        user = request.user

        if not poll_id or not option_id:
            return Response(
                {"error": "Poll and option are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            poll = Poll.objects.get(pk=poll_id)
            option = Option.objects.get(pk=option_id, poll_id=poll_id)
        except (Poll.DoesNotExist, Option.DoesNotExist):
            return Response(
                {"error": "Invalid poll or option ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Vote.objects.filter(poll=poll, user=user).exists():
            return Response(
                {"detail": "User has already voted in this poll."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.data["user"] = user.id
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user, poll=poll, option=option)
            self.send_realtime_updates(poll_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def send_realtime_updates(self, poll_id):
        """
        Sends real-time updates to clients subscribed to the poll results.
        """
        channel_layer = get_channel_layer()
        results_data = self.get_poll_results(poll_id)

        async_to_sync(channel_layer.group_send)(
            f"poll_{poll_id}_results",
            {
                "type": "send_results_update",
                "message": results_data,
            },
        )

    def get_poll_results(self, poll_id):
        """
        Efficiently aggregates vote counts for each option in a poll.
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
