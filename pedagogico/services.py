"""
Camada de serviços do app `pedagogico` — versão integrada ao System Teacher.

Mudança em relação à versão standalone: as funções que recebiam/devolviam
`matricula` agora usam o `id` do `User` (mesmo padrão do resto do System
Teacher — Diagnostic, TeacherFeedback etc. sempre identificam aluno pelo
id, nunca por um campo à parte). `matricula` continua existindo em
`StudentProfile`, mas como campo opcional pra quando um export precisar
de um identificador que não seja o username — não é mais a chave de
busca das APIs deste app.

Mesma limitação documentada da versão standalone: `analisar_causa_raiz`
funciona por Subject (disciplina), não por Skill/micro-habilidade BNCC —
juntar essa granularidade fina exigiria vincular LancamentoNota a Skill,
não só a Subject.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import Avg

from classrooms.models import Classroom
from subjects.models import Subject
from users.models import User

from .models import LancamentoNota, RegistroFrequencia

FREQUENCIA_MINIMA_LEGAL = Decimal("0.75")
MEDIA_MINIMA = Decimal("6.0")
QUEDA_RENDIMENTO_LIMITE = Decimal("0.20")

ACOES_RECOMENDADAS_POR_DISCIPLINA: dict[Optional[str], str] = {
    "Matemática": "Revisar operações e conceitos de base antes de avançar no conteúdo atual.",
    "Português": "Reforçar leitura e interpretação de texto com exercícios guiados.",
    None: "Agendar conversa individual para identificar a causa específica da queda.",
}


def _frequencia_percentual(aluno: User, bimestre: int) -> Optional[Decimal]:
    registros = RegistroFrequencia.objects.filter(aluno=aluno, bimestre=bimestre)
    total = registros.count()
    if total == 0:
        return None
    presentes = registros.filter(presente=True).count()
    return Decimal(presentes) / Decimal(total)


def _media_bimestre(aluno: User, bimestre: int, disciplina: Optional[Subject] = None) -> Optional[Decimal]:
    qs = LancamentoNota.objects.filter(aluno=aluno, bimestre=bimestre)
    if disciplina is not None:
        qs = qs.filter(disciplina=disciplina)
    resultado = qs.aggregate(media=Avg("nota"))["media"]
    return Decimal(str(resultado)) if resultado is not None else None


def calcular_alertas_aluno(aluno: User, bimestre: int) -> str:
    motivos: list[str] = []

    freq = _frequencia_percentual(aluno, bimestre)
    if freq is not None and freq < FREQUENCIA_MINIMA_LEGAL:
        motivos.append(f"Frequência crítica ({freq:.0%})")

    media_atual = _media_bimestre(aluno, bimestre)
    if media_atual is not None and media_atual < MEDIA_MINIMA:
        motivos.append(f"Média abaixo do mínimo ({media_atual:.1f})")

    if bimestre > 1:
        media_anterior = _media_bimestre(aluno, bimestre - 1)
        if media_anterior is not None and media_atual is not None and media_anterior > 0:
            queda = (media_anterior - media_atual) / media_anterior
            if queda >= QUEDA_RENDIMENTO_LIMITE:
                motivos.append(f"Queda de nota ({queda:.0%})")

    return " | ".join(motivos)


def analisar_causa_raiz(aluno: User, disciplina: Subject) -> dict:
    bimestres_com_nota = list(
        LancamentoNota.objects.filter(aluno=aluno, disciplina=disciplina)
        .order_by("bimestre").values_list("bimestre", "nota")
    )
    if len(bimestres_com_nota) < 2:
        return {
            "causa_raiz": "Dados insuficientes — menos de 2 bimestres lançados nesta disciplina.",
            "acao_recomendada": ACOES_RECOMENDADAS_POR_DISCIPLINA[None],
        }

    bimestre_anterior, nota_anterior = bimestres_com_nota[-2]
    bimestre_atual, nota_atual = bimestres_com_nota[-1]
    if nota_anterior == 0:
        return {
            "causa_raiz": "Dados insuficientes para calcular variação (nota anterior é zero).",
            "acao_recomendada": ACOES_RECOMENDADAS_POR_DISCIPLINA[None],
        }

    queda = (nota_anterior - nota_atual) / nota_anterior
    if queda < QUEDA_RENDIMENTO_LIMITE:
        return {
            "causa_raiz": "Sem queda relevante detectada nesta disciplina.",
            "acao_recomendada": ACOES_RECOMENDADAS_POR_DISCIPLINA[None],
        }

    return {
        "causa_raiz": (
            f"Queda de {queda:.0%} em {disciplina.name} "
            f"(bimestre {bimestre_anterior}: {nota_anterior} → bimestre {bimestre_atual}: {nota_atual})."
        ),
        "acao_recomendada": ACOES_RECOMENDADAS_POR_DISCIPLINA.get(
            disciplina.name, ACOES_RECOMENDADAS_POR_DISCIPLINA[None]),
    }


@transaction.atomic
def processar_chamada_em_lote(turma: Classroom, disciplina: Subject, data, bimestre: int,
                               lista_ausentes_ids: list[int]) -> dict:
    """`lista_ausentes_ids` são ids de User (não mais matrícula — ver
    docstring do módulo)."""
    ausentes = set(lista_ausentes_ids)
    presentes_count = 0
    ausentes_count = 0

    for aluno in turma.students.all():
        presente = aluno.id not in ausentes
        RegistroFrequencia.objects.update_or_create(
            aluno=aluno, disciplina=disciplina, data=data,
            defaults={"presente": presente, "bimestre": bimestre},
        )
        if presente:
            presentes_count += 1
        else:
            ausentes_count += 1

    return {"presentes": presentes_count, "ausentes": ausentes_count}


@transaction.atomic
def salvar_grid_notas_em_lote(dados_notas: list[dict]) -> list[LancamentoNota]:
    """Cada item: {"aluno_id": int, "disciplina_id": int, "bimestre": int,
    "nota": float|Decimal}. Validação roda ANTES de qualquer escrita —
    ver nota na versão standalone sobre por que full_clean() pós-escrita
    dava falso positivo de unicidade."""
    salvos = []
    for item in dados_notas:
        nota = Decimal(str(item["nota"]))
        bimestre = int(item["bimestre"])
        if not (Decimal("0") <= nota <= Decimal("10")):
            raise ValueError(f"Nota fora do intervalo 0–10: {nota} (aluno {item['aluno_id']}).")
        if not (1 <= bimestre <= 4):
            raise ValueError(f"Bimestre inválido: {bimestre} (aluno {item['aluno_id']}).")

        obj, _ = LancamentoNota.objects.update_or_create(
            aluno_id=item["aluno_id"],
            disciplina_id=item["disciplina_id"],
            bimestre=bimestre,
            defaults={"nota": nota},
        )
        salvos.append(obj)
    return salvos
