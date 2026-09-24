"""
Testes de find_root_causes / analisar_causa_raiz — a busca recursiva de
causa raiz na árvore de Skill.prerequisites (que pode atravessar
disciplinas diferentes).
"""
from django.test import TestCase

from learning.models import StudentSkill
from subjects.models import Skill, Subject
from users.models import User

from .diagnostic import MASTERY_THRESHOLD_MEDIUM, analisar_causa_raiz, find_root_causes


class FindRootCausesTests(TestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.matematica = Subject.objects.create(name="Matemática")
        self.fracoes = Skill.objects.create(subject=self.matematica, name="Frações")
        self.equacoes = Skill.objects.create(subject=self.matematica, name="Equações do 1º Grau")
        self.sistemas = Skill.objects.create(subject=self.matematica, name="Sistemas de Equações")
        self.sistemas.prerequisites.set([self.fracoes, self.equacoes])

    def _definir_mastery(self, skill, valor):
        StudentSkill.objects.update_or_create(
            student=self.aluno, skill=skill, defaults={"mastery_level": valor})

    def test_sem_prerequisito_a_propria_habilidade_e_a_causa_raiz(self):
        causas = find_root_causes(self.aluno, self.fracoes)
        self.assertEqual(len(causas), 1)
        self.assertEqual(causas[0]["skill_id"], self.fracoes.id)

    def test_prerequisito_dominado_nao_e_causa_a_propria_habilidade_e(self):
        """Sistemas fraco, mas os dois pré-requisitos já dominados (>=70)
        -> a causa raiz é a própria Sistemas de Equações, não os
        pré-requisitos."""
        self._definir_mastery(self.fracoes, 90)
        self._definir_mastery(self.equacoes, 85)
        causas = find_root_causes(self.aluno, self.sistemas)
        self.assertEqual(len(causas), 1)
        self.assertEqual(causas[0]["skill_id"], self.sistemas.id)

    def test_prerequisito_sem_dado_nenhum_nao_e_tratado_como_causa(self):
        """Aluno nunca foi diagnosticado no pré-requisito -> não sabemos,
        NUNCA tratamos como causa (não inventa problema onde não há dado)."""
        causas = find_root_causes(self.aluno, self.sistemas)
        self.assertEqual(len(causas), 1)
        self.assertEqual(causas[0]["skill_id"], self.sistemas.id)

    def test_um_prerequisito_fraco_aponta_ele_como_causa(self):
        self._definir_mastery(self.fracoes, 30)  # fraco
        self._definir_mastery(self.equacoes, 85)  # dominado
        causas = find_root_causes(self.aluno, self.sistemas)
        self.assertEqual(len(causas), 1)
        self.assertEqual(causas[0]["skill_id"], self.fracoes.id)

    def test_dois_prerequisitos_fracos_ao_mesmo_tempo_retorna_os_dois(self):
        self._definir_mastery(self.fracoes, 20)
        self._definir_mastery(self.equacoes, 25)
        causas = find_root_causes(self.aluno, self.sistemas)
        ids = {c["skill_id"] for c in causas}
        self.assertEqual(ids, {self.fracoes.id, self.equacoes.id})

    def test_cadeia_de_dois_niveis_desce_ate_a_causa_mais_funda(self):
        """Frações depende de uma habilidade ainda mais básica — se essa
        também estiver fraca, a causa raiz deve ser ELA, não Frações."""
        numeros = Skill.objects.create(subject=self.matematica, name="Números Naturais")
        self.fracoes.prerequisites.set([numeros])
        self._definir_mastery(self.fracoes, 30)
        self._definir_mastery(numeros, 20)
        causas = find_root_causes(self.aluno, self.sistemas)
        self.assertEqual(len(causas), 1)
        self.assertEqual(causas[0]["skill_id"], numeros.id)

    def test_causa_raiz_interdisciplinar_atravessa_subjects_diferentes(self):
        """O caso real do seed: Física depende de Matemática — a causa
        raiz de uma lacuna em Física deve poder apontar pra outra
        disciplina."""
        fisica = Subject.objects.create(name="Física")
        cinematica = Skill.objects.create(subject=fisica, name="Cinemática")
        funcao_quadratica = Skill.objects.create(subject=self.matematica, name="Função Quadrática")
        cinematica.prerequisites.set([funcao_quadratica])

        self._definir_mastery(funcao_quadratica, 15)  # fraco
        resultado = analisar_causa_raiz(self.aluno, cinematica)

        self.assertFalse(resultado["e_a_propria_causa_raiz"])
        self.assertEqual(len(resultado["causas_raiz"]), 1)
        causa = resultado["causas_raiz"][0]
        self.assertEqual(causa["skill_id"], funcao_quadratica.id)
        self.assertEqual(causa["subject_name"], "Matemática")  # disciplina DIFERENTE da diagnosticada

    def test_protegido_contra_ciclo_no_grafo(self):
        """Nunca deveria existir um ciclo real, mas a função não pode
        entrar em recursão infinita se um dia existir por engano."""
        self.fracoes.prerequisites.set([self.sistemas])  # ciclo: sistemas -> fracoes -> sistemas
        self._definir_mastery(self.fracoes, 20)
        self._definir_mastery(self.sistemas, 20)
        try:
            causas = find_root_causes(self.aluno, self.sistemas)
        except RecursionError:
            self.fail("find_root_causes entrou em loop infinito com um ciclo no grafo")
        self.assertIsInstance(causas, list)

    def test_analisar_causa_raiz_empacota_a_habilidade_diagnosticada(self):
        resultado = analisar_causa_raiz(self.aluno, self.fracoes)
        self.assertEqual(resultado["habilidade_diagnosticada"]["skill_id"], self.fracoes.id)
        self.assertTrue(resultado["e_a_propria_causa_raiz"])


class CausaRaizAPITests(TestCase):
    def setUp(self):
        from classrooms.models import Classroom
        from learning.models import Diagnostic
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        self.professor_de_fora = User.objects.create_user(
            username="prof2", password="x", email="p2@t.com", role=User.Role.TEACHER)
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno)

        materia = Subject.objects.create(name="Matemática")
        self.fracoes = Skill.objects.create(subject=materia, name="Frações")
        self.sistemas = Skill.objects.create(subject=materia, name="Sistemas de Equações")
        self.sistemas.prerequisites.set([self.fracoes])
        StudentSkill.objects.create(student=self.aluno, skill=self.fracoes, mastery_level=20)

        self.diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.sistemas, mastery_level=25,
            difficulty_level="advanced", evidence=["teste"])

    def test_dono_do_diagnostico_acessa_causa_raiz(self):
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.get(f"/api/diagnostics/{self.diagnostico.id}/causa-raiz/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["causas_raiz"][0]["skill_id"], self.fracoes.id)

    def test_professor_vinculado_acessa_causa_raiz(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get(f"/api/diagnostics/{self.diagnostico.id}/causa-raiz/")
        self.assertEqual(resp.status_code, 200)

    def test_professor_de_fora_nao_acessa_causa_raiz(self):
        """404, não 403 — mesmo padrão de isolamento do resto do projeto:
        o get_queryset do DiagnosticViewSet já filtra antes."""
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.get(f"/api/diagnostics/{self.diagnostico.id}/causa-raiz/")
        self.assertEqual(resp.status_code, 404)

    def test_outro_aluno_nao_acessa_causa_raiz_de_ninguem(self):
        outro_aluno = User.objects.create_user(
            username="pedro", password="x", email="pe@t.com", role=User.Role.STUDENT)
        self.client.force_authenticate(user=outro_aluno)
        resp = self.client.get(f"/api/diagnostics/{self.diagnostico.id}/causa-raiz/")
        self.assertEqual(resp.status_code, 404)
