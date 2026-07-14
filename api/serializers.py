from rest_framework import serializers
from accounts.models import User
from customer.models import Customer
from core.models import Notification


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "password",
        ]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )

        return user
    
class CustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer
        fields = "__all__"
        read_only_fields = ["user"]


class NotificationSerializer(serializers.ModelSerializer):

    category = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "status",
            "category",
            "target",
            "barangay",
            "created_at",
            "expires_at",
        ]