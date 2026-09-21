"""
Regra central desta view (Seção 16): "aluno não vê dados de outro aluno"
é aplicada no PRÓPRIO QUERYSET, não só como permissão de objeto — um
aluno logado nem consegue listar outros alunos, o /api/students/ dele
sempre retorna só a própria linha.

Professor vê só os alunos das Classroom que ele leciona (vínculo real,
desde a introdução do model Classroom) — não mais "qualquer professor vê
qualquer aluno". Admin continua vendo todos.
"""
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from classrooms.models import Classroom
from core.permissions import IsTeacher, IsTeacherOfStudent
from users.models import User

from .serializers import ProgressRecordSerializer, StudentSerializer, StudentSkillSerializer


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        base = User.objects.filter(role=User.Role.STUDENT).select_related(
            "student_profile").order_by("username")
        user = self.request.user
        if user.role == User.Role.ADMIN:
            return base
        if user.is_teacher:
            turmas_do_professor = Classroom.objects.filter(teachers=user)
            return base.filter(classrooms_enrolled__in=turmas_do_professor).distinct()
        # Aluno: só ele mesmo aparece, mesmo trocando o {id} na URL.
        return base.filter(pk=user.pk)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, IsTeacherOfStudent])
    def skills(self, request, pk=None):
        # get_object() já aplica IsTeacherOfStudent (permissão de objeto) —
        # aluno cai no caminho de baixo, sem essa permission_class extra
        # (ver override de get_permissions abaixo).
        student = self.get_object()
        estados = student.skill_states.select_related("skill", "skill__subject").all()
        return Response(StudentSkillSerializer(estados, many=True).data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, IsTeacherOfStudent])
    def progress(self, request, pk=None):
        student = self.get_object()
        registros = student.progress_records.select_related("skill").all()
        return Response(ProgressRecordSerializer(registros, many=True).data)

    @action(detail=True, methods=["get"], url_path="notes-analysis",
            permission_classes=[permissions.IsAuthenticated, IsTeacher, IsTeacherOfStudent])
    def notes_analysis(self, request, pk=None):
        """GET /api/students/{id}/notes-analysis/ — só professor com
        vínculo de Classroom com este aluno. Analisa as anotações que O
        PRÓPRIO professor logado escreveu sobre este aluno."""
        from ai.notes_analyzer import build_default_service

        student = self.get_object()
        service = build_default_service()
        resultado = service.analyze(teacher=request.user, student=student)
        return Response(resultado)

    def get_permissions(self):
        """skills/progress precisam liberar o PRÓPRIO aluno (get_queryset
        já garante que ele só acessa a si mesmo) — IsTeacherOfStudent
        sozinho bloquearia o aluno, que não é professor. Então essas duas
        actions usam IsTeacherOfStudent só quando quem pede é professor;
        para o aluno dono, get_queryset() já é suficiente."""
        if self.action in ("skills", "progress") and self.request.user.is_authenticated \
                and not self.request.user.is_teacher:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()
