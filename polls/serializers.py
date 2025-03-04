from rest_framework import serializers
from .models import Poll, Option, Vote, User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "option_text", "option_order"]


class PollSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True)
    poll_type = serializers.CharField()
    settings = serializers.JSONField()

    class Meta:
        model = Poll
        fields = [
            "id",
            "title",
            "description",
            "created_at",
            "expires_at",
            "options",
            "poll_type",
            "settings",
        ]
        read_only_fields = ["created_at"]

    def create(self, validated_data):
        options_data = validated_data.pop("options")
        poll = Poll.objects.create(
            **validated_data, user=self.context["request"].user
        )
        for order, option_data in enumerate(options_data):
            Option.objects.create(
                poll=poll,
                option_text=option_data["option_text"],
                option_order=order,
            )
        return poll


class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ["id", "poll", "option", "user", "created_at"]
        read_only_fields = ["created_at", "user"]


class PollResultsSerializer(serializers.Serializer):
    poll_id = serializers.IntegerField()
    results = serializers.ListField()

    def to_representation(self, instance):
        """
        Customize representation to match the structure from get_poll_results.
        """
        return instance
