"""
Serviço de Diagnóstico (Seção 5 do escopo).
-----------------------------------------------
`mastery_level`, `priority` e `evidence` são SEMPRE calculados em código, a
partir de AssessmentQuestion reais — nunca gerados por IA. Isso é o que
torna "a IA não deve inventar evidências" uma garantia estrutural, não só
uma instrução de prompt que ela poderia deixar de seguir (mesmo padrão já
usado no sistema de automação escolar para o filtro de segurança e o RAG
por banco de atividades).

A IA (via AIProvider, opcional) entra só como uma camada de ENRIQUECIMENTO
do texto de `recommended_action` — nunca dos números ou das evidências —
e sempre com fallback determinístico se não estiver configurada ou falhar.
"""
from dataclasses import dataclass, field

import logging

from django.conf import settings

from assessments.models import AssessmentQuestion
from learning.models import Diagnostic
from subjects.models import Skill
from users.models import User

from .provider import AIProvider

MINIMUM_QUESTIONS_FOR_DIAGNOSIS = 3
MASTERY_THRESHOLD_LOW = 40
MASTERY_THRESHOLD_MEDIUM = 70

RECOMMENDED_ACTION_BY_PRIORITY = {
    "high": "Revisar conceitos fundamentais antes de avançar para conteúdo novo.",
    "medium": "Reforçar com exercícios práticos direcionados a esta habilidade.",
    "low": "Avançar para aplicações mais complexas desta habilidade.",
}


def priority_for_mastery(mastery_level: int) -> str:
    """Extraída como função de módulo (não só método do serviço) porque
    ai/activity_generator.py (Etapa 7) precisa da MESMA classificação de
    prioridade para decidir a sequência de atividades — duplicar essa
    lógica em dois lugares seria o tipo de coisa que descasa silenciosamente
    quando um dos dois for ajustado no futuro."""
    if mastery_level < MASTERY_THRESHOLD_LOW:
        return "high"
    if mastery_level < MASTERY_THRESHOLD_MEDIUM:
        return "medium"
    return "low"


@dataclass
class SkillDiagnosisResult:
    skill: Skill
    status: str  # "ok" | "insufficient_evidence"
    mastery_level: int | None = None
    priority: str | None = None
    evidence: list[str] = field(default_factory=list)
    recommended_action: str | None = None
    missing_info: str | None = None

    def to_dict(self) -> dict:
        if self.status == "insufficient_evidence":
            return {"status": self.status, "skill": self.skill.name, "missing_info": self.missing_info}
        return {
            "status": self.status, "skill": self.skill.name, "mastery_level": self.mastery_level,
            "priority": self.priority, "evidence": self.evidence,
            "recommended_action": self.recommended_action,
        }


class DiagnosticService:
    def __init__(self, ai_provider: AIProvider | None = None):
        # None é um valor válido e esperado — significa "rodar sem
        # enriquecimento de IA", não um erro de configuração.
        self.ai_provider = ai_provider

    def _priority_for(self, mastery_level: int) -> str:
        return priority_for_mastery(mastery_level)

    def _build_recommended_action(self, skill: Skill, priority: str, evidence: list[str]) -> str:
        """Ação padrão vem de uma tabela curada (determinística — sempre
        funciona). Se um AIProvider foi passado, tentamos uma versão mais
        específica; qualquer falha (rede, parsing, timeout) cai de volta
        pra tabela curada em vez de propagar erro pro chamador."""
        acao_padrao = RECOMMENDED_ACTION_BY_PRIORITY[priority]
        if self.ai_provider is None:
            return acao_padrao

        try:
            resposta = self.ai_provider.generate_structured(
                system_prompt=(
                    "Você sugere UMA ação pedagógica curta (máximo 15 palavras) para "
                    "reforçar uma habilidade específica, baseada SOMENTE nas evidências "
                    "fornecidas. Nunca invente evidências novas. Responda apenas com "
                    'JSON: {"recommended_action": "..."}'
                ),
                user_prompt=(
                    f"Habilidade: {skill.name}\nPrioridade: {priority}\n"
                    f"Evidências: {'; '.join(evidence)}"
                ),
                response_schema={"recommended_action": str},
            )
            acao = resposta.get("recommended_action", "").strip()
            return acao if acao else acao_padrao
        except (TimeoutError, ValueError, KeyError) as e:
            logging.getLogger(__name__).warning("Enriquecimento de IA falhou, usando texto padrão: %s", e)
            return acao_padrao

    def diagnose_skill(self, student: User, skill: Skill) -> SkillDiagnosisResult:
        """Diagnostica UMA habilidade para UM aluno, a partir das questões
        de avaliação já respondidas e corrigidas (is_correct != None)."""
        questoes = AssessmentQuestion.objects.filter(
            assessment__student=student, skill=skill, is_correct__isnull=False)
        total = questoes.count()

        if total < MINIMUM_QUESTIONS_FOR_DIAGNOSIS:
            return SkillDiagnosisResult(
                skill=skill, status="insufficient_evidence",
                missing_info=(f"Apenas {total} questão(ões) corrigida(s) para esta habilidade — "
                               f"mínimo de {MINIMUM_QUESTIONS_FOR_DIAGNOSIS} necessário."),
            )

        acertos = questoes.filter(is_correct=True).count()
        erros = total - acertos
        mastery_level = round((acertos / total) * 100)
        priority = self._priority_for(mastery_level)

        evidence = [f"{erros} de {total} questões da habilidade '{skill.name}' respondidas incorretamente"]
        if erros > 0:
            avaliacoes_com_erro = list(
                questoes.filter(is_correct=False).values_list("assessment__title", flat=True).distinct())
            if avaliacoes_com_erro:
                evidence.append(f"Erros presentes em: {', '.join(avaliacoes_com_erro)}")

        recommended_action = self._build_recommended_action(skill, priority, evidence)

        return SkillDiagnosisResult(
            skill=skill, status="ok", mastery_level=mastery_level, priority=priority,
            evidence=evidence, recommended_action=recommended_action,
        )

    def diagnose_student(self, student: User, skills=None) -> dict:
        """Diagnostica todas as habilidades que o aluno já tem questão
        respondida (ou o subconjunto passado em `skills`). Formato de
        saída = exatamente o schema da Seção 5 do escopo."""
        if skills is None:
            skills = Skill.objects.filter(
                assessment_questions__assessment__student=student).distinct()

        resultados = [self.diagnose_skill(student, skill) for skill in skills]
        ok = [r for r in resultados if r.status == "ok"]
        insuficientes = [r for r in resultados if r.status == "insufficient_evidence"]

        if not ok and not insuficientes:
            return {"status": "insufficient_evidence",
                    "message": "Nenhuma habilidade com questões respondidas encontrada para este aluno."}

        return {"skills": [r.to_dict() for r in ok],
                "insufficient_evidence": [r.to_dict() for r in insuficientes]}

    def persist_diagnostics(self, student: User, skills=None) -> tuple[list[Diagnostic], list[dict]]:
        """Roda diagnose_student() e GRAVA um Diagnostic (status=PENDING —
        Seção 1, é sempre uma proposta) para cada habilidade com evidência
        suficiente. Retorna (diagnósticos criados, lista de habilidades
        com evidência insuficiente) — nunca esconde o caso insuficiente."""
        if skills is None:
            skills = list(Skill.objects.filter(
                assessment_questions__assessment__student=student).distinct())

        resultados = [self.diagnose_skill(student, skill) for skill in skills]

        criados = []
        for r in resultados:
            if r.status != "ok":
                continue
            diagnostico = Diagnostic.objects.create(
                student=student, skill=r.skill, mastery_level=r.mastery_level,
                difficulty_level=r.skill.difficulty_level, evidence=r.evidence,
                status=Diagnostic.Status.PENDING,
            )
            criados.append(diagnostico)

        insuficientes = [r.to_dict() for r in resultados if r.status == "insufficient_evidence"]
        return criados, insuficientes


def build_default_service() -> DiagnosticService:
    """Fábrica usada pela view — lê a config do Django uma vez só aqui,
    não espalhado pelo código."""
    from .provider import get_default_provider
    return DiagnosticService(ai_provider=get_default_provider())
