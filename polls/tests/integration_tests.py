import dj_database_url
from django.test import TestCase
from testcontainers.postgres import PostgresContainer
from django.conf import settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
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
        if db_url.startswith("postgresql+psycopg2"):
            db_url = db_url.replace("postgresql+psycopg2", "postgres")
        db_config = dj_database_url.parse(db_url)
        db_config["ATOMIC_REQUESTS"] = False

        settings.DATABASES["default"] = db_config

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


class RegisterLoginTests(BaseIntegrationTest, APITestMixin, APITestCase):
    """
    Tests for user registration and login API endpoints.
    """

    def test_register_user_success(self):
        """
        Test successful user registration.
        """
        url = reverse("register")
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpassword",
        }
        response = self.client.post(url, user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["username"], "newuser")
        self.assertEqual(response.data["user"]["email"], "newuser@example.com")

    def test_register_user_invalid_data(self):
        """
        Test user registration with invalid data.
        """
        url = reverse("register")
        user_data = {
            "email": "invalid-email",  # Invalid email format
            "password": "short",  # Password too short
        }
        response = self.client.post(url, user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertIn("username", response.data)

    def test_register_user_already_logged_in(self):
        """
        Test registration attempt when user is already logged in.
        """
        self.authenticate_client()  # Log in a default user
        url = reverse("register")
        user_data = {
            "username": "anotheruser",
            "email": "another@example.com",
            "password": "anotherpassword",
        }
        response = self.client.post(url, user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Already logged in.")

    def test_login_user_success(self):
        """
        Test successful user login.
        """
        self.create_test_user()  # Create a user to log in
        url = reverse("login")
        login_data = {"email": "test@example.com", "password": "testpassword"}
        response = self.client.post(url, login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "test@example.com")

    def test_login_user_invalid_credentials(self):
        """
        Test login with invalid credentials.
        """
        url = reverse("login")
        login_data = {"email": "test@example.com", "password": "wrongpassword"}
        response = self.client.post(url, login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "Invalid Credentials")


class PollViewSetTests(BaseIntegrationTest, APITestMixin, APITestCase):
    """
    Tests for PollViewSet API endpoints.
    """

    def setUp(self):
        super().setUp()
        self.test_user = self.authenticate_client()
        self.poll_data = {
            "title": "Test Poll",
            "description": "This is a test poll.",
            "options": [
                {"option_text": "Option A"},
                {"option_text": "Option B"},
            ],
            "poll_type": "single_choice",
            "settings": {},
        }
        self.poll_detail_url = reverse(
            "poll-detail", kwargs={"pk": 1}
        )  # URL for detail/update/delete
        self.poll_list_url = reverse("poll-list")  # URL for list/create

    def test_list_polls(self):
        """
        Test listing all polls.
        """
        self.create_poll(self.poll_data)  # Create a poll first
        response = self.client.get(self.poll_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data), 1
        )  # Assuming only one poll created
        self.assertEqual(response.data[0]["title"], "Test Poll")

    def test_list_polls_filtered_deleted(self):
        """
        Test listing polls filtered by is_deleted status.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        poll = Poll.objects.get(pk=poll_id)
        poll.is_deleted = True
        poll.save()

        response = self.client.get(self.poll_list_url, {"is_deleted": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], poll_id)

        response = self.client.get(self.poll_list_url, {"is_deleted": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data), 0
        )  # Should be zero since the poll is soft deleted

    def test_create_poll(self):
        """
        Test creating a new poll.
        """
        response = self.client.post(
            self.poll_list_url, self.poll_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Test Poll")
        self.assertEqual(Poll.objects.count(), 1)

    def test_create_poll_invalid_data(self):
        """
        Test creating a poll with invalid data.
        """
        invalid_poll_data = {
            "description": "Missing title"
        }  # Title is required
        response = self.client.post(
            self.poll_list_url, invalid_poll_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_retrieve_poll(self):
        """
        Test retrieving a specific poll.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        url = reverse("poll-detail", kwargs={"pk": poll_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Poll")

    def test_retrieve_poll_not_found(self):
        """
        Test retrieving a non-existent poll.
        """
        url = reverse("poll-detail", kwargs={"pk": 999})  # Non-existent pk
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_poll(self):
        """
        Test updating an existing poll.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        url = reverse("poll-detail", kwargs={"pk": poll_id})
        updated_poll_data = {
            "title": "Updated Test Poll",
            "description": "Updated description.",
            "options": [
                {
                    "option_text": "Option C"
                }  # Keeping only one option for simplicity in test
            ],
            "poll_type": "single_choice",
            "settings": {},
        }
        response = self.client.put(url, updated_poll_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Test Poll")
        self.assertEqual(
            len(response.data["options"]), 1
        )  # Verify option update

    def test_update_poll_not_found(self):
        """
        Test updating a non-existent poll.
        """
        url = reverse("poll-detail", kwargs={"pk": 999})  # Non-existent pk
        updated_poll_data = {
            "title": "Updated Test Poll",
            "description": "Updated description.",
        }
        response = self.client.put(url, updated_poll_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_poll_invalid_data(self):
        """
        Test updating a poll with invalid data.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        url = reverse("poll-detail", kwargs={"pk": poll_id})
        invalid_poll_data = {"title": ""}  # Invalid - title cannot be blank
        response = self.client.put(url, invalid_poll_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_partial_update_poll(self):
        """
        Test partially updating a poll.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        url = reverse("poll-detail", kwargs={"pk": poll_id})
        partial_poll_data = {"description": "Partially updated description."}
        response = self.client.patch(url, partial_poll_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["description"], "Partially updated description."
        )
        # Title should remain the same
        self.assertEqual(response.data["title"], "Test Poll")

    def test_partial_update_poll_not_found(self):
        """
        Test partially updating a non-existent poll.
        """
        url = reverse("poll-detail", kwargs={"pk": 999})  # Non-existent pk
        partial_poll_data = {"description": "Partially updated description."}
        response = self.client.patch(url, partial_poll_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_partial_update_poll_invalid_data(self):
        """
        Test partially updating a poll with invalid data (making title blank).
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        url = reverse("poll-detail", kwargs={"pk": poll_id})
        invalid_poll_data = {"title": ""}  # Invalid - title cannot be blank
        response = self.client.patch(url, invalid_poll_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_destroy_poll(self):
        """
        Test soft deleting a poll.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        url = reverse("poll-detail", kwargs={"pk": poll_id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        poll = Poll.objects.get(pk=poll_id)
        self.assertTrue(poll.is_deleted)  # Verify soft delete

    def test_destroy_poll_not_found(self):
        """
        Test deleting a non-existent poll.
        """
        url = reverse("poll-detail", kwargs={"pk": 999})  # Non-existent pk
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class VoteCreateViewTests(BaseIntegrationTest, APITestMixin, APITestCase):
    """
    Tests for VoteCreateView API endpoint.
    """

    def setUp(self):
        super().setUp()
        self.test_user = self.authenticate_client()
        self.poll_data = {
            "title": "Vote Test Poll",
            "description": "Poll for vote testing.",
            "options": [
                {"option_text": "Vote Option 1"},
                {"option_text": "Vote Option 2"},
            ],
            "poll_type": "single_choice",
            "settings": {},
        }
        self.vote_url = reverse("vote")

    def test_create_vote(self):
        """
        Test creating a vote successfully.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        option1 = Poll.objects.get(pk=poll_id).options.first()
        vote_data = {"poll": poll_id, "option": option1.id}
        response = self.client.post(self.vote_url, vote_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vote.objects.count(), 1)
        vote = Vote.objects.first()
        self.assertEqual(vote.poll.id, poll_id)
        self.assertEqual(vote.option.id, option1.id)
        self.assertEqual(vote.user, self.test_user)

    def test_create_vote_duplicate(self):
        """
        Test creating a duplicate vote by the same user.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        option1 = Poll.objects.get(pk=poll_id).options.first()
        vote_data = {"poll": poll_id, "option": option1.id}
        # First vote
        self.client.post(self.vote_url, vote_data, format="json")
        # Second duplicate vote
        response = self.client.post(self.vote_url, vote_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"], "User has already voted in this poll."
        )
        self.assertEqual(Vote.objects.count(), 1)  # Still only one vote in DB

    def test_create_vote_invalid_poll_option_id(self):
        """
        Test creating vote with invalid poll or option ID.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        vote_data_invalid_poll = {
            "poll": 999,  # Invalid poll ID
            "option": Poll.objects.get(pk=poll_id).options.first().id,
        }
        response = self.client.post(
            self.vote_url, vote_data_invalid_poll, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid poll or option ID.")

        vote_data_invalid_option = {
            "poll": poll_id,
            "option": 999,
        }  # Invalid option ID
        response = self.client.post(
            self.vote_url, vote_data_invalid_option, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid poll or option ID.")

    def test_create_vote_missing_poll_option(self):
        """
        Test creating vote with missing poll or option data.
        """
        vote_data_missing_poll = {"option": 1}  # Missing poll ID
        response = self.client.post(
            self.vote_url, vote_data_missing_poll, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"], "Poll and option are required."
        )

        vote_data_missing_option = {"poll": 1}  # Missing option ID
        response = self.client.post(
            self.vote_url, vote_data_missing_option, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"], "Poll and option are required."
        )


class PollResultsViewTests(BaseIntegrationTest, APITestMixin, APITestCase):
    """
    Tests for PollResultsView API endpoint.
    """

    def setUp(self):
        super().setUp()
        self.test_user = self.authenticate_client()
        self.poll_data = {
            "title": "Results Test Poll",
            "description": "Poll for results testing.",
            "options": [
                {"option_text": "Results Option 1"},
                {"option_text": "Results Option 2"},
            ],
            "poll_type": "single_choice",
            "settings": {},
        }

    def test_retrieve_poll_results(self):
        """
        Test retrieving poll results.
        """
        poll_response = self.create_poll(self.poll_data)
        poll_id = poll_response["id"]
        option1 = Poll.objects.get(pk=poll_id).options.first()
        self.vote_on_poll(poll_id, option1.id)  # Cast a vote

        url = reverse("poll-results", kwargs={"pk": poll_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("poll_id", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["poll_id"], poll_id)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        for result in results:
            if result["option_id"] == option1.id:
                self.assertEqual(result["vote_count"], 1)
                break

    def test_retrieve_poll_results_not_found(self):
        """
        Test retrieving results for a non-existent poll.
        """
        url = reverse("poll-results", kwargs={"pk": 999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
