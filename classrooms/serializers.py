"""Serializer da Classroom (Turma)."""
from rest_framework import serializers

from users.models import User

from .models import Classroom


class UsuarioResumidoSerializer(serializers.ModelSerializer):
    """Representação mínima usada só pra exibir quem é quem numa turma —
    nunca inclui email nem qualquer outro dado além do necessário pra
    identificar a pessoa na tela."""
    class Meta:
        model = User
        fields = ["id", "username"]


class ClassroomSerializer(serializers.ModelSerializer):
    teachers_detail = UsuarioResumidoSerializer(source="teachers", many=True, read_only=True)
    students_detail = UsuarioResumidoSerializer(source="students", many=True, read_only=True)

    class Meta:
        model = Classroom
        fields = ["id", "name", "teachers", "students", "teachers_detail", "students_detail",
                  "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "teachers": {"write_only": True, "required": False},
            "students": {"write_only": True, "required": False},
        }
