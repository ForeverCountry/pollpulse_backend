from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from .models import Poll, Vote
from .serializers import PollSerializer, VoteSerializer
from drf_yasg.utils import swagger_auto_schema
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from .serializers import UserSerializer


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
