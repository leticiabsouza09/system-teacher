"""
Mesma regra de queryset filtrado da Etapa students: aluno só vê as
próprias avaliações; professor/admin veem todas."""
from rest_framework import permissions, viewsets

from .models import Assessment, AssessmentQuestion
from .serializers import AssessmentQuestionSerializer, AssessmentSerializer


class AssessmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["subject", "student"]

    def get_queryset(self):
        base = Assessment.objects.select_related("subject", "student").prefetch_related("questions")
        user = self.request.user
        if user.is_teacher or user.role == "admin":
            return base
        return base.filter(student=user)


class AssessmentQuestionViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["assessment", "skill"]

    def get_queryset(self):
        base = AssessmentQuestion.objects.select_related("skill", "assessment")
        user = self.request.user
        if user.is_teacher or user.role == "admin":
            return base
        return base.filter(assessment__student=user)
