"""
Testes de ActivityGeneratorService (Etapa 7) e AdaptationService (Etapa 8).
Nome do arquivo não é 'tests.py' porque já existe um (do DiagnosticService,
Etapa 6) — o test runner do Django descobre qualquer 'test*.py'.
"""
from django.test import TestCase

from assessments.models import Assessment, AssessmentQuestion
from learning.models import ActivityAttempt, Diagnostic, StudyActivity, StudyPlan
from students.models import StudentProfile
from subjects.models import Skill, Subject
from users.models import User

from .activity_generator import ActivityGeneratorService
from .recommendation import AdaptationService


class ActivityGeneratorServiceTests(TestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        StudentProfile.objects.create(user=self.aluno, grade_level="8º ano", study_time_available=30)
        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Porcentagem", difficulty_level="basic")

    def test_prioridade_alta_gera_sequencia_completa_com_todos_os_tipos_novos(self):
        diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=20,  # < 40 -> high
            difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED)

        plano = ActivityGeneratorService().generate_plan_from_diagnostics(self.aluno, [diagnostico])

        self.assertEqual(plano.status, StudyPlan.Status.DRAFT)
        self.assertEqual(plano.created_by_ai, True)
        atividades = list(plano.activities.order_by("order"))
        self.assertEqual(len(atividades), 6)
        tipos = [a.activity_type for a in atividades]
        self.assertEqual(tipos, [
            StudyActivity.ActivityType.REVIEW, StudyActivity.ActivityType.TRUE_FALSE,
            StudyActivity.ActivityType.MULTIPLE_CHOICE, StudyActivity.ActivityType.SHORT_ANSWER,
            StudyActivity.ActivityType.PROBLEM_SOLVING, StudyActivity.ActivityType.MINI_ASSESSMENT,
        ])

    def test_prioridade_media_inclui_exercicio_pratico(self):
        diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=55,  # 40-70 -> medium
            difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED)
        plano = ActivityGeneratorService().generate_plan_from_diagnostics(self.aluno, [diagnostico])
        tipos = [a.activity_type for a in plano.activities.order_by("order")]
        self.assertIn(StudyActivity.ActivityType.PRACTICAL_EXERCISE, tipos)

    def test_prioridade_baixa_gera_sequencia_curta(self):
        diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=85,  # >= 70 -> low
            difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED)

        plano = ActivityGeneratorService().generate_plan_from_diagnostics(self.aluno, [diagnostico])
        atividades = list(plano.activities.order_by("order"))
        self.assertEqual(len(atividades), 2)
        self.assertEqual(atividades[0].activity_type, StudyActivity.ActivityType.CHALLENGE)

    def test_tempo_estimado_respeita_tempo_disponivel_do_aluno(self):
        self.aluno.student_profile.study_time_available = 5  # bem curto de propósito
        self.aluno.student_profile.save()
        diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=20,
            difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED)

        plano = ActivityGeneratorService().generate_plan_from_diagnostics(self.aluno, [diagnostico])
        for atividade in plano.activities.all():
            self.assertLessEqual(atividade.estimated_minutes, 10)  # nunca do tamanho "cheio" do template

    def test_um_diagnostico_so_mantem_duracao_minima_de_7_dias(self):
        """Caso comum (1 lacuna) não deve mudar de comportamento — o
        prazo mínimo de 7 dias continua valendo mesmo quando a carga é
        pequena."""
        diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=20,
            difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED)
        plano = ActivityGeneratorService().generate_plan_from_diagnostics(self.aluno, [diagnostico])
        self.assertEqual((plano.end_date - plano.start_date).days, 7)

    def test_multiplos_diagnosticos_simultaneos_estendem_o_prazo_sem_descartar_atividade(self):
        """A falha real que corrigimos: 6 disciplinas de prioridade alta
        ao mesmo tempo entulhavam um plano de 7 dias fixos com 36
        atividades — bem acima do tempo diário do aluno. Agora o prazo se
        estende (16 dias, pra 30 min/dia e 480 min de carga total), mas
        NENHUMA atividade é descartada — a lacuna continua real."""
        materia = self.skill.subject
        outras_habilidades = [
            Skill.objects.create(subject=materia, name=f"Habilidade {i}", difficulty_level="basic")
            for i in range(5)
        ]
        diagnosticos = [Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=20,
            difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED)]
        for hab in outras_habilidades:
            diagnosticos.append(Diagnostic.objects.create(
                student=self.aluno, skill=hab, mastery_level=20,
                difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED))

        plano = ActivityGeneratorService().generate_plan_from_diagnostics(self.aluno, diagnosticos)

        self.assertEqual(plano.activities.count(), 36)  # 6 habilidades × 6 atividades — nada descartado
        self.assertEqual((plano.end_date - plano.start_date).days, 16)  # ceil(480 / 30)

    def test_carga_extrema_nao_ultrapassa_30_dias(self):
        """Trava de segurança: mesmo com carga absurda, o plano nunca
        passa de 30 dias — um plano "de 3 meses" não seria útil."""
        materia = self.skill.subject
        muitas_habilidades = [
            Skill.objects.create(subject=materia, name=f"Habilidade Extra {i}", difficulty_level="basic")
            for i in range(20)
        ]
        diagnosticos = [Diagnostic.objects.create(
            student=self.aluno, skill=hab, mastery_level=20,
            difficulty_level="basic", evidence=["teste"], status=Diagnostic.Status.APPROVED)
            for hab in muitas_habilidades]

        plano = ActivityGeneratorService().generate_plan_from_diagnostics(self.aluno, diagnosticos)
        self.assertEqual((plano.end_date - plano.start_date).days, 30)


class AdaptationServiceTests(TestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Porcentagem", difficulty_level="basic")
        plano = StudyPlan.objects.create(student=self.aluno, start_date="2026-01-01", end_date="2026-01-08")
        self.atividade = StudyActivity.objects.create(
            study_plan=plano, skill=self.skill, title="Ativ", activity_type="review",
            difficulty="basic", estimated_minutes=15, order=1)

    def _tentativa(self, score):
        return ActivityAttempt.objects.create(
            activity=self.atividade, student=self.aluno, answer="x", score=score, time_spent=60)

    def test_score_alto_aumenta_dificuldade(self):
        self._tentativa(90)
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)
        self.assertEqual(decisao["action"], "increase_difficulty")
        self.assertEqual(decisao["from"], "basic")
        self.assertEqual(decisao["to"], "intermediate")

    def test_score_alto_gera_proxima_atividade_de_verdade_no_plano(self):
        """Sem isso, a adaptação seria só uma sugestão textual que ninguém
        usa — a próxima StudyActivity precisa existir no banco, no mesmo
        plano, já na dificuldade nova."""
        self._tentativa(90)
        n_atividades_antes = StudyActivity.objects.filter(study_plan=self.atividade.study_plan).count()
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)

        self.assertIsNotNone(decisao["next_activity"])
        nova = decisao["next_activity"]
        self.assertEqual(nova.study_plan_id, self.atividade.study_plan_id)
        self.assertEqual(nova.difficulty, "intermediate")
        self.assertEqual(nova.order, self.atividade.order + 1)
        self.assertEqual(
            StudyActivity.objects.filter(study_plan=self.atividade.study_plan).count(),
            n_atividades_antes + 1)

    def test_score_baixo_isolado_tambem_gera_atividade_de_reforco(self):
        self._tentativa(30)
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)
        self.assertEqual(decisao["action"], "reduce_difficulty_temporarily")
        self.assertIsNotNone(decisao["next_activity"])
        self.assertEqual(decisao["next_activity"].activity_type, StudyActivity.ActivityType.REVIEW)

    def test_maintain_nao_gera_atividade_nova(self):
        self._tentativa(70)
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)
        self.assertEqual(decisao["action"], "maintain")
        self.assertIsNone(decisao["next_activity"])

    def test_flagged_for_teacher_nao_gera_atividade_nova(self):
        for _ in range(3):
            self._tentativa(30)
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)
        self.assertEqual(decisao["action"], "flagged_for_teacher")
        self.assertIsNone(decisao["next_activity"])

    def test_score_medio_mantem(self):
        self._tentativa(70)
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)
        self.assertEqual(decisao["action"], "maintain")

    def test_score_baixo_isolado_reduz_temporariamente_sem_sinalizar_professor(self):
        self._tentativa(30)
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)
        self.assertEqual(decisao["action"], "reduce_difficulty_temporarily")
        # UMA tentativa baixa não deve, sozinha, criar alerta pro professor:
        self.assertEqual(Diagnostic.objects.count(), 0)

    def test_tres_tentativas_baixas_seguidas_sinaliza_professor_sem_ajustar_sozinho(self):
        for _ in range(3):
            self._tentativa(30)
        decisao = AdaptationService().apply_adaptation(self.aluno, self.skill)
        self.assertEqual(decisao["action"], "flagged_for_teacher")
        alerta = Diagnostic.objects.get()
        self.assertEqual(alerta.status, Diagnostic.Status.PENDING)
        self.assertIn("dificuldade persistente", alerta.evidence[0])

    def test_score_attempt_sem_gabarito_nao_altera_nota(self):
        tentativa = self._tentativa(0)
        tentativa.activity.expected_answer = ""  # sem gabarito
        tentativa.activity.save()
        resultado = AdaptationService().score_attempt(tentativa)
        self.assertEqual(resultado.score, 0)  # não modificou — não inventou correção

    def test_score_attempt_com_gabarito_corrige_automaticamente(self):
        self.atividade.expected_answer = "42"
        self.atividade.save()
        tentativa = ActivityAttempt.objects.create(
            activity=self.atividade, student=self.aluno, answer="42", score=0, time_spent=60)
        resultado = AdaptationService().score_attempt(tentativa)
        self.assertEqual(resultado.score, 100)


class DashboardTests(TestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)

    def test_aluno_nao_acessa_dashboard_do_professor(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.aluno)
        resp = client.get("/api/dashboard/teacher/")
        self.assertEqual(resp.status_code, 403)

    def test_professor_acessa_dashboard_proprio(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.professor)
        resp = client.get("/api/dashboard/teacher/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("students", resp.data)
