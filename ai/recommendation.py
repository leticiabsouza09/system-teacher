"""
Sistema de Adaptação (Seção 8 do escopo).
--------------------------------------------
Regras aplicadas em código, não em prompt de IA — são regras de negócio
determinísticas, não algo que se "pede" pra um modelo de linguagem decidir:
  score >= 85            -> aumentar dificuldade gradualmente
  60 <= score < 85        -> manter nível, trabalhar os erros
  score < 60              -> revisar conceitos, reduzir dificuldade temporariamente
  dificuldade persistente -> sinalizar professor, NUNCA aumentar sozinho

"Uma única resposta incorreta não deve ser suficiente para classificar uma
habilidade como não dominada" (Seção 8) já é garantido pelo próprio
DiagnosticService (MINIMUM_QUESTIONS_FOR_DIAGNOSIS) — a adaptação aqui
trabalha em cima do SCORE DE UMA ATIVIDADE (que já agrega várias questões
daquela atividade), não de uma resposta isolada.
"""
from django.db import models
from django.db.models import Max

from learning.models import ActivityAttempt, Diagnostic, StudyActivity
from subjects.models import Skill
from users.models import User

from .activity_generator import build_activity_content

SCORE_HIGH = 85
SCORE_LOW = 60
PERSISTENT_FAILURE_THRESHOLD = 3  # tentativas consecutivas abaixo de SCORE_LOW

DIFFICULTY_ORDER = [Skill.DifficultyLevel.BASIC, Skill.DifficultyLevel.INTERMEDIATE,
                    Skill.DifficultyLevel.ADVANCED]

# Que TIPO de atividade gerar automaticamente para cada decisão de
# adaptação — "maintain" e "flagged_for_teacher" não geram nada sozinhos
# (Seção 8: dificuldade persistente nunca ajusta automaticamente).
TIPO_PROXIMA_ATIVIDADE_POR_ACAO = {
    "increase_difficulty": StudyActivity.ActivityType.PROBLEM_SOLVING,
    "reduce_difficulty_temporarily": StudyActivity.ActivityType.REVIEW,
}
TITULO_PROXIMA_ATIVIDADE_POR_ACAO = {
    "increase_difficulty": "Avançando em {skill}",
    "reduce_difficulty_temporarily": "Reforço de {skill}",
}


def _proxima_dificuldade(atual: str, subir: bool) -> str:
    """Sobe ou desce um degrau na escala Básico→Intermediário→Avançado,
    sem passar dos limites (nunca 'sobe' do Avançado nem 'desce' do Básico)."""
    indice = DIFFICULTY_ORDER.index(atual)
    novo_indice = indice + 1 if subir else indice - 1
    novo_indice = max(0, min(novo_indice, len(DIFFICULTY_ORDER) - 1))
    return DIFFICULTY_ORDER[novo_indice]


class AdaptationService:
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider

    def score_attempt(self, attempt: ActivityAttempt) -> ActivityAttempt:
        """Corrige a tentativa. Sem gabarito (expected_answer vazio), a
        atividade precisa de correção manual do professor — não inventamos
        uma nota; deixamos None de propósito (nunca 0 disfarçado de nota real)."""
        gabarito = (attempt.activity.expected_answer or "").strip()
        if not gabarito:
            return attempt  # score permanece como veio (0, definido na criação) — sem gabarito automático

        acertou = attempt.answer.strip().lower() == gabarito.lower()
        attempt.score = 100 if acertou else 0
        attempt.save(update_fields=["score"])
        return attempt

    def apply_adaptation(self, student: User, skill: Skill) -> dict:
        """Roda depois de cada tentativa: decide a ação (subir/manter/
        reduzir dificuldade, ou sinalizar o professor) com base nas
        tentativas recentes daquele aluno naquela habilidade — e, quando a
        ação for subir/reduzir dificuldade, JÁ GERA a próxima atividade
        real no plano, no nível ajustado (não fica só como informação na
        resposta da API, como acontecia antes desta versão)."""
        tentativas = list(ActivityAttempt.objects.filter(
            student=student, activity__skill=skill
        ).order_by("-completed_at")[:PERSISTENT_FAILURE_THRESHOLD])

        if not tentativas:
            return {"action": "none", "reason": "Sem tentativas registradas para esta habilidade."}

        ultima = tentativas[0]
        dificuldade_atual = ultima.activity.difficulty

        # Dificuldade persistente: várias tentativas seguidas abaixo do
        # mínimo -> sinaliza o professor via um NOVO Diagnostic (reaproveita
        # a fila de aprovação que já existe, em vez de inventar um canal
        # novo) e NÃO mexe na dificuldade sozinho — nenhuma atividade nova
        # é gerada aqui de propósito.
        if (len(tentativas) >= PERSISTENT_FAILURE_THRESHOLD
                and all(t.score < SCORE_LOW for t in tentativas)):
            Diagnostic.objects.create(
                student=student, skill=skill, mastery_level=round(
                    sum(t.score for t in tentativas) / len(tentativas)),
                difficulty_level=dificuldade_atual,
                evidence=[f"{PERSISTENT_FAILURE_THRESHOLD} tentativas consecutivas com nota "
                          f"abaixo de {SCORE_LOW} em '{skill.name}' — dificuldade persistente, "
                          f"não ajustada automaticamente."],
                status=Diagnostic.Status.PENDING,
            )
            return {"action": "flagged_for_teacher", "skill": skill.name,
                    "reason": f"{PERSISTENT_FAILURE_THRESHOLD} tentativas seguidas abaixo de {SCORE_LOW}.",
                    "next_activity": None}

        if ultima.score >= SCORE_HIGH:
            decisao = {"action": "increase_difficulty", "skill": skill.name,
                       "from": dificuldade_atual,
                       "to": _proxima_dificuldade(dificuldade_atual, subir=True)}
        elif ultima.score >= SCORE_LOW:
            return {"action": "maintain", "skill": skill.name, "difficulty": dificuldade_atual,
                    "next_activity": None}
        else:
            decisao = {"action": "reduce_difficulty_temporarily", "skill": skill.name,
                       "from": dificuldade_atual,
                       "to": _proxima_dificuldade(dificuldade_atual, subir=False)}

        nova_atividade = self.generate_next_activity(ultima.activity, decisao)
        decisao["next_activity"] = nova_atividade
        return decisao

    def generate_next_activity(self, atividade_concluida: StudyActivity, decisao: dict):
        """Cria de fato a próxima StudyActivity no MESMO plano, no nível
        de dificuldade decidido — sem isso, a adaptação seria só um
        diagnóstico bonito que ninguém usa. 'maintain' e
        'flagged_for_teacher' nunca chegam aqui (ver apply_adaptation)."""
        tipo = TIPO_PROXIMA_ATIVIDADE_POR_ACAO.get(decisao["action"])
        if tipo is None:
            return None

        plano = atividade_concluida.study_plan
        skill = atividade_concluida.skill
        nova_dificuldade = decisao["to"]

        conteudo = build_activity_content(skill, tipo, nova_dificuldade, self.ai_provider)
        ultima_ordem = plano.activities.aggregate(m=Max("order"))["m"] or 0
        titulo = TITULO_PROXIMA_ATIVIDADE_POR_ACAO[decisao["action"]].format(skill=skill.name)

        return StudyActivity.objects.create(
            study_plan=plano, skill=skill, title=titulo, description=conteudo["description"],
            activity_type=tipo, difficulty=nova_dificuldade, estimated_minutes=15,
            instructions=conteudo["instructions"], expected_answer=conteudo["expected_answer"],
            explanation=conteudo["explanation"], order=ultima_ordem + 1,
        )
