"""
Regra central desta view (Seção 16): "aluno não vê dados de outro aluno"
é aplicada no PRÓPRIO QUERYSET, não só como permissão de objeto — um
aluno logado nem consegue listar outros alunos, o /api/students/ dele
sempre retorna só a própria linha. Professor e admin veem todos.
"""
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsTeacher
from users.models import User

from .serializers import ProgressRecordSerializer, StudentSerializer, StudentSkillSerializer


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        base = User.objects.filter(role=User.Role.STUDENT).select_related(
            "student_profile").order_by("username")
        user = self.request.user
        if user.is_teacher or user.role == User.Role.ADMIN:
            return base
        # Aluno: só ele mesmo aparece, mesmo trocando o {id} na URL.
        return base.filter(pk=user.pk)

    @action(detail=True, methods=["get"])
    def skills(self, request, pk=None):
        student = self.get_object()  # já filtrado pelo get_queryset acima
        estados = student.skill_states.select_related("skill", "skill__subject").all()
        return Response(StudentSkillSerializer(estados, many=True).data)

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        student = self.get_object()
        registros = student.progress_records.select_related("skill").all()
        return Response(ProgressRecordSerializer(registros, many=True).data)

    @action(detail=True, methods=["get"], url_path="notes-analysis",
            permission_classes=[permissions.IsAuthenticated, IsTeacher])
    def notes_analysis(self, request, pk=None):
        """GET /api/students/{id}/notes-analysis/ — só professor. Analisa
        as anotações que O PRÓPRIO professor logado escreveu sobre este
        aluno (nunca as de outro professor)."""
        from ai.notes_analyzer import build_default_service

        student = self.get_object()
        service = build_default_service()
        resultado = service.analyze(teacher=request.user, student=student)
        return Response(resultado)
