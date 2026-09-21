"""
Testes das duas correções encontradas no teste manual via Postman:
1) createsuperuser agora define role=ADMIN (antes ficava STUDENT por padrão).
2) StudentSkill/ProgressRecord são sincronizados na aprovação de diagnóstico
   e na correção de atividade (só quando há gabarito real).
"""
from django.contrib.auth.management.commands.createsuperuser import Command as CreateSuperuserCommand
from django.test import TestCase
from rest_framework.test import APITestCase

from assessments.models import Assessment, AssessmentQuestion
from learning.models import ActivityAttempt, Diagnostic, ProgressRecord, StudentSkill, StudyActivity, StudyPlan
from subjects.models import Skill, Subject
from users.models import User

from .recommendation import AdaptationService


class CreateSuperuserRoleTests(TestCase):
    def test_createsuperuser_define_role_admin(self):
        User.objects.create_superuser(username="admin_teste", email="a@t.com", password="x")
        admin = User.objects.get(username="admin_teste")
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_create_user_comum_continua_student_por_padrao(self):
        """A correção é só no create_superuser — create_user normal (usado
        no registro via API) continua com o default STUDENT do campo."""
        aluno = User.objects.create_user(username="aluno_teste", email="a2@t.com", password="x")
        self.assertEqual(aluno.role, User.Role.STUDENT)


class DiagnosticApprovalSyncsStudentSkillTests(APITestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno)
        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        self.diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=30,
            difficulty_level="basic", evidence=["teste"])

    def test_aprovar_diagnostico_cria_student_skill(self):
        self.assertFalse(StudentSkill.objects.filter(student=self.aluno, skill=self.skill).exists())

        self.client.force_authenticate(user=self.professor)
        resp = self.client.patch(f"/api/diagnostics/{self.diagnostico.id}/approve/",
                                  {"status": "approved"}, format="json")
        self.assertEqual(resp.status_code, 200)

        estado = StudentSkill.objects.get(student=self.aluno, skill=self.skill)
        self.assertEqual(estado.mastery_level, 30)
        self.assertIsNotNone(estado.last_evaluated_at)

    def test_aprovar_diagnostico_registra_progress_record(self):
        self.client.force_authenticate(user=self.professor)
        self.client.patch(f"/api/diagnostics/{self.diagnostico.id}/approve/",
                           {"status": "approved"}, format="json")

        registro = ProgressRecord.objects.get(student=self.aluno, skill=self.skill)
        self.assertEqual(registro.mastery_before, 0)  # não existia StudentSkill antes
        self.assertEqual(registro.mastery_after, 30)
        self.assertEqual(registro.source, ProgressRecord.Source.ASSESSMENT)

    def test_segunda_aprovacao_atualiza_em_vez_de_duplicar(self):
        """Sincroniza duas vezes (dois diagnósticos aprovados na mesma
        habilidade) — deve ATUALIZAR o StudentSkill existente, não criar
        um segundo (o campo é unique_together (student, skill))."""
        self.client.force_authenticate(user=self.professor)
        self.client.patch(f"/api/diagnostics/{self.diagnostico.id}/approve/",
                           {"status": "approved"}, format="json")

        diagnostico2 = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=55,
            difficulty_level="basic", evidence=["segunda avaliação"])
        self.client.patch(f"/api/diagnostics/{diagnostico2.id}/approve/",
                           {"status": "approved"}, format="json")

        self.assertEqual(StudentSkill.objects.filter(student=self.aluno, skill=self.skill).count(), 1)
        estado = StudentSkill.objects.get(student=self.aluno, skill=self.skill)
        self.assertEqual(estado.mastery_level, 55)
        self.assertEqual(ProgressRecord.objects.filter(student=self.aluno, skill=self.skill).count(), 2)


class ActivityAttemptSyncsStudentSkillTests(APITestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        plano = StudyPlan.objects.create(student=self.aluno, start_date="2026-01-01", end_date="2026-01-08")
        self.atividade_sem_gabarito = StudyActivity.objects.create(
            study_plan=plano, skill=self.skill, title="Revisão", activity_type="review",
            difficulty="basic", estimated_minutes=15, order=1, expected_answer="")
        self.atividade_com_gabarito = StudyActivity.objects.create(
            study_plan=plano, skill=self.skill, title="Miniavaliação", activity_type="mini_assessment",
            difficulty="basic", estimated_minutes=10, order=2, expected_answer="1/2")

    def test_atividade_sem_gabarito_nao_toca_em_student_skill(self):
        """Este é o bug exato que apareceu no teste manual: uma atividade
        sem gabarito (score sempre 0) NÃO pode zerar o mastery_level real
        do aluno."""
        tentativa = ActivityAttempt.objects.create(
            activity=self.atividade_sem_gabarito, student=self.aluno,
            answer="qualquer coisa", score=0, time_spent=60)
        AdaptationService().score_attempt(tentativa)

        self.assertFalse(StudentSkill.objects.filter(student=self.aluno, skill=self.skill).exists())
        self.assertEqual(ProgressRecord.objects.filter(student=self.aluno, skill=self.skill).count(), 0)

    def test_atividade_com_gabarito_e_acerto_aumenta_mastery(self):
        tentativa = ActivityAttempt.objects.create(
            activity=self.atividade_com_gabarito, student=self.aluno,
            answer="1/2", score=0, time_spent=60)
        AdaptationService().score_attempt(tentativa)

        estado = StudentSkill.objects.get(student=self.aluno, skill=self.skill)
        self.assertEqual(estado.mastery_level, 5)  # 0 (default) + 5 (score>=85)
        registro = ProgressRecord.objects.get(student=self.aluno, skill=self.skill)
        self.assertEqual(registro.source, ProgressRecord.Source.ACTIVITY)

    def test_atividade_com_gabarito_e_erro_reduz_mastery_sem_ficar_negativo(self):
        tentativa = ActivityAttempt.objects.create(
            activity=self.atividade_com_gabarito, student=self.aluno,
            answer="resposta errada", score=0, time_spent=60)
        AdaptationService().score_attempt(tentativa)

        estado = StudentSkill.objects.get(student=self.aluno, skill=self.skill)
        self.assertEqual(estado.mastery_level, 0)  # max(0, 0 - 5) = 0, nunca negativo
