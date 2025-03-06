from django.test import TestCase
from testcontainers.postgres import PostgresContainer
from django.conf import settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from ..models import Poll, User, Vote


class BaseIntegrationTest(TestCase):
    """
    Base test class that manages the lifecycle of the Postgres test container
    and applies Django migrations.
    """

    container = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.container = PostgresContainer("postgres:16")
        cls.container.start()
        cls._setup_database()

    @classmethod
    def _setup_database(cls):
        db_url = cls.container.get_connection_url()
        settings.DATABASES["default"] = {
            "ENGINE": "django.db.backends.postgresql",
            "URL": db_url,
            "ATOMIC_REQUESTS": False,
        }
        from django.core.management import call_command

        call_command("migrate")

    @classmethod
    def tearDownClass(cls):
        if cls.container:
            cls.container.stop()
        super().tearDownClass()


class APITestMixin:
    """
    Mixin providing common helper methods for API testing:
      - Authenticating clients
      - Creating test users
      - Creating polls, voting, and fetching poll results
    """

    def authenticate_client(self, user=None):
        self.client = APIClient()
        if user is None:
            user = self.create_test_user()
        self.token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        return user

    def create_test_user(self):
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
        )

    def create_poll(self, poll_data):
        response = self.client.post("/api/v1/polls/", poll_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def vote_on_poll(self, poll_id, option_id):
        vote_data = {"poll": poll_id, "option": option_id}
        response = self.client.post("/api/v1/vote/", vote_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def get_poll_results(self, poll_id):
        response = self.client.get(f"/api/v1/polls/{poll_id}/results/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data


class PollIntegrationTests(BaseIntegrationTest, APITestMixin):
    """
    Integration tests for poll functionality.
    """

    def setUp(self):
        # Authenticate API client and create a test user.
        self.test_user = self.authenticate_client()

    def test_create_poll_and_vote(self):
        # Define poll data payload.
        poll_data = {
            "title": "Integration Test Poll",
            "description": "Test poll created via integration test",
            "options": [
                {"option_text": "Option 1"},
                {"option_text": "Option 2"},
            ],
            "poll_type": "single_choice",
            "settings": {},
        }
        # Create poll and verify creation.
        poll_response = self.create_poll(poll_data)
        poll_id = poll_response["id"]

        poll = Poll.objects.get(pk=poll_id)
        self.assertEqual(poll.title, "Integration Test Poll")
        self.assertEqual(poll.options.count(), 2)

        # Vote on the first poll option.
        option1 = poll.options.first()
        self.vote_on_poll(poll_id, option1.id)

        # Verify that the vote exists in the database.
        vote_exists = Vote.objects.filter(
            poll=poll, user=self.test_user
        ).exists()
        self.assertTrue(vote_exists)

        # Fetch poll results and verify vote counts.
        results_response = self.get_poll_results(poll_id)
        results = results_response["results"]
        self.assertEqual(len(results), 2)
        for result in results:
            if result["option_id"] == option1.id:
                self.assertEqual(result["vote_count"], 1)
            else:
                self.assertEqual(result["vote_count"], 0)
