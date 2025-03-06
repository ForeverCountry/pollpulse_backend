from django.test import TestCase
from testcontainers.postgres import PostgresContainer
from django.conf import settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from ..models import Poll, User, Vote


class BaseIntegrationTest(TestCase):
    container = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.container = PostgresContainer("postgres:16")
        cls.container.start()
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


class PollIntegrationTests(BaseIntegrationTest):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

    def test_create_poll_and_vote(self):
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
        poll_response = self.client.post(
            "/api/v1/polls/", poll_data, format="json"
        )
        self.assertEqual(poll_response.status_code, status.HTTP_201_CREATED)
        poll_id = poll_response.data["id"]

        poll = Poll.objects.get(pk=poll_id)
        self.assertEqual(poll.title, "Integration Test Poll")
        self.assertEqual(poll.options.count(), 2)

        option1 = poll.options.first()
        vote_data = {"poll": poll_id, "option": option1.id}
        vote_response = self.client.post(
            "/api/v1/vote/", vote_data, format="json"
        )
        self.assertEqual(vote_response.status_code, status.HTTP_201_CREATED)

        vote = Vote.objects.filter(poll=poll, user=self.user).exists()
        self.assertTrue(vote)

        results_response = self.client.get(f"/api/v1/polls/{poll_id}/results/")
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        results = results_response.data["results"]
        self.assertEqual(len(results), 2)
        for result in results:
            if result["option_id"] == option1.id:
                self.assertEqual(result["vote_count"], 1)
            else:
                self.assertEqual(result["vote_count"], 0)
