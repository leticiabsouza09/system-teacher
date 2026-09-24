"""
Leitura liberada para qualquer autenticado (aluno precisa ver disciplinas/
habilidades pra entender o próprio plano). Escrita só para professor/admin
— gerenciar o currículo não é uma ação de aluno (Seção 3).
"""
from rest_framework import permissions, viewsets

from core.permissions import IsTeacher

from .models import Skill, Subject
from .serializers import SkillSerializer, SubjectSerializer


class IsTeacherOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_teacher)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsTeacherOrReadOnly]


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.select_related("subject").prefetch_related("prerequisites").all()
    serializer_class = SkillSerializer
    permission_classes = [IsTeacherOrReadOnly]
    filterset_fields = ["subject", "stage", "grade"]
