from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from .models import Poll, Vote
from .serializers import PollSerializer, VoteSerializer
from drf_yasg.utils import swagger_auto_schema


class PollViewSet(viewsets.ModelViewSet):
    """
    API endpoint for creating and managing polls.
    """

    queryset = Poll.objects.all()
    serializer_class = PollSerializer


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
        voter_identifier = request.data.get("voter_identifier")
        if poll_id and voter_identifier:
            if Vote.objects.filter(
                poll_id=poll_id, voter_identifier=voter_identifier
            ).exists():
                return Response(
                    {"detail": "Duplicate vote is not allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)
