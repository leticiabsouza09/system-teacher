"""Views de login/registro. Login usa Token do DRF (rest_framework.authtoken)
— simples e suficiente para o MVP (ver nota em settings.py)."""
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    """POST /api/auth/register/ — aberto (AllowAny é a única exceção
    correta a IsAuthenticated no projeto todo: sem isso ninguém cria conta).
    throttle_scope="auth" limita a 10 tentativas/minuto por IP (Seção 13:
    proteção contra força bruta)."""
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/auth/login/ — mesma proteção de throttle do registro:
    sem isso, um script poderia tentar milhares de senhas por minuto."""
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class MeView(APIView):
    """GET /api/auth/me/ — não estava na lista original de endpoints, mas
    todo frontend precisa disso pra saber quem está logado sem decodificar
    o token; adicionei por ser praticamente obrigatório."""
    def get(self, request):
        return Response(UserSerializer(request.user).data)
