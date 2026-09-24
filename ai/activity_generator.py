"""
Gerador de Atividades (Seção 6/7 do escopo).
----------------------------------------------
Diferente do diagnóstico (onde números/evidência NUNCA podem vir da IA),
aqui o conteúdo É criação — título, enunciado, explicação. Por isso a IA
pode gerar esse texto livremente; a garantia que continua valendo é
"adequado ao nível do aluno" e "só para a habilidade certa", que é
imposto em código (a sequência e a dificuldade vêm de `priority_for_mastery`,
não da IA). Sem AIProvider configurado, usa templates determinísticos —
funcionais, só menos elaborados.
"""
import logging

from django.db import transaction

from learning.models import Diagnostic, StudyActivity, StudyPlan
from subjects.models import Skill
from users.models import User

from .diagnostic import priority_for_mastery
from .provider import AIProvider

# Sequência de atividades por prioridade — reflete o exemplo da Seção 6
# (revisão → exercícios → aplicação → miniavaliação), encurtada conforme a
# gravidade: prioridade baixa não precisa repetir revisão do zero.
# Sequência de atividades por prioridade — reflete o exemplo da Seção 6
# (revisão → exercícios → aplicação → miniavaliação), encurtada conforme a
# gravidade: prioridade baixa não precisa repetir revisão do zero.
# Os 8 tipos de atividade da Seção 7 aparecem todos aqui, distribuídos
# pelas 3 faixas — nenhum tipo definido no model fica sem uso real.
ACTIVITY_SEQUENCE_BY_PRIORITY = {
    "high": [
        (StudyActivity.ActivityType.REVIEW, "Revisão de {skill}", 15),
        (StudyActivity.ActivityType.TRUE_FALSE, "Verdadeiro ou falso sobre {skill}", 10),
        (StudyActivity.ActivityType.MULTIPLE_CHOICE, "Exercícios básicos de {skill}", 15),
        (StudyActivity.ActivityType.SHORT_ANSWER, "Perguntas curtas sobre {skill}", 10),
        (StudyActivity.ActivityType.PROBLEM_SOLVING, "Problemas de aplicação de {skill}", 20),
        (StudyActivity.ActivityType.MINI_ASSESSMENT, "Miniavaliação de {skill}", 10),
    ],
    "medium": [
        (StudyActivity.ActivityType.MULTIPLE_CHOICE, "Exercícios de {skill}", 15),
        (StudyActivity.ActivityType.PRACTICAL_EXERCISE, "Exercício prático de {skill}", 20),
        (StudyActivity.ActivityType.PROBLEM_SOLVING, "Problemas de aplicação de {skill}", 20),
        (StudyActivity.ActivityType.MINI_ASSESSMENT, "Miniavaliação de {skill}", 10),
    ],
    "low": [
        (StudyActivity.ActivityType.CHALLENGE, "Desafio avançado de {skill}", 20),
        (StudyActivity.ActivityType.MINI_ASSESSMENT, "Miniavaliação de {skill}", 10),
    ],
}

DEFAULT_TEMPLATES = {
    StudyActivity.ActivityType.REVIEW:
        ("Revise os conceitos fundamentais de {skill} antes de praticar.",
         "Leia o material de referência e anote os pontos que ainda geram dúvida."),
    StudyActivity.ActivityType.TRUE_FALSE:
        ("Responda afirmações de verdadeiro ou falso sobre {skill}.",
         "Justifique mentalmente cada resposta antes de decidir — não vale chutar."),
    StudyActivity.ActivityType.MULTIPLE_CHOICE:
        ("Responda questões de múltipla escolha sobre {skill}.",
         "Leia cada alternativa com atenção antes de escolher."),
    StudyActivity.ActivityType.SHORT_ANSWER:
        ("Responda perguntas curtas e diretas sobre {skill}.",
         "Respostas objetivas — não precisa de texto longo."),
    StudyActivity.ActivityType.PROBLEM_SOLVING:
        ("Resolva um problema contextualizado envolvendo {skill}.",
         "Mostre o passo a passo do raciocínio, não só a resposta final."),
    StudyActivity.ActivityType.PRACTICAL_EXERCISE:
        ("Pratique {skill} aplicada a uma situação do dia a dia.",
         "O objetivo é ver o conceito funcionando fora do papel."),
    StudyActivity.ActivityType.CHALLENGE:
        ("Resolva um desafio avançado envolvendo {skill}.",
         "Este exercício é mais difícil de propósito — você já domina o básico."),
    StudyActivity.ActivityType.MINI_ASSESSMENT:
        ("Miniavaliação para confirmar o domínio de {skill}.",
         "Responda sem consultar material de apoio, como em uma prova."),
}


def build_activity_content(skill: Skill, activity_type: str, difficulty: str,
                            ai_provider: AIProvider | None = None) -> dict:
    """Extraída como função de módulo (não só método de
    ActivityGeneratorService) porque ai/recommendation.py (adaptação)
    também precisa montar o conteúdo de UMA atividade nova ao decidir
    subir/reduzir dificuldade — duplicar o template em dois lugares seria
    o tipo de coisa que descasa silenciosamente."""
    descricao_padrao, instrucoes_padrao = DEFAULT_TEMPLATES[activity_type]
    conteudo = {
        "description": descricao_padrao.format(skill=skill.name),
        "instructions": instrucoes_padrao.format(skill=skill.name),
        "expected_answer": "",  # sem gabarito automático nesta versão — ver nota na Etapa 8
        "explanation": f"Esta atividade trabalha diretamente a habilidade '{skill.name}'.",
    }

    if ai_provider is None:
        return conteudo

    try:
        resposta = ai_provider.generate_structured(
            system_prompt=(
                "Você cria o enunciado de UMA atividade de estudo, adequada ao nível "
                "informado. Responda apenas com JSON: {\"description\": \"...\", "
                "\"instructions\": \"...\", \"explanation\": \"...\"}. Sem gabarito "
                "(expected_answer não faz parte da resposta)."
            ),
            user_prompt=(f"Habilidade: {skill.name}\nTipo de atividade: {activity_type}\n"
                         f"Nível de dificuldade: {difficulty}"),
            response_schema={"description": str, "instructions": str, "explanation": str},
        )
        for campo in ("description", "instructions", "explanation"):
            if resposta.get(campo):
                conteudo[campo] = resposta[campo]
    except (TimeoutError, ValueError, KeyError) as e:
        logging.getLogger(__name__).warning("Enriquecimento de IA falhou, usando template padrão: %s", e)

    return conteudo


class ActivityGeneratorService:
    def __init__(self, ai_provider: AIProvider | None = None):
        self.ai_provider = ai_provider

    def _build_content(self, skill: Skill, activity_type: str, difficulty: str) -> dict:
        return build_activity_content(skill, activity_type, difficulty, self.ai_provider)

    DIAS_MINIMOS_PLANO = 7
    DIAS_MAXIMOS_PLANO = 30

    @transaction.atomic
    def generate_plan_from_diagnostics(self, student: User, diagnostics) -> StudyPlan:
        """Gera um StudyPlan + StudyActivities a partir de diagnósticos já
        APROVADOS (Seção 1: só depois da validação humana). `diagnostics`
        é um iterável de Diagnostic — quem chama decide quais entram
        (normalmente: todos os aprovados/modificados ainda não usados
        num plano).

        A duração do plano (`end_date`) é calculada a partir da carga
        total de minutos ÷ tempo disponível por dia — não é mais fixa em
        7 dias. Sem isso, várias disciplinas com prioridade alta ao mesmo
        tempo entulhavam um plano de 1 semana com dezenas de atividades
        (6 disciplinas × 6 atividades = 36, bem acima do que um aluno com
        30 min/dia disponíveis consegue cumprir em 7 dias). Nenhuma
        atividade é descartada — a lacuna continua real — só o prazo se
        ajusta pra caber no ritmo do aluno.
        """
        import math
        from datetime import date, timedelta

        tempo_disponivel = getattr(
            getattr(student, "student_profile", None), "study_time_available", 30)
        if not tempo_disponivel or tempo_disponivel <= 0:
            tempo_disponivel = 30

        # Monta a lista de atividades ANTES de criar o StudyPlan, pra
        # poder somar a carga total e só então decidir a duração.
        atividades_planejadas = []
        for diagnostico in diagnostics:
            prioridade = priority_for_mastery(diagnostico.mastery_level)
            sequencia = ACTIVITY_SEQUENCE_BY_PRIORITY[prioridade]
            for activity_type, titulo_template, minutos_base in sequencia:
                # Não deixa uma única atividade estourar sozinha o tempo
                # diário disponível — reduz proporcionalmente se preciso.
                minutos = min(minutos_base, max(tempo_disponivel, 10))
                atividades_planejadas.append({
                    "diagnostico": diagnostico, "activity_type": activity_type,
                    "titulo_template": titulo_template, "minutos": minutos,
                })

        total_minutos = sum(item["minutos"] for item in atividades_planejadas)
        dias_pela_carga = math.ceil(total_minutos / tempo_disponivel)
        duracao_dias = max(self.DIAS_MINIMOS_PLANO, min(dias_pela_carga, self.DIAS_MAXIMOS_PLANO))

        plano = StudyPlan.objects.create(
            student=student, created_by_ai=True, status=StudyPlan.Status.DRAFT,
            start_date=date.today(), end_date=date.today() + timedelta(days=duracao_dias),
        )

        for ordem, item in enumerate(atividades_planejadas, start=1):
            diagnostico = item["diagnostico"]
            conteudo = self._build_content(diagnostico.skill, item["activity_type"],
                                            diagnostico.difficulty_level)
            StudyActivity.objects.create(
                study_plan=plano, skill=diagnostico.skill,
                title=item["titulo_template"].format(skill=diagnostico.skill.name),
                description=conteudo["description"], activity_type=item["activity_type"],
                difficulty=diagnostico.difficulty_level, estimated_minutes=item["minutos"],
                instructions=conteudo["instructions"],
                expected_answer=conteudo["expected_answer"],
                explanation=conteudo["explanation"], order=ordem,
            )

        return plano


def build_default_service() -> ActivityGeneratorService:
    from .provider import get_default_provider
    return ActivityGeneratorService(ai_provider=get_default_provider())
