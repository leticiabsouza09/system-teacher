"""
Análise de Anotações do Professor.
--------------------------------------
Sintetiza o histórico de `TeacherFeedback` que um professor escreveu sobre
um aluno e sugere próximos passos pedagógicos.

Princípio seguido (mesmo do resto do pacote `ai/`): a síntese NUNCA
inventa um fato que não esteja escrito nas anotações — o professor é a
única fonte de evidência aqui (diferente do diagnóstico, que usa dados
de questões). Por padrão, o resumo é 100% determinístico; a IA, quando
configurada, reformula esse texto de forma mais elaborada — um resumo
mais completo e cada sugestão com uma justificativa — mas tudo que ela
devolve passa por um filtro de segurança antes de chegar ao professor, e
a resposta sempre deixa explícito que é uma opinião, não uma decisão
automática: quem decide usar ou não é sempre o professor.
"""
import logging

from learning.models import TeacherFeedback
from subjects.models import Skill
from users.models import User

from .provider import AIProvider

MINIMUM_NOTES_FOR_ANALYSIS = 2
RATING_LOW = 2.5
RATING_HIGH = 4.0
MAX_SUGGESTED_ACTIONS = 4

DISCLAIMER = "Isto é uma sugestão gerada automaticamente — a decisão de usar ou não é sempre sua."

# Termos que nunca devem aparecer numa sugestão pedagógica gerada por IA —
# se aparecerem, descartamos a resposta da IA inteira e usamos o texto
# padrão. Escopo deliberadamente amplo: qualquer linguagem de diagnóstico
# clínico/psicológico está fora do papel desta ferramenta.
TERMOS_PROIBIDOS = [
    "tdah", "autis", "depress", "ansiedade", "transtorno", "bipolar",
    "medicaç", "medicad", "psiquiátr", "psicológic", "diagnóstico clínico",
    "distúrbio",
]


def _texto_e_seguro(texto: str) -> bool:
    texto_lower = texto.lower()
    return not any(termo in texto_lower for termo in TERMOS_PROIBIDOS)


ACOES_PADRAO_POR_FAIXA = {
    "baixa": [
        {"action": "Considere gerar um novo diagnóstico para reavaliar o desempenho recente.",
         "reason": "A nota média das últimas anotações está baixa, o que pode indicar uma "
                    "lacuna que vale confirmar com dados de avaliação, não só observação."},
        {"action": "Agende uma conversa individual com o aluno.",
         "reason": "Entender o contexto por trás das dificuldades relatadas ajuda a decidir "
                    "o próximo passo com mais segurança do que agir só pela nota."},
    ],
    "media": [
        {"action": "Continue acompanhando de perto o desempenho nas próximas atividades.",
         "reason": "As anotações não indicam nem melhora consistente nem piora — vale "
                    "observar mais um pouco antes de mudar o plano de estudo."},
    ],
    "alta": [
        {"action": "Considere aumentar o desafio no próximo plano de estudo.",
         "reason": "As observações recentes são consistentemente positivas, um sinal de que "
                    "o nível atual pode não estar mais desafiando o suficiente."},
    ],
}


class NotesAnalysisService:
    def __init__(self, ai_provider: AIProvider | None = None):
        self.ai_provider = ai_provider

    def _faixa(self, media: float) -> str:
        if media < RATING_LOW:
            return "baixa"
        if media < RATING_HIGH:
            return "media"
        return "alta"

    def _resumo_padrao(self, notas: list[TeacherFeedback], media: float, faixa: str) -> str:
        tendencia = {
            "baixa": "as observações recentes apontam dificuldade recorrente",
            "media": "as observações recentes são mistas, sem uma tendência clara",
            "alta": "as observações recentes são consistentemente positivas",
        }[faixa]
        return (
            f"{len(notas)} anotações registradas, nota média {media:.1f}/5 — {tendencia}. "
            f"Última observação: \"{notas[0].comment or '(sem comentário)'}\""
        )

    def _validar_acoes_ia(self, acoes_brutas) -> list[dict]:
        """Aceita só itens no formato esperado {action, reason} — qualquer
        item malformado (a IA errando o schema) é descartado silenciosamente
        em vez de quebrar a resposta inteira."""
        validas = []
        for item in acoes_brutas or []:
            if isinstance(item, dict) and item.get("action") and item.get("reason"):
                validas.append({"action": str(item["action"]), "reason": str(item["reason"])})
        return validas[:MAX_SUGGESTED_ACTIONS]

    def analyze(self, teacher: User, student: User, skill: "Skill | None" = None) -> dict:
        """Analisa as anotações que ESTE professor escreveu sobre ESTE
        aluno (nunca as de outro professor — cada professor só vê e
        sintetiza as próprias observações, mesmo isolamento já aplicado
        em TeacherFeedbackViewSet)."""
        qs = TeacherFeedback.objects.filter(teacher=teacher, student=student).order_by("-created_at")
        notas = list(qs)

        if len(notas) < MINIMUM_NOTES_FOR_ANALYSIS:
            return {
                "status": "insufficient_evidence",
                "message": (
                    f"Menos de {MINIMUM_NOTES_FOR_ANALYSIS} anotações registradas para "
                    "este aluno — escreva mais observações antes de pedir uma síntese."
                ),
            }

        media = sum(n.rating for n in notas) / len(notas)
        faixa = self._faixa(media)

        resultado = {
            "status": "ok",
            "notes_analyzed": len(notas),
            "average_rating": round(media, 1),
            "summary": self._resumo_padrao(notas, media, faixa),
            "suggested_actions": ACOES_PADRAO_POR_FAIXA[faixa],
            "source": "deterministic",
            "disclaimer": DISCLAIMER,
        }

        if self.ai_provider is None:
            return resultado

        try:
            resposta = self.ai_provider.generate_structured(
                system_prompt=(
                    "Você é um consultor pedagógico ajudando um professor a interpretar as "
                    "PRÓPRIAS anotações que ele escreveu sobre um aluno. Baseie-se SOMENTE no "
                    "texto fornecido — nunca invente comportamento, causa ou diagnóstico não "
                    "mencionados. Nunca use linguagem de diagnóstico clínico ou psicológico "
                    "(isso não é seu papel; se notar sinais preocupantes, sugira encaminhar "
                    "para quem é responsável por isso na escola, sem nomear uma condição). "
                    "Escreva um resumo de 3 a 5 frases conectando os padrões que você percebe "
                    "nas anotações — cite trechos das anotações quando ajudar. Depois, sugira "
                    f"de 2 a {MAX_SUGGESTED_ACTIONS} próximos passos pedagógicos concretos, "
                    "cada um com uma frase de justificativa baseada nas anotações. Deixe claro "
                    "que são sugestões — quem decide usar ou não é sempre o professor. Responda "
                    'apenas com JSON: {"summary": "...", "suggested_actions": '
                    '[{"action": "...", "reason": "..."}, ...]}'
                ),
                user_prompt="\n".join(
                    f"[{n.created_at.date()}] nota {n.rating}/5: {n.comment or '(sem comentário)'}"
                    for n in notas
                ),
                response_schema={"summary": str, "suggested_actions": list},
            )
            summary_ia = resposta.get("summary", "").strip()
            acoes_ia = self._validar_acoes_ia(resposta.get("suggested_actions"))

            texto_completo = summary_ia + " " + " ".join(f"{a['action']} {a['reason']}" for a in acoes_ia)
            if summary_ia and acoes_ia and _texto_e_seguro(texto_completo):
                resultado["summary"] = summary_ia
                resultado["suggested_actions"] = acoes_ia
                resultado["source"] = "ai"
            # Se a IA devolveu algo vazio, malformado, ou que tropeçou no
            # filtro de segurança, resultado já tem o texto determinístico
            # — nunca sobrescrevemos com nada arriscado ou incompleto.
        except (TimeoutError, ValueError, KeyError) as e:
            logging.getLogger(__name__).warning("Enriquecimento de IA falhou, usando texto padrão: %s", e)
            pass  # mantém o resultado determinístico

        return resultado


def build_default_service() -> NotesAnalysisService:
    from .provider import get_default_provider
    return NotesAnalysisService(ai_provider=get_default_provider())
