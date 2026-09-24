"""
Testes do comando seed_demo_data — focados na limpeza de resíduo entre
execuções (o bug real que motivou esses testes: Skill/StudentSkill/
Diagnostic de uma versão antiga do currículo sobrevivendo silenciosamente
depois de um reseed, porque get_or_create nunca detecta rename).
"""
from django.core.management import call_command
from django.test import TestCase

from assessments.models import Assessment, AssessmentQuestion
from learning.models import Diagnostic, StudentSkill
from subjects.models import Skill, Subject
from users.models import User


class SeedDemoDataCleanupTests(TestCase):
    def test_rodar_duas_vezes_seguidas_nao_duplica_nem_deixa_orfa(self):
        call_command("seed_demo_data")
        contagem_skills_1 = Skill.objects.count()
        contagem_studentskill_1 = StudentSkill.objects.count()

        call_command("seed_demo_data")
        contagem_skills_2 = Skill.objects.count()
        contagem_studentskill_2 = StudentSkill.objects.count()

        self.assertEqual(contagem_skills_1, contagem_skills_2)
        self.assertEqual(contagem_studentskill_1, contagem_studentskill_2)

    def test_skill_com_nome_antigo_e_removida_no_proximo_reseed(self):
        """O cenário exato do bug: uma Skill de uma versão anterior do
        currículo (nome sem o sufixo de série), com StudentSkill,
        Diagnostic e AssessmentQuestion grudados nela — tudo isso deve
        sumir no próximo reseed, sem levantar erro de FK protegida."""
        call_command("seed_demo_data")
        joana = User.objects.get(username="joana")
        materia = Subject.objects.get(name="Matemática")

        skill_orfa = Skill.objects.create(
            subject=materia, name="Sistemas de Equações (nome antigo)", difficulty_level="advanced")
        avaliacao_antiga = Assessment.objects.create(
            student=joana, subject=materia, title="[ANTIGA] Prova", date="2026-01-01", score=20)
        AssessmentQuestion.objects.create(
            assessment=avaliacao_antiga, skill=skill_orfa, question="q",
            correct_answer="a", student_answer="b", is_correct=False)
        StudentSkill.objects.create(student=joana, skill=skill_orfa, mastery_level=20)
        Diagnostic.objects.create(
            student=joana, skill=skill_orfa, mastery_level=20,
            difficulty_level="advanced", evidence=["antigo"])

        call_command("seed_demo_data")  # não deve levantar ProtectedError

        self.assertFalse(Skill.objects.filter(id=skill_orfa.id).exists())
        self.assertFalse(StudentSkill.objects.filter(student=joana, skill_id=skill_orfa.id).exists())
        self.assertFalse(Diagnostic.objects.filter(student=joana, skill_id=skill_orfa.id).exists())
        # O currículo atual (nome novo) continua intacto.
        self.assertTrue(Skill.objects.filter(subject=materia, name="Sistemas de Equações — 9º ano").exists())

    def test_joana_termina_com_exatamente_8_habilidades_diagnosticadas_apos_reseed(self):
        """Trava de regressão direta pro bug relatado: depois de gerar e
        aprovar todos os diagnósticos, a Joana deve ter EXATAMENTE 8
        StudentSkill — nem a mais (resíduo), nem a menos."""
        from rest_framework.test import APIClient

        call_command("seed_demo_data")
        client = APIClient()
        joana = User.objects.get(username="joana")
        professor = User.objects.get(username="prof_ana")

        client.force_authenticate(user=joana)
        resp = client.post("/api/diagnostics/generate/")
        self.assertEqual(len(resp.data["diagnostics"]), 8)

        client.force_authenticate(user=professor)
        for diag in resp.data["diagnostics"]:
            client.patch(f"/api/diagnostics/{diag['id']}/approve/", {"status": "approved"}, format="json")

        self.assertEqual(StudentSkill.objects.filter(student=joana).count(), 8)
