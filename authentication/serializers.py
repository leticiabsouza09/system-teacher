"""
Serializers de autenticação. Ficam num app próprio (não em `users`) porque
a Seção 12 do escopo já separa os dois namespaces na API: /api/auth/... é
sobre a AÇÃO de autenticar, /api/users/... (Etapa 5) é sobre o RECURSO
usuário. Pequeno desvio da árvore original da Etapa 1, justificado por
essa separação já estar implícita nos endpoints pedidos.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from users.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "first_name", "last_name", "role"]
        extra_kwargs = {"role": {"required": True}}

    def validate_role(self, value):
        # Ninguém se autorregistra como admin pela API pública — só o
        # Django Admin (ou um comando de management) cria administradores.
        if value == User.Role.ADMIN:
            raise serializers.ValidationError("Não é possível se registrar como administrador.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Usuário ou senha inválidos.", code="authorization")
        if not user.is_active:
            raise serializers.ValidationError("Esta conta está desativada.", code="authorization")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Representação pública e segura do usuário — nunca inclui password
    nem nada além do necessário (Seção 13: proteção de dados pessoais)."""
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role"]
        read_only_fields = fields
