"""
Testes do DiagnosticService — o núcleo determinístico não depende de
nenhuma chave de API real; o enriquecimento por IA é testado com um
provider falso (injeção de dependência via AIProvider), sem gastar
nenhuma chamada de verdade.
"""
from django.test import TestCase

from assessments.models import Assessment, AssessmentQuestion
from subjects.models import Skill, Subject
from users.models import User

from .diagnostic import MINIMUM_QUESTIONS_FOR_DIAGNOSIS, DiagnosticService
from .provider import AIProvider


def _criar_questoes(aluno, skill, corretas: int, erradas: int):
    avaliacao = Assessment.objects.create(
        student=aluno, subject=skill.subject, title=f"Prova de {skill.name}",
        date="2026-01-01", score=0)
    for _ in range(corretas):
        AssessmentQuestion.objects.create(
            assessment=avaliacao, skill=skill, question="q", correct_answer="a",
            student_answer="a", is_correct=True)
    for _ in range(erradas):
        AssessmentQuestion.objects.create(
            assessment=avaliacao, skill=skill, question="q", correct_answer="a",
            student_answer="b", is_correct=False)


class DiagnosticServiceTests(TestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Porcentagem", difficulty_level="basic")

    def test_evidencia_insuficiente_quando_poucas_questoes(self):
        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=1)  # total=2 < mínimo 3
        service = DiagnosticService()
        resultado = service.diagnose_skill(self.aluno, self.skill)
        self.assertEqual(resultado.status, "insufficient_evidence")
        self.assertIsNotNone(resultado.missing_info)

    def test_diagnostico_calcula_mastery_level_a_partir_de_dados_reais(self):
        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=4)  # 20% de acerto
        service = DiagnosticService()
        resultado = service.diagnose_skill(self.aluno, self.skill)
        self.assertEqual(resultado.status, "ok")
        self.assertEqual(resultado.mastery_level, 20)
        self.assertEqual(resultado.priority, "high")  # < 40
        self.assertIn("4 de 5 questões", resultado.evidence[0])

    def test_prioridade_media_e_baixa(self):
        _criar_questoes(self.aluno, self.skill, corretas=3, erradas=2)  # 60%
        resultado = DiagnosticService().diagnose_skill(self.aluno, self.skill)
        self.assertEqual(resultado.priority, "medium")

        materia2 = self.skill.subject
        skill2 = Skill.objects.create(subject=materia2, name="Geometria", difficulty_level="basic")
        _criar_questoes(self.aluno, skill2, corretas=9, erradas=1)  # 90%
        resultado2 = DiagnosticService().diagnose_skill(self.aluno, skill2)
        self.assertEqual(resultado2.priority, "low")

    def test_sem_ai_provider_usa_acao_padrao_determinística(self):
        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=4)
        resultado = DiagnosticService(ai_provider=None).diagnose_skill(self.aluno, self.skill)
        self.assertEqual(resultado.recommended_action,
                          "Revisar conceitos fundamentais antes de avançar para conteúdo novo.")

    def test_ai_provider_que_falha_cai_no_padrao_determinístico(self):
        class ProviderQueFalha(AIProvider):
            def generate_structured(self, *a, **kw):
                raise TimeoutError("simulado")

        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=4)
        resultado = DiagnosticService(ai_provider=ProviderQueFalha()).diagnose_skill(self.aluno, self.skill)
        # Não propagou a exceção, e caiu no texto padrão:
        self.assertEqual(resultado.recommended_action,
                          "Revisar conceitos fundamentais antes de avançar para conteúdo novo.")

    def test_ai_provider_funcional_enriquece_a_acao(self):
        class ProviderFalso(AIProvider):
            def generate_structured(self, system_prompt, user_prompt, response_schema):
                return {"recommended_action": "Praticar porcentagem com problemas do dia a dia."}

        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=4)
        resultado = DiagnosticService(ai_provider=ProviderFalso()).diagnose_skill(self.aluno, self.skill)
        self.assertEqual(resultado.recommended_action, "Praticar porcentagem com problemas do dia a dia.")

    def test_persist_diagnostics_grava_como_pending(self):
        from learning.models import Diagnostic

        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=4)
        criados, insuficientes = DiagnosticService().persist_diagnostics(self.aluno)

        self.assertEqual(len(criados), 1)
        self.assertEqual(criados[0].status, Diagnostic.Status.PENDING)  # Seção 1: sempre proposta
        self.assertEqual(criados[0].mastery_level, 20)
        self.assertEqual(insuficientes, [])

    def test_persist_diagnostics_reporta_insuficientes_sem_especular(self):
        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=1)  # total=2, insuficiente
        criados, insuficientes = DiagnosticService().persist_diagnostics(self.aluno)
        self.assertEqual(criados, [])
        self.assertEqual(len(insuficientes), 1)
        self.assertEqual(insuficientes[0]["status"], "insufficient_evidence")

    def test_multiplas_habilidades_ao_mesmo_tempo(self):
        """Seção 16 pede explicitamente testar 'múltiplas habilidades' —
        uma chamada só diagnosticando 2 habilidades com situações diferentes
        (uma com evidência boa, outra insuficiente) na mesma resposta."""
        materia = self.skill.subject
        skill2 = Skill.objects.create(subject=materia, name="Geometria", difficulty_level="basic")
        _criar_questoes(self.aluno, self.skill, corretas=1, erradas=4)  # suficiente, 20%
        _criar_questoes(self.aluno, skill2, corretas=1, erradas=0)      # insuficiente (total=1)

        resultado = DiagnosticService().diagnose_student(self.aluno)
        self.assertEqual(len(resultado["skills"]), 1)
        self.assertEqual(resultado["skills"][0]["skill"], "Porcentagem")
        self.assertEqual(len(resultado["insufficient_evidence"]), 1)
        self.assertEqual(resultado["insufficient_evidence"][0]["skill"], "Geometria")
