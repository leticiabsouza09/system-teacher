"""
Diagnostic/StudyPlan: leitura filtrada por dono (aluno só vê o próprio);
escrita de conteúdo é exclusiva da IA (Etapa 6) — aqui só existe a ação de
APROVAÇÃO/edição de status, que é humana por definição (Seção 1).
"""
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsTeacher, IsTeacherOrReadOnlyOwner

from .models import (
    ActivityAttempt, Diagnostic, ProgressRecord, StudentSkill, StudyActivity, StudyPlan,
    TeacherFeedback,
)
from .serializers import (
    ActivityAttemptCreateSerializer, ActivityAttemptSerializer, DiagnosticApproveSerializer,
    DiagnosticSerializer, ProgressRecordSerializer, StudyActivitySerializer, StudyPlanSerializer,
    TeacherFeedbackSerializer,
)


def _filtrar_por_dono_ou_professor(queryset, user):
    if user.role == "admin":
        return queryset
    if user.is_teacher:
        from classrooms.models import Classroom
        turmas = Classroom.objects.filter(teachers=user)
        return queryset.filter(student__classrooms_enrolled__in=turmas).distinct()
    return queryset.filter(student=user)


class DiagnosticViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DiagnosticSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["student", "skill", "status"]

    def get_queryset(self):
        qs = Diagnostic.objects.select_related("skill", "student", "validated_by")
        return _filtrar_por_dono_ou_professor(qs, self.request.user)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """POST /api/diagnostics/generate/ — gera diagnósticos reais via
        DiagnosticService. Aluno gera para si mesmo; professor pode gerar
        para um aluno específico passando {"student": <id>}."""
        from ai.diagnostic import build_default_service

        if request.user.is_student:
            aluno_alvo = request.user
        elif request.user.is_teacher:
            student_id = request.data.get("student")
            if not student_id:
                return Response({"student": ["Obrigatório quando quem chama é professor."]},
                                 status=status.HTTP_400_BAD_REQUEST)
            try:
                from users.models import User
                aluno_alvo = User.objects.get(pk=student_id, role=User.Role.STUDENT)
            except User.DoesNotExist:
                return Response({"student": ["Aluno não encontrado."]},
                                 status=status.HTTP_404_NOT_FOUND)
            from core.permissions import teacher_has_classroom_with
            if not teacher_has_classroom_with(request.user, aluno_alvo):
                return Response({"detail": "Você não tem vínculo com este aluno."},
                                 status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"detail": "Apenas aluno ou professor podem solicitar um diagnóstico."},
                             status=status.HTTP_403_FORBIDDEN)

        service = build_default_service()
        criados, insuficientes = service.persist_diagnostics(aluno_alvo)

        return Response({
            "diagnostics": DiagnosticSerializer(criados, many=True).data,
            "insufficient_evidence": insuficientes,
        }, status=status.HTTP_201_CREATED if criados else status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], permission_classes=[IsTeacherOrReadOnlyOwner])
    def approve(self, request, pk=None):
        """PATCH /api/diagnostics/{id}/approve/ — só professor (a
        permission_classes da action já barra aluno; IsTeacherOrReadOnlyOwner
        só libera SAFE_METHODS pro dono, e PATCH não é SAFE_METHOD)."""
        diagnostico = self.get_object()
        serializer = DiagnosticApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        diagnostico.status = serializer.validated_data["status"]
        if "mastery_level" in serializer.validated_data:
            diagnostico.mastery_level = serializer.validated_data["mastery_level"]
        diagnostico.validated_by = request.user
        diagnostico.validated_at = timezone.now()
        diagnostico.save()

        if diagnostico.status in (Diagnostic.Status.APPROVED, Diagnostic.Status.MODIFIED):
            self._sincronizar_student_skill(diagnostico)

        return Response(DiagnosticSerializer(diagnostico).data)

    def _sincronizar_student_skill(self, diagnostico: Diagnostic) -> None:
        """Um diagnóstico aprovado (ou aprovado com edição) é a fonte de
        verdade mais recente sobre o domínio do aluno naquela habilidade —
        por isso sincroniza StudentSkill aqui. Sem isso, StudentSkill nunca
        era escrito em lugar nenhum do sistema, e os dashboards/métricas
        (skills_mastered, percentual_objetivos_dominados) ficavam sempre
        vazios, mesmo com diagnósticos e planos aprovados de verdade."""
        estado, criado = StudentSkill.objects.get_or_create(
            student=diagnostico.student, skill=diagnostico.skill,
            defaults={"mastery_level": 0, "confidence": 0.5})
        antes = 0 if criado else estado.mastery_level

        estado.mastery_level = diagnostico.mastery_level
        estado.confidence = 0.6
        estado.last_evaluated_at = timezone.now()
        estado.save()

        if antes != estado.mastery_level:
            ProgressRecord.objects.create(
                student=diagnostico.student, skill=diagnostico.skill,
                mastery_before=antes, mastery_after=estado.mastery_level,
                source=ProgressRecord.Source.ASSESSMENT)


class StudyPlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudyPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["student", "status"]

    def get_queryset(self):
        qs = StudyPlan.objects.select_related("student").prefetch_related("activities__skill")
        return _filtrar_por_dono_ou_professor(qs, self.request.user)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """POST /api/study-plans/generate/ — gera plano real a partir dos
        diagnósticos JÁ APROVADOS do aluno (Seção 1: só depois de validação
        humana). Se não houver nenhum aprovado, retorna 400 em vez de gerar
        um plano vazio ou inventar diagnóstico."""
        from ai.activity_generator import build_default_service

        if request.user.is_student:
            aluno_alvo = request.user
        elif request.user.is_teacher:
            student_id = request.data.get("student")
            if not student_id:
                return Response({"student": ["Obrigatório quando quem chama é professor."]},
                                 status=status.HTTP_400_BAD_REQUEST)
            from users.models import User
            try:
                aluno_alvo = User.objects.get(pk=student_id, role=User.Role.STUDENT)
            except User.DoesNotExist:
                return Response({"student": ["Aluno não encontrado."]}, status=status.HTTP_404_NOT_FOUND)
            from core.permissions import teacher_has_classroom_with
            if not teacher_has_classroom_with(request.user, aluno_alvo):
                return Response({"detail": "Você não tem vínculo com este aluno."},
                                 status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"detail": "Apenas aluno ou professor podem gerar um plano."},
                             status=status.HTTP_403_FORBIDDEN)

        diagnosticos_aprovados = Diagnostic.objects.filter(
            student=aluno_alvo, status__in=[Diagnostic.Status.APPROVED, Diagnostic.Status.MODIFIED])
        if not diagnosticos_aprovados.exists():
            return Response(
                {"detail": "Nenhum diagnóstico aprovado encontrado para este aluno. "
                           "Gere e aprove um diagnóstico primeiro (/api/diagnostics/generate/)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = build_default_service()
        plano = service.generate_plan_from_diagnostics(aluno_alvo, diagnosticos_aprovados)
        return Response(StudyPlanSerializer(plano).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], permission_classes=[IsTeacherOrReadOnlyOwner])
    def approve(self, request, pk=None):
        """Não estava na lista original de endpoints, mas o fluxo completo
        (Seção 20) exige 'professor revisa/aprova' o plano, do mesmo jeito
        que já existe para o diagnóstico — adicionei por consistência."""
        plano = self.get_object()
        novo_status = request.data.get("status")
        if novo_status not in dict(StudyPlan.Status.choices):
            return Response({"status": ["Valor inválido."]}, status=status.HTTP_400_BAD_REQUEST)
        plano.status = novo_status
        if "teacher_notes" in request.data:
            plano.teacher_notes = request.data["teacher_notes"]
        plano.save()
        return Response(StudyPlanSerializer(plano).data)


class StudyActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """Rota registrada como 'activities' para bater com /api/activities/
    do escopo, mesmo o model se chamando StudyActivity."""
    serializer_class = StudyActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["study_plan", "skill", "status"]

    def get_queryset(self):
        qs = StudyActivity.objects.select_related("skill", "study_plan")
        user = self.request.user
        if user.role == "admin":
            return qs
        if user.is_teacher:
            from classrooms.models import Classroom
            turmas = Classroom.objects.filter(teachers=user)
            return qs.filter(study_plan__student__classrooms_enrolled__in=turmas).distinct()
        return qs.filter(study_plan__student=user)

    @action(detail=True, methods=["post"])
    def attempt(self, request, pk=None):
        """POST /api/activities/{id}/attempt/ — cria a tentativa, corrige
        automaticamente (se houver gabarito) e aplica a regra de adaptação
        (Etapa 8): quando a decisão é subir/reduzir dificuldade, a próxima
        StudyActivity já É criada no plano nesse nível — não fica só uma
        recomendação textual que ninguém usa."""
        from ai.recommendation import AdaptationService

        atividade = self.get_object()
        serializer = ActivityAttemptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tentativa = ActivityAttempt.objects.create(
            activity=atividade, student=request.user, score=0, **serializer.validated_data)
        atividade.status = StudyActivity.Status.COMPLETED
        atividade.save(update_fields=["status"])

        adaptacao = AdaptationService()
        tentativa = adaptacao.score_attempt(tentativa)
        decisao = adaptacao.apply_adaptation(request.user, atividade.skill)

        nova_atividade = decisao.pop("next_activity", None)
        decisao["next_activity"] = StudyActivitySerializer(nova_atividade).data if nova_atividade else None

        return Response(
            {"attempt": ActivityAttemptSerializer(tentativa).data, "adaptation": decisao},
            status=status.HTTP_201_CREATED,
        )


class ProgressRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProgressRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["student", "skill", "source"]

    def get_queryset(self):
        qs = ProgressRecord.objects.select_related("skill", "student")
        return _filtrar_por_dono_ou_professor(qs, self.request.user)


class TeacherFeedbackViewSet(viewsets.ModelViewSet):
    """Só professor cria/edita/apaga (o feedback É a avaliação DELE sobre
    um diagnóstico — não faz sentido o aluno escrever nisso). Cada
    professor só vê o feedback que ele mesmo deu; cada aluno só vê o
    feedback recebido — nunca o de outro aluno."""
    serializer_class = TeacherFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["student", "diagnostic"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsTeacher()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = TeacherFeedback.objects.select_related("teacher", "student", "diagnostic")
        user = self.request.user
        if user.is_teacher:
            return qs.filter(teacher=user)
        if user.is_student:
            return qs.filter(student=user)
        return qs  # admin

    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user)

    def perform_update(self, serializer):
        """Um professor não edita feedback de outro — get_queryset() já
        restringe a isso, mas o teacher do registro nunca muda na edição
        (equivalente a read_only, só reforçado aqui por clareza)."""
        serializer.save(teacher=self.request.user)
