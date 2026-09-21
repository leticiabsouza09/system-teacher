"""
Dashboards (Seção 10/11). São agregados só-leitura — não expõem CRUD
próprio, por isso não têm ViewSet/router, só duas APIViews simples.
"""
from django.db.models import Avg
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsTeacher
from learning.models import ActivityAttempt, Diagnostic, StudentSkill, StudyPlan
from users.models import User

from .serializers import StudentDashboardSerializer, TeacherDashboardSerializer

MASTERY_DOMINADA = 70  # mesmo limiar de referência usado em ai/diagnostic.py (MASTERY_THRESHOLD_MEDIUM)


class StudentDashboardView(APIView):
    """GET /api/dashboard/student/ — sempre sobre o PRÓPRIO aluno logado;
    não aceita ver o dashboard de outro (isso é o professor quem vê, no
    dashboard dele)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        aluno = request.user
        estados = StudentSkill.objects.filter(student=aluno).select_related("skill")

        progress_overall = estados.aggregate(media=Avg("mastery_level"))["media"] or 0.0
        dominadas = [{"skill": e.skill.name, "mastery_level": e.mastery_level}
                     for e in estados if e.mastery_level >= MASTERY_DOMINADA]
        em_desenvolvimento = [{"skill": e.skill.name, "mastery_level": e.mastery_level}
                              for e in estados if e.mastery_level < MASTERY_DOMINADA]

        atividades_concluidas = ActivityAttempt.objects.filter(student=aluno).count()
        tempo_estudado = sum(
            ActivityAttempt.objects.filter(student=aluno).values_list("time_spent", flat=True)) // 60

        plano_atual = (StudyPlan.objects.filter(student=aluno)
                       .exclude(status=StudyPlan.Status.ARCHIVED)
                       .order_by("-created_at").first())
        plano_serializado = None
        if plano_atual:
            from learning.serializers import StudyPlanSerializer
            plano_serializado = StudyPlanSerializer(plano_atual).data

        dados = {
            "progress_overall": round(progress_overall, 1),
            "activities_completed": atividades_concluidas,
            "study_time_minutes": tempo_estudado,
            "skills_mastered": dominadas,
            "skills_developing": em_desenvolvimento,
            "current_plan": plano_serializado,
        }
        return Response(StudentDashboardSerializer(dados).data)


class TeacherDashboardView(APIView):
    """GET /api/dashboard/teacher/ — visão agregada só dos alunos das
    Classroom que o professor logado leciona (vínculo real, desde a
    introdução do model Classroom — antes era "qualquer professor vê
    qualquer aluno")."""
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        from classrooms.models import Classroom

        turmas = Classroom.objects.filter(teachers=request.user)
        alunos = User.objects.filter(role=User.Role.STUDENT, classrooms_enrolled__in=turmas).distinct()
        resumo_alunos = []
        for aluno in alunos:
            media = (StudentSkill.objects.filter(student=aluno)
                     .aggregate(media=Avg("mastery_level"))["media"] or 0.0)
            pendentes = Diagnostic.objects.filter(student=aluno, status=Diagnostic.Status.PENDING).count()
            resumo_alunos.append({
                "id": aluno.id, "username": aluno.username,
                "progress_overall": round(media, 1), "pending_diagnostics": pendentes,
            })

        pending_diagnostics_count = Diagnostic.objects.filter(
            status=Diagnostic.Status.PENDING, student__in=alunos).count()
        plans_awaiting_approval_count = StudyPlan.objects.filter(
            status=StudyPlan.Status.DRAFT, student__in=alunos).count()

        # Alertas de dificuldade persistente: Diagnostic gerado pelo
        # AdaptationService (Etapa 8) carrega essa frase na evidência.
        # NOTA: comparar por texto na evidência é uma solução simples para
        # o MVP — o ideal seria um campo/flag dedicado no model Diagnostic
        # (ex.: source="persistent_difficulty"), a evoluir numa próxima
        # iteração se esse fluxo crescer.
        alertas = Diagnostic.objects.filter(
            status=Diagnostic.Status.PENDING,
            evidence__icontains="dificuldade persistente",
            student__in=alunos,
        ).select_related("student", "skill")

        alertas_serializados = [
            {"student": a.student.username, "skill": a.skill.name,
             "evidence": a.evidence, "created_at": a.created_at}
            for a in alertas
        ]

        dados = {
            "students": resumo_alunos,
            "pending_diagnostics_count": pending_diagnostics_count,
            "plans_awaiting_approval_count": plans_awaiting_approval_count,
            "persistent_difficulty_alerts": alertas_serializados,
        }
        return Response(TeacherDashboardSerializer(dados).data)


class SystemMetricsView(APIView):
    """GET /api/dashboard/metrics/ — Seção 15 do escopo. Só professor/admin
    (métricas agregadas do sistema todo não são algo que um aluno individual
    precise ver). Cada métrica vem com "proxy" (se é uma aproximação, não a
    definição original) e "not_implemented" (motivo explícito, quando o
    schema atual não sustenta o cálculo) — nunca um número inventado."""
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        from ai.progress_analyzer import ProgressAnalyzerService
        return Response(ProgressAnalyzerService().compute_all())
