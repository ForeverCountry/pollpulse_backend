from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PollViewSet, VoteCreateView

router = DefaultRouter()
router.register(r"polls", PollViewSet, basename="poll")

urlpatterns = [
    path("", include(router.urls)),
    path("vote/", VoteCreateView.as_view(), name="vote"),
]
