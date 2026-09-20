"""
Popula o banco com dados de demonstração — um cenário realista pra testar
o fluxo completo (diagnóstico → aprovação → plano → atividade →
dashboards) sem precisar cadastrar tudo na mão pelo /admin/.

Uso:
    python manage.py seed_demo_data

Idempotente para usuários/disciplinas/habilidades (get_or_create); as
avaliações de demonstração são recriadas do zero a cada execução, pra
sempre gerar o mesmo cenário previsível (senão o mastery_level mudaria a
cada vez que o comando rodasse de novo, já que o diagnóstico soma TODAS
as questões já registradas).
"""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from assessments.models import Assessment, AssessmentQuestion
from students.models import StudentProfile
from subjects.models import Skill, Subject
from teachers.models import TeacherProfile
from users.models import User

SENHA_DEMO = "DemoSenha123!"


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração (aluno, professor, disciplina, avaliações)."

    def handle(self, *args, **options):
        materia, _ = Subject.objects.get_or_create(
            name="Matemática", defaults={"description": "Matemática — Ensino Fundamental II"})

        fracoes, _ = Skill.objects.get_or_create(
            subject=materia, name="Frações", defaults={"difficulty_level": Skill.DifficultyLevel.BASIC})
        equacoes, _ = Skill.objects.get_or_create(
            subject=materia, name="Equações do 1º Grau",
            defaults={"difficulty_level": Skill.DifficultyLevel.INTERMEDIATE})
        sistemas, _ = Skill.objects.get_or_create(
            subject=materia, name="Sistemas de Equações",
            defaults={"difficulty_level": Skill.DifficultyLevel.ADVANCED})
        sistemas.prerequisites.set([fracoes, equacoes])
        self.stdout.write(self.style.SUCCESS(
            f"Disciplina '{materia.name}' com 3 habilidades (grafo de pré-requisitos configurado)."))

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
            user=joana, defaults={"grade_level": "8º ano", "study_time_available": 30})

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

        # Recria as avaliações de demonstração do zero, pra sempre dar o
        # mesmo cenário previsível (mastery_level é calculado a partir de
        # TODA questão já registrada, então rodar o comando 2x não pode
        # duplicar dado e mudar o resultado).
        Assessment.objects.filter(student__in=[joana, pedro], title__startswith="[DEMO]").delete()

        av_joana = Assessment.objects.create(
            student=joana, subject=materia, title="[DEMO] Avaliação Bimestral", date="2026-09-01", score=35)
        # Joana: 4 de 5 erradas em Sistemas de Equações -> 20% -> prioridade "high"
        for i, correta in enumerate([False, False, False, False, True]):
            AssessmentQuestion.objects.create(
                assessment=av_joana, skill=sistemas,
                question=f"Resolva o sistema de equações (questão {i + 1})",
                correct_answer="x=2, y=3",
                student_answer="x=2, y=3" if correta else "x=1, y=1",
                is_correct=correta,
            )

        av_pedro = Assessment.objects.create(
            student=pedro, subject=materia, title="[DEMO] Avaliação Bimestral", date="2026-09-01", score=85)
        # Pedro: 4 de 5 corretas em Sistemas de Equações -> 80% -> prioridade "low"
        for i, correta in enumerate([True, True, True, False, True]):
            AssessmentQuestion.objects.create(
                assessment=av_pedro, skill=sistemas,
                question=f"Resolva o sistema de equações (questão {i + 1})",
                correct_answer="x=2, y=3",
                student_answer="x=2, y=3" if correta else "x=1, y=1",
                is_correct=correta,
            )

        self.stdout.write(self.style.SUCCESS(
            "Avaliações de demonstração criadas: Joana com desempenho baixo (20%) em "
            "'Sistemas de Equações' — deve gerar diagnóstico de prioridade ALTA. Pedro com "
            "desempenho alto (80%) na mesma habilidade — prioridade BAIXA, pra comparar."))

        self.stdout.write(self.style.SUCCESS("\nPronto! Credenciais de teste:"))
        self.stdout.write(f"  Professor: prof_ana / {SENHA_DEMO}")
        self.stdout.write(f"  Aluna:     joana    / {SENHA_DEMO}  (desempenho baixo)")
        self.stdout.write(f"  Aluno:     pedro    / {SENHA_DEMO}  (desempenho alto)")
