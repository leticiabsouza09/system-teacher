"""
Mesma regra de queryset filtrado dos outros apps: aluno só vê as próprias
avaliações; professor vê só as dos alunos das Classroom que leciona
(vínculo real); admin vê todas.
"""
from rest_framework import permissions, viewsets

from .models import Assessment, AssessmentQuestion
from .serializers import AssessmentQuestionSerializer, AssessmentSerializer


def _turmas_do_professor(user):
    from classrooms.models import Classroom
    return Classroom.objects.filter(teachers=user)


class AssessmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["subject", "student"]

    def get_queryset(self):
        base = Assessment.objects.select_related("subject", "student").prefetch_related("questions")
        user = self.request.user
        if user.role == "admin":
            return base
        if user.is_teacher:
            return base.filter(student__classrooms_enrolled__in=_turmas_do_professor(user)).distinct()
        return base.filter(student=user)


class AssessmentQuestionViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["assessment", "skill"]

    def get_queryset(self):
        base = AssessmentQuestion.objects.select_related("skill", "assessment")
        user = self.request.user
        if user.role == "admin":
            return base
        if user.is_teacher:
            return base.filter(
                assessment__student__classrooms_enrolled__in=_turmas_do_professor(user)).distinct()
        return base.filter(assessment__student=user)
