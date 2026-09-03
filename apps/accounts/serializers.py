"""Sérialiseurs accounts : login JWT avec claims, équipe du pressing, profil."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class LoginSerializer(TokenObtainPairSerializer):
    """Login par numéro de téléphone (username) + mot de passe.

    Enrichit le JWT avec `role` et `pressing_id` : la PWA connaît le rôle de
    l'utilisateur dès la connexion, sans requête supplémentaire.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["pressing_id"] = str(user.pressing_id) if user.pressing_id else None
        return token


class UserSerializer(serializers.ModelSerializer):
    """Représentation d'un utilisateur de l'équipe (lecture seule)."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "pressing",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class EmployeeCreateSerializer(serializers.ModelSerializer):
    """Création d'un employé par le gérant — rôle et pressing forcés côté serveur."""

    password = serializers.CharField(
        write_only=True, validators=[validate_password], style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ["id", "username", "password", "first_name", "last_name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        # `pressing` et `role` ne viennent JAMAIS du payload client : ils sont
        # déduits du gérant authentifié (isolation multi-tenant, moindre
        # privilège — un employé ne peut pas créer un gérant).
        request = self.context["request"]
        return User.objects.create_user(
            username=validated_data["username"],
            password=validated_data.pop("password"),
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            role=User.Role.EMPLOYE,
            pressing=request.user.pressing,
        )


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour d'un employé : infos, activation, réinitialisation du mot de passe."""

    password = serializers.CharField(
        write_only=True, required=False, validators=[validate_password]
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "is_active", "password"]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
