"""
Popula o banco com dados de demonstração — um cenário realista pra testar
o fluxo completo (diagnóstico → aprovação → plano → atividade →
dashboards) sem precisar cadastrar tudo na mão pelo /admin/.

Uso:
    python manage.py seed_demo_data

Idempotente para usuários/disciplinas (get_or_create); as avaliações de
demonstração, os diagnósticos e os StudentSkill de joana/pedro são
recriados do ZERO a cada execução — sem isso, todo diagnóstico/plano
aprovado numa sessão de teste anterior ficaria acumulado silenciosamente
pra sempre no banco local, e uma renomeação de habilidade entre versões
do currículo (ex.: "Sistemas de Equações" → "Sistemas de Equações — 9º
ano") deixaria uma Skill órfã com histórico fantasma grudado nela — foi
exatamente isso que aconteceu antes desta correção.

Currículo de demonstração cobre Ensino Fundamental II e Ensino Médio, em
9 disciplinas — pra mostrar que o sistema não é só matemática. Isso é
uma simplificação deliberada pra fins de portfólio: a Joana (uma única
aluna) tem lacunas registradas em habilidades de várias séries diferentes
ao mesmo tempo, o que não existiria de verdade num cenário real (um aluno
está numa série só), mas deixa a tela do plano de estudo mostrando a
amplitude real do sistema numa demonstração só.
"""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from assessments.models import Assessment, AssessmentQuestion
from classrooms.models import Classroom
from learning.models import Diagnostic, StudentSkill
from students.models import StudentProfile
from subjects.models import Skill, Subject
from teachers.models import TeacherProfile
from users.models import User

SENHA_DEMO = "DemoSenha123!"

BASIC = Skill.DifficultyLevel.BASIC
INTERMEDIATE = Skill.DifficultyLevel.INTERMEDIATE
ADVANCED = Skill.DifficultyLevel.ADVANCED
FUND2 = Skill.Stage.FUNDAMENTAL_II
EM = Skill.Stage.ENSINO_MEDIO


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração (aluno, professor, disciplinas, avaliações)."

    def _criar_disciplina_com_habilidades(self, nome, descricao, habilidades):
        """habilidades: lista de (nome, difficulty_level, stage, grade) —
        devolve a Subject e um dict {nome_da_habilidade: instância}."""
        materia, _ = Subject.objects.get_or_create(name=nome, defaults={"description": descricao})
        criadas = {}
        for nome_habilidade, nivel, etapa, serie in habilidades:
            skill, _ = Skill.objects.get_or_create(
                subject=materia, name=nome_habilidade,
                defaults={"difficulty_level": nivel, "stage": etapa, "grade": serie})
            criadas[nome_habilidade] = skill
        return materia, criadas

    def handle(self, *args, **options):
        # --- Currículo: Fundamental II + Ensino Médio, 9 disciplinas ---
        matematica, sk_mat = self._criar_disciplina_com_habilidades(
            "Matemática", "Matemática — Fundamental II e Ensino Médio",
            [("Frações — 6º ano", BASIC, FUND2, 6),
             ("Equações do 1º Grau — 8º ano", INTERMEDIATE, FUND2, 8),
             ("Sistemas de Equações — 9º ano", ADVANCED, FUND2, 9),
             ("Função Quadrática — 1º ano EM", ADVANCED, EM, 1)])
        sk_mat["Sistemas de Equações — 9º ano"].prerequisites.set(
            [sk_mat["Frações — 6º ano"], sk_mat["Equações do 1º Grau — 8º ano"]])

        portugues, sk_port = self._criar_disciplina_com_habilidades(
            "Português", "Língua Portuguesa — Fundamental II e Ensino Médio",
            [("Interpretação de Texto — 7º ano", BASIC, FUND2, 7),
             ("Concordância Verbal — 9º ano", INTERMEDIATE, FUND2, 9),
             ("Redação Dissertativa — 3º ano EM", ADVANCED, EM, 3)])

        ciencias, sk_cie = self._criar_disciplina_com_habilidades(
            "Ciências", "Ciências — Fundamental II",
            [("Ciclo da Água — 6º ano", BASIC, FUND2, 6),
             ("Genética Básica — 9º ano", INTERMEDIATE, FUND2, 9)])

        biologia, sk_bio = self._criar_disciplina_com_habilidades(
            "Biologia", "Biologia — Ensino Médio",
            [("Citologia — 1º ano EM", BASIC, EM, 1),
             ("Genética Mendeliana — 2º ano EM", INTERMEDIATE, EM, 2)])
        # Interdisciplinar dentro da própria "família": Genética do EM
        # aprofunda a Genética Básica do Fundamental II.
        sk_bio["Genética Mendeliana — 2º ano EM"].prerequisites.set(
            [sk_cie["Genética Básica — 9º ano"]])

        fisica, sk_fis = self._criar_disciplina_com_habilidades(
            "Física", "Física — Ensino Médio",
            [("Cinemática — 1º ano EM", BASIC, EM, 1),
             ("Leis de Newton — 2º ano EM", INTERMEDIATE, EM, 2)])
        # Interdisciplinar de verdade (disciplinas diferentes): Cinemática
        # depende de Função Quadrática — é o que faz a causa raiz de uma
        # lacuna em Física poder apontar pra Matemática (find_root_causes
        # em ai/diagnostic.py).
        sk_fis["Cinemática — 1º ano EM"].prerequisites.set(
            [sk_mat["Função Quadrática — 1º ano EM"]])
        sk_fis["Leis de Newton — 2º ano EM"].prerequisites.set(
            [sk_fis["Cinemática — 1º ano EM"]])

        quimica, sk_qui = self._criar_disciplina_com_habilidades(
            "Química", "Química — Ensino Médio",
            [("Tabela Periódica — 1º ano EM", BASIC, EM, 1),
             ("Ligações Químicas — 2º ano EM", INTERMEDIATE, EM, 2)])

        historia, sk_his = self._criar_disciplina_com_habilidades(
            "História", "História — Fundamental II e Ensino Médio",
            [("Brasil Colônia — 7º ano", BASIC, FUND2, 7),
             ("Revolução Industrial — 8º ano", INTERMEDIATE, FUND2, 8),
             ("Guerra Fria — 3º ano EM", ADVANCED, EM, 3)])

        geografia, sk_geo = self._criar_disciplina_com_habilidades(
            "Geografia", "Geografia — Fundamental II e Ensino Médio",
            [("Placas Tectônicas — 6º ano", BASIC, FUND2, 6),
             ("Globalização — 9º ano", INTERMEDIATE, FUND2, 9)])

        ingles, sk_ing = self._criar_disciplina_com_habilidades(
            "Inglês", "Língua Inglesa — Fundamental II e Ensino Médio",
            [("Simple Past — 7º ano", BASIC, FUND2, 7),
             ("Present Perfect — 9º ano", INTERMEDIATE, FUND2, 9)])

        # --- Limpeza de Skill órfã (nome antigo, de antes de uma renomeação
        # no currículo) — sem isso, uma Skill como a antiga "Sistemas de
        # Equações" (sem sufixo de série) ficaria pra sempre no banco,
        # carregando StudentSkill/Diagnostic fantasma de sessões antigas
        # mesmo depois do reseed, já que get_or_create nunca detecta rename.
        disciplinas_e_habilidades_validas = [
            (matematica, sk_mat), (portugues, sk_port), (ciencias, sk_cie),
            (biologia, sk_bio), (fisica, sk_fis), (quimica, sk_qui),
            (historia, sk_his), (geografia, sk_geo), (ingles, sk_ing),
        ]
        total_orfas = 0
        for materia_obj, habilidades_validas in disciplinas_e_habilidades_validas:
            orfas = Skill.objects.filter(subject=materia_obj).exclude(name__in=habilidades_validas.keys())
            if orfas.exists():
                total_orfas += orfas.count()
                # AssessmentQuestion.skill é PROTECT — precisa esvaziar antes
                # de conseguir apagar a Skill em si.
                AssessmentQuestion.objects.filter(skill__in=orfas).delete()
                orfas.delete()
        if total_orfas:
            self.stdout.write(self.style.WARNING(
                f"Removidas {total_orfas} Skill(s) órfã(s) de versões anteriores do currículo "
                "(nome antigo que não existe mais) — evita histórico fantasma."))

        self.stdout.write(self.style.SUCCESS(
            "9 disciplinas com habilidades cobrindo Fundamental II e Ensino Médio "
            "(Matemática, Português, Ciências, Biologia, Física, Química, "
            "História, Geografia, Inglês) — incluindo um pré-requisito "
            "interdisciplinar real (Física·Cinemática depende de Matemática·"
            "Função Quadrática), pra causa raiz poder atravessar disciplinas."))

        # --- Usuários ---
        professor, criado_prof = User.objects.get_or_create(
            username="prof_ana", defaults={
                "email": "ana@escola-demo.com", "role": User.Role.TEACHER,
                "first_name": "Ana", "password": make_password(SENHA_DEMO),
            })
        if not criado_prof:
            professor.set_password(SENHA_DEMO)
            professor.save()
        TeacherProfile.objects.get_or_create(user=professor)

        joana, criada_joana = User.objects.get_or_create(
            username="joana", defaults={
                "email": "joana@escola-demo.com", "role": User.Role.STUDENT,
                "first_name": "Joana", "password": make_password(SENHA_DEMO),
            })
        if not criada_joana:
            joana.set_password(SENHA_DEMO)
            joana.save()
        StudentProfile.objects.update_or_create(
            user=joana, defaults={"grade_level": "9º ano", "study_time_available": 30})

        pedro, criado_pedro = User.objects.get_or_create(
            username="pedro", defaults={
                "email": "pedro@escola-demo.com", "role": User.Role.STUDENT,
                "first_name": "Pedro", "password": make_password(SENHA_DEMO),
            })
        if not criado_pedro:
            pedro.set_password(SENHA_DEMO)
            pedro.save()
        StudentProfile.objects.update_or_create(
            user=pedro, defaults={"grade_level": "8º ano", "study_time_available": 45})

        self.stdout.write(self.style.SUCCESS(
            f"Usuários prontos: professor 'prof_ana', alunos 'joana' e 'pedro' (senha: {SENHA_DEMO})."))

        turma, _ = Classroom.objects.get_or_create(name="8º Ano A - Demo")
        turma.teachers.set([professor])
        turma.students.set([joana, pedro])
        self.stdout.write(self.style.SUCCESS(
            "Turma '8º Ano A - Demo' criada, vinculando prof_ana a joana e pedro — "
            "sem essa turma, a professora não veria nenhum dos dois nos dashboards."))

        # --- Avaliações de demonstração (recriadas do zero a cada execução) ---
        Assessment.objects.filter(student__in=[joana, pedro], title__startswith="[DEMO]").delete()
        # Diagnostic e StudentSkill NÃO eram limpos antes — sobreviviam de
        # sessão pra sessão, fazendo o "progresso médio" e as habilidades
        # sincronizadas de execuções antigas (inclusive com nomes de Skill
        # que já não existem mais no currículo atual) aparecerem
        # silenciosamente na tela, mesmo depois de reseed.
        Diagnostic.objects.filter(student__in=[joana, pedro]).delete()
        StudentSkill.objects.filter(student__in=[joana, pedro]).delete()

        # Joana: lacuna em 8 habilidades de 7 disciplinas diferentes
        # (Fundamental II e Ensino Médio misturados de propósito — ver
        # docstring do módulo) — 4 de 5 erradas em cada, prioridade ALTA.
        lacunas_joana = [
            (matematica, sk_mat["Sistemas de Equações — 9º ano"], "Resolva o sistema de equações"),
            (matematica, sk_mat["Função Quadrática — 1º ano EM"], "Resolva a função quadrática"),
            (portugues, sk_port["Interpretação de Texto — 7º ano"], "Interprete o texto e responda"),
            (ciencias, sk_cie["Genética Básica — 9º ano"], "Explique o conceito de genética"),
            (biologia, sk_bio["Citologia — 1º ano EM"], "Identifique a estrutura celular"),
            (fisica, sk_fis["Cinemática — 1º ano EM"], "Calcule a velocidade média"),
            (historia, sk_his["Guerra Fria — 3º ano EM"], "Explique o contexto da Guerra Fria"),
            (ingles, sk_ing["Present Perfect — 9º ano"], "Complete a frase em Present Perfect"),
        ]
        for materia_da_questao, habilidade, enunciado in lacunas_joana:
            av = Assessment.objects.create(
                student=joana, subject=materia_da_questao, title="[DEMO] Avaliação Bimestral",
                date="2026-09-01", score=35)
            for i, correta in enumerate([False, False, False, False, True]):
                AssessmentQuestion.objects.create(
                    assessment=av, skill=habilidade,
                    question=f"{enunciado} (questão {i + 1})",
                    correct_answer="resposta correta",
                    student_answer="resposta correta" if correta else "resposta incorreta",
                    is_correct=correta,
                )

        # Pedro: continua só em Matemática, com bom desempenho — contraste
        # de prioridade BAIXA pra comparar com a Joana.
        av_pedro = Assessment.objects.create(
            student=pedro, subject=matematica, title="[DEMO] Avaliação Bimestral", date="2026-09-01", score=85)
        for i, correta in enumerate([True, True, True, False, True]):
            AssessmentQuestion.objects.create(
                assessment=av_pedro, skill=sk_mat["Sistemas de Equações — 9º ano"],
                question=f"Resolva o sistema de equações (questão {i + 1})",
                correct_answer="x=2, y=3",
                student_answer="x=2, y=3" if correta else "x=1, y=1",
                is_correct=correta,
            )

        self.stdout.write(self.style.SUCCESS(
            "Avaliações de demonstração criadas: Joana com desempenho baixo (20%) em "
            "8 habilidades de 7 disciplinas diferentes (Matemática, Português, Ciências, "
            "Biologia, Física, História, Inglês) — deve gerar diagnósticos de prioridade "
            "ALTA em todas. Pedro com desempenho alto (80%) só em Matemática, pra comparar."))

        self.stdout.write(self.style.SUCCESS("\nPronto! Credenciais de teste:"))
        self.stdout.write(f"  Professor: prof_ana / {SENHA_DEMO}")
        self.stdout.write(f"  Aluna:     joana    / {SENHA_DEMO}  (lacunas em 7 disciplinas, incluindo pré-requisito interdisciplinar)")
        self.stdout.write(f"  Aluno:     pedro    / {SENHA_DEMO}  (desempenho alto em Matemática)")
