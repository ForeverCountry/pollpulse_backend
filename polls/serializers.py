from rest_framework import serializers
from .models import Poll, Option, Vote, User


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.

    Handles user registration. Includes fields for username, email, and password.
    Password is write-only and is hashed before saving.
    """

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        """
        Overrides the default create method to hash the password.
        """
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.

    Accepts email and password for user authentication. Password is write-only.
    """

    email = serializers.CharField()
    password = serializers.CharField(write_only=True)


class OptionSerializer(serializers.ModelSerializer):
    """
    Serializer for the Option model.

    Used to represent poll options. Includes fields for id, option text and order.
    """

    class Meta:
        model = Option
        fields = ["id", "option_text", "option_order"]
        read_only_fields = ["id"]


class PollSerializer(serializers.ModelSerializer):
    """
    Serializer for the Poll model.

    Handles serialization and deserialization of Poll objects.
    Includes nested serialization for 'options'.
    Provides custom create and update methods to handle nested options.
    """

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
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        """
        Overrides the default create method to handle nested 'options'.

        Creates a Poll instance and then creates associated Option instances.
        """
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

    def update(self, instance, validated_data):
        """
        Overrides the default update method to handle nested 'options'.

        Updates the Poll instance and manages associated Option instances,
        including creating new options, updating existing ones, and deleting removed options.
        """
        options_data = validated_data.pop("options", None)
        instance = super().update(instance, validated_data)

        if options_data is not None:
            instance_option_ids = set(
                instance.options.values_list("id", flat=True)
            )
            request_option_ids = set()

            for order, option_data in enumerate(options_data):
                option_id = option_data.get("id", None)
                if option_id:
                    option = Option.objects.get(id=option_id, poll=instance)
                    option_serializer = OptionSerializer(
                        option, data=option_data, partial=True
                    )
                    option_serializer.is_valid(raise_exception=True)
                    option_serializer.save()
                    request_option_ids.add(option_id)
                else:
                    Option.objects.create(
                        poll=instance, option_order=order, **option_data
                    )

            for option_to_delete in instance.options.filter(
                id__in=instance_option_ids - request_option_ids
            ):
                option_to_delete.delete()
        return instance


class VoteSerializer(serializers.ModelSerializer):
    """
    Serializer for the Vote model.

    Used for creating and representing user votes on poll options.
    Includes fields for id, poll, option, user, and creation timestamp.
    User and created_at fields are read-only as they are automatically set.
    """

    class Meta:
        model = Vote
        fields = ["id", "poll", "option", "user", "created_at"]
        read_only_fields = ["created_at", "user", "id"]


class PollResultsSerializer(serializers.Serializer):
    """
    Serializer for representing poll results.

    Structures the poll results data, including poll_id and a list of results.
    Each result in the list typically contains option details and vote counts.
    """

    poll_id = serializers.IntegerField()
    results = serializers.ListField()

    def to_representation(self, instance):
        """
        Customize representation to match the structure from get_poll_results.
        Currently, it returns the instance itself, but can be extended
        to further format the output if needed.
        """
        return instance
