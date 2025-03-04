from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from .models import Poll, Vote, Option, User
from .serializers import (
    LoginSerializer,
    PollSerializer,
    VoteSerializer,
    UserSerializer,
    PollResultsSerializer,
)
from drf_yasg.utils import swagger_auto_schema
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Count


@swagger_auto_schema(
    method="post",
    request_body=UserSerializer,
    responses={
        201: UserSerializer(
            help_text="Successfully registered user with token and user details."
        ),
        400: "Bad Request - Validation errors or already logged in.",
    },
    operation_summary="Register a new user",
    operation_description="Registers a new user account. Returns user details and authentication token upon successful registration.",
)
@api_view(["POST"])
@permission_classes([])
def register(request):
    """User registration endpoint."""
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
    request_body=LoginSerializer(
        help_text="Provide email and password for login."
    ),
    responses={
        200: UserSerializer(
            help_text="Successful login. Returns user details and token."
        ),
        400: "Bad Request - Invalid credentials.",
    },
    operation_summary="User login",
    operation_description="Logs in an existing user using email and password. Returns user details and authentication token upon successful login.",
)
@api_view(["POST"])
@permission_classes([])
def login(request):
    """User login endpoint."""
    email = request.data.get("email")
    password = request.data.get("password")

    user = User.objects.filter(email=email).first()
    if user and user.check_password(password):
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

    def get_queryset(self):
        """
        Optionally filters the polls based on whether they are deleted or not.
        """
        queryset = Poll.objects.all()
        is_deleted = self.request.query_params.get("is_deleted")
        if is_deleted is not None:
            queryset = queryset.filter(is_deleted=is_deleted)
        return queryset

    @swagger_auto_schema(
        operation_summary="List all polls",
        operation_description="Retrieve a list of all polls. Supports filtering by 'is_deleted' status using query parameters.",
        responses={200: PollSerializer(many=True, help_text="List of polls.")},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Create a new poll",
        operation_description="Create a new poll. Authenticated users are associated with created polls.",
        request_body=PollSerializer(help_text="Poll data to create."),
        responses={
            201: PollSerializer(help_text="Poll created successfully."),
            400: "Bad Request - Validation errors.",
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Retrieve a specific poll",
        operation_description="Retrieve details of a specific poll by its ID.",
        responses={
            200: PollSerializer(help_text="Poll details."),
            404: "Not Found - Poll not found.",
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update an existing poll",
        operation_description="Update an existing poll. Requires poll ID.",
        request_body=PollSerializer(help_text="Poll data to update."),
        responses={
            200: PollSerializer(help_text="Poll updated successfully."),
            400: "Bad Request - Validation errors.",
            404: "Not Found - Poll not found.",
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update a poll",
        operation_description="Partially update fields of an existing poll. Requires poll ID.",
        request_body=PollSerializer(
            partial=True, help_text="Fields of poll to update."
        ),
        responses={
            200: PollSerializer(help_text="Poll updated successfully."),
            400: "Bad Request - Validation errors.",
            404: "Not Found - Poll not found.",
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete a poll (soft delete)",
        operation_description="Soft deletes a poll. Poll is marked as deleted but not permanently removed.",
        responses={
            204: "No Content - Poll successfully soft deleted.",
            404: "Not Found - Poll not found.",
        },
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True  # Soft delete
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VoteCreateView(generics.CreateAPIView):
    """
    API endpoint for casting votes.
    """

    serializer_class = VoteSerializer

    @swagger_auto_schema(
        operation_summary="Cast a vote for a poll option",
        operation_description="Allows an authenticated user to cast a vote for a specific option in a poll. Prevents duplicate votes from the same user for the same poll.",
        request_body=VoteSerializer(
            help_text="Vote data: poll ID and option ID are required."
        ),
        responses={
            201: VoteSerializer(help_text="Vote cast successfully."),
            400: "Bad Request - Invalid poll/option ID, or duplicate vote.",
            401: "Unauthorized - Authentication required.",
        },
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PollResultsView(generics.RetrieveAPIView):
    """
    API endpoint to view poll results in API format.
    """

    serializer_class = PollResultsSerializer
    queryset = Poll.objects.all()
    lookup_field = "pk"

    @swagger_auto_schema(
        operation_summary="Retrieve poll results",
        operation_description="Retrieves the vote counts for each option in a specific poll.",
        responses={
            200: PollResultsSerializer(
                help_text="Poll results with vote counts."
            ),
            404: "Not Found - Poll not found.",
        },
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        results_data = self.get_poll_results(instance.id)
        return Response(results_data)

    def get_poll_results(self, poll_id):
        """
        Re-using the efficient vote count aggregation logic.
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
