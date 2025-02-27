from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from .views import register, login, PollViewSet, VoteCreateView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"polls", PollViewSet, basename="poll")

urlpatterns = [
    path("register/", register, name="register"),
    path("login/", login, name="login"),
    path("api-token-auth/", obtain_auth_token, name="api_token_auth"),
    path("vote/", VoteCreateView.as_view(), name="vote"),
]

urlpatterns += router.urls
