"""
Módulo de Métricas do Sistema (Seção 15 do escopo).
-------------------------------------------------------
Princípio seguido em todo o projeto, aplicado aqui com mais força ainda:
NUNCA fabricar um número para uma métrica que os dados atuais não
sustentam. Cada métrica abaixo é OU calculada de verdade a partir dos
models existentes, OU explicitamente marcada como não implementável com o
schema atual — com o motivo, não um valor inventado.

Várias métricas da Seção 15 (retenção, transferência de conhecimento,
diferenças de desempenho entre grupos, tempo de revisão do professor,
"inconsistências") exigiriam um dado que o sistema não coleta hoje (ex.:
reavaliação após algumas semanas, distinção de aluno por turma/perfil
demográfico, cronômetro na tela do professor). Essas aparecem como
`None` com uma nota explicando o que falta — não como zero disfarçado.

Outras métricas usam um PROXY razoável na ausência do dado ideal — estão
marcadas com "proxy": True no resultado, para quem consumir a API saber
que não é a medição perfeita da definição original.
"""
from django.db.models import Avg, Count

from learning.models import ActivityAttempt, Diagnostic, ProgressRecord, StudentSkill, StudyPlan, TeacherFeedback

from .diagnostic import MASTERY_THRESHOLD_MEDIUM

# Mesma suposição documentada usada no sistema de automação escolar: tempo
# que um professor levaria pra montar isso na mão, só pra estimar "tempo
# economizado" — não é uma medição real, é uma premissa declarada.
TEMPO_MANUAL_ESTIMADO_MIN_POR_PLANO = 20


def _metrica(valor=None, proxy: bool = False, nao_implementado: str = None) -> dict:
    """Formato padrão de toda métrica: valor OU motivo de não estar
    implementada — nunca os dois, nunca nenhum dos dois (isso seria um 0
    silencioso)."""
    if nao_implementado is not None:
        return {"value": None, "proxy": False, "not_implemented": nao_implementado}
    return {"value": valor, "proxy": proxy, "not_implemented": None}


class ProgressAnalyzerService:
    """Calcula as métricas da Seção 15, agrupadas nas mesmas 5 categorias
    do escopo original (aprendizagem, qualidade da IA, engajamento,
    eficiência docente, segurança e equidade)."""

    # ------------------------------------------------------------------
    # A. Aprendizagem
    # ------------------------------------------------------------------

    def ganho_medio_aprendizagem(self) -> dict:
        ganhos = list(ProgressRecord.objects.values_list("mastery_after", "mastery_before"))
        if not ganhos:
            return _metrica(nao_implementado="Nenhum ProgressRecord registrado ainda.")
        media_real = sum(depois - antes for depois, antes in ganhos) / len(ganhos)
        return _metrica(round(media_real, 1))

    def percentual_objetivos_dominados(self) -> dict:
        total = StudentSkill.objects.count()
        if total == 0:
            return _metrica(nao_implementado="Nenhum StudentSkill registrado ainda.")
        dominados = StudentSkill.objects.filter(mastery_level__gte=MASTERY_THRESHOLD_MEDIUM).count()
        return _metrica(round(dominados / total, 3))

    def reducao_de_erros(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige comparar a taxa de erro do aluno em dois períodos (antes/depois de uma "
            "intervenção); o schema atual não marca qual AssessmentQuestion é 'antes' e qual "
            "é 'depois' de um plano de estudo específico."))

    def retencao(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige reavaliar a mesma habilidade algumas semanas depois do domínio inicial; "
            "não há um agendamento de reavaliação nem uma tag 'reteste' no schema atual."))

    def transferencia_de_conhecimento(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige distinguir 'questão praticada' de 'questão nova' para a mesma habilidade; "
            "AssessmentQuestion não marca se a questão já apareceu numa StudyActivity do aluno."))

    # ------------------------------------------------------------------
    # B. Qualidade da IA
    # ------------------------------------------------------------------

    def concordancia_docente(self) -> dict:
        """% de diagnósticos que o professor aprovou SEM alterar
        (APPROVED) entre todos os já avaliados (APPROVED+MODIFIED+REJECTED).
        MODIFIED e REJECTED contam como discordância parcial/total."""
        avaliados = Diagnostic.objects.filter(
            status__in=[Diagnostic.Status.APPROVED, Diagnostic.Status.MODIFIED,
                        Diagnostic.Status.REJECTED])
        total = avaliados.count()
        if total == 0:
            return _metrica(nao_implementado="Nenhum diagnóstico avaliado pelo professor ainda.")
        aprovados_sem_alteracao = avaliados.filter(status=Diagnostic.Status.APPROVED).count()
        return _metrica(round(aprovados_sem_alteracao / total, 3))

    def precisao_diagnostica(self) -> dict:
        """Proxy: nota média que os professores dão ao diagnóstico via
        TeacherFeedback, normalizada de 1-5 para 0-1. Não é a definição
        original (confirmação formal de acerto), mas é o dado mais
        próximo disponível sem um campo dedicado de 'diagnóstico correto?'."""
        media = TeacherFeedback.objects.filter(diagnostic__isnull=False).aggregate(m=Avg("rating"))["m"]
        if media is None:
            return _metrica(nao_implementado="Nenhum TeacherFeedback vinculado a diagnóstico ainda.")
        return _metrica(round((media - 1) / 4, 3), proxy=True)

    def adequacao_das_atividades(self) -> dict:
        """Proxy: % de ActivityAttempt com score >= 60 — atividade
        'adequada ao nível' tende a gerar desempenho razoável, não uma
        nota quase sempre 0 ou quase sempre 100."""
        total = ActivityAttempt.objects.count()
        if total == 0:
            return _metrica(nao_implementado="Nenhuma ActivityAttempt registrada ainda.")
        adequadas = ActivityAttempt.objects.filter(score__gte=60).count()
        return _metrica(round(adequadas / total, 3), proxy=True)

    def cobertura_das_lacunas(self) -> dict:
        """% de Diagnostic (lacunas identificadas) cuja habilidade
        recebeu pelo menos uma StudyActivity para aquele aluno — ou seja,
        a lacuna virou atividade de verdade, não só ficou no papel."""
        diagnosticos = Diagnostic.objects.select_related("student", "skill")
        total = diagnosticos.count()
        if total == 0:
            return _metrica(nao_implementado="Nenhum diagnóstico gerado ainda.")
        cobertos = sum(
            1 for d in diagnosticos
            if d.student.study_plans.filter(activities__skill=d.skill).exists()
        )
        return _metrica(round(cobertos / total, 3))

    def taxa_recomendacoes_inadequadas(self) -> dict:
        """Proxy: % de TeacherFeedback com rating <= 2 (numa escala 1-5) —
        não existe hoje um campo dedicado 'esta atividade/diagnóstico foi
        inadequado'."""
        total = TeacherFeedback.objects.count()
        if total == 0:
            return _metrica(nao_implementado="Nenhum TeacherFeedback registrado ainda.")
        inadequadas = TeacherFeedback.objects.filter(rating__lte=2).count()
        return _metrica(round(inadequadas / total, 3), proxy=True)

    # ------------------------------------------------------------------
    # C. Engajamento
    # ------------------------------------------------------------------

    def taxa_de_conclusao(self) -> dict:
        from learning.models import StudyActivity
        total = StudyActivity.objects.count()
        if total == 0:
            return _metrica(nao_implementado="Nenhuma StudyActivity gerada ainda.")
        concluidas = StudyActivity.objects.filter(status=StudyActivity.Status.COMPLETED).count()
        return _metrica(round(concluidas / total, 3))

    def tempo_de_estudo_total_minutos(self) -> dict:
        if not ActivityAttempt.objects.exists():
            return _metrica(nao_implementado="Nenhuma ActivityAttempt registrada ainda.")
        soma = sum(ActivityAttempt.objects.values_list("time_spent", flat=True))
        return _metrica(round(soma / 60, 1))

    def frequencia_de_estudos(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige agrupar tentativas por semana/aluno para uma média de dias ativos; o "
            "schema tem o timestamp (completed_at) mas essa agregação não foi implementada "
            "nesta versão — dá para adicionar sem mudar model."))

    def retorno_ao_sistema(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige registro de sessão/login por dia; o projeto usa Token auth sem log de "
            "acesso — não há como saber quando um aluno 'voltou' ao sistema."))

    # ------------------------------------------------------------------
    # D. Eficiência docente
    # ------------------------------------------------------------------

    def tempo_economizado_estimado_minutos(self) -> dict:
        """Suposição documentada (mesma lógica do sistema de automação
        escolar): cada StudyPlan gerado pela IA levaria
        TEMPO_MANUAL_ESTIMADO_MIN_POR_PLANO minutos pra um professor
        montar na mão. Isso NÃO é medido, é uma premissa — por isso
        sempre marcado como proxy."""
        planos_gerados_por_ia = StudyPlan.objects.filter(created_by_ai=True).count()
        if planos_gerados_por_ia == 0:
            return _metrica(nao_implementado="Nenhum StudyPlan gerado pela IA ainda.")
        return _metrica(planos_gerados_por_ia * TEMPO_MANUAL_ESTIMADO_MIN_POR_PLANO, proxy=True)

    def tempo_de_revisao_professor(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige cronometrar quanto tempo o professor leva entre abrir e aprovar um "
            "diagnóstico/plano; não há esse tipo de telemetria de UI implementada."))

    def quantidade_de_ajustes(self) -> dict:
        """Diagnósticos que o professor MODIFICOU (não só aprovou/rejeitou)
        antes de aceitar — é a medida mais direta de 'quanto a IA errou o
        suficiente para precisar de correção humana'."""
        total_avaliados = Diagnostic.objects.exclude(status=Diagnostic.Status.PENDING).count()
        if total_avaliados == 0:
            return _metrica(nao_implementado="Nenhum diagnóstico avaliado pelo professor ainda.")
        modificados = Diagnostic.objects.filter(status=Diagnostic.Status.MODIFIED).count()
        return _metrica(round(modificados / total_avaliados, 3))

    def percentual_planos_aprovados(self) -> dict:
        total = StudyPlan.objects.count()
        if total == 0:
            return _metrica(nao_implementado="Nenhum StudyPlan gerado ainda.")
        aprovados = StudyPlan.objects.filter(status=StudyPlan.Status.APPROVED).count()
        return _metrica(round(aprovados / total, 3))

    # ------------------------------------------------------------------
    # E. Segurança e equidade
    # ------------------------------------------------------------------

    def diagnosticos_incorretos(self) -> dict:
        """% de diagnósticos que o professor REJEITOU por completo —
        proxy direto e sem ambiguidade pra 'a IA errou o diagnóstico'."""
        total_avaliados = Diagnostic.objects.exclude(status=Diagnostic.Status.PENDING).count()
        if total_avaliados == 0:
            return _metrica(nao_implementado="Nenhum diagnóstico avaliado pelo professor ainda.")
        rejeitados = Diagnostic.objects.filter(status=Diagnostic.Status.REJECTED).count()
        return _metrica(round(rejeitados / total_avaliados, 3))

    def diferenca_desempenho_entre_grupos(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige um atributo de agrupamento (turma, perfil demográfico etc.) que o schema "
            "atual não modela — StudentProfile não tem 'turma' (ver TODO em "
            "core/permissions.py:IsTeacherOfStudent, mesma lacuna estrutural)."))

    def inconsistencias_entre_perfis_equivalentes(self) -> dict:
        return _metrica(nao_implementado=(
            "Exige uma definição operacional de 'perfis equivalentes' (mesma faixa de "
            "mastery_level, mesma disciplina) e comparar as recomendações entre eles — não "
            "implementado nesta versão."))

    def intervencoes_obrigatorias_do_professor(self) -> dict:
        """Diagnósticos gerados pelo AdaptationService por dificuldade
        persistente — mesma busca por texto na evidência usada no
        dashboard do professor (ver nota de limitação no README)."""
        total = Diagnostic.objects.filter(
            status=Diagnostic.Status.PENDING, evidence__icontains="dificuldade persistente"
        ).count()
        return _metrica(total)

    # ------------------------------------------------------------------

    def compute_all(self) -> dict:
        """Um único payload com as 5 categorias, pronto pra servir de
        resposta de API (ver dashboard/views.py:SystemMetricsView)."""
        return {
            "aprendizagem": {
                "ganho_medio_aprendizagem": self.ganho_medio_aprendizagem(),
                "percentual_objetivos_dominados": self.percentual_objetivos_dominados(),
                "reducao_de_erros": self.reducao_de_erros(),
                "retencao": self.retencao(),
                "transferencia_de_conhecimento": self.transferencia_de_conhecimento(),
            },
            "qualidade_da_ia": {
                "concordancia_docente": self.concordancia_docente(),
                "precisao_diagnostica": self.precisao_diagnostica(),
                "adequacao_das_atividades": self.adequacao_das_atividades(),
                "cobertura_das_lacunas": self.cobertura_das_lacunas(),
                "taxa_recomendacoes_inadequadas": self.taxa_recomendacoes_inadequadas(),
            },
            "engajamento": {
                "taxa_de_conclusao": self.taxa_de_conclusao(),
                "tempo_de_estudo_total_minutos": self.tempo_de_estudo_total_minutos(),
                "frequencia_de_estudos": self.frequencia_de_estudos(),
                "retorno_ao_sistema": self.retorno_ao_sistema(),
            },
            "eficiencia_docente": {
                "tempo_economizado_estimado_minutos": self.tempo_economizado_estimado_minutos(),
                "tempo_de_revisao_professor": self.tempo_de_revisao_professor(),
                "quantidade_de_ajustes": self.quantidade_de_ajustes(),
                "percentual_planos_aprovados": self.percentual_planos_aprovados(),
            },
            "seguranca_e_equidade": {
                "taxa_recomendacoes_inadequadas": self.taxa_recomendacoes_inadequadas(),
                "diagnosticos_incorretos": self.diagnosticos_incorretos(),
                "diferenca_desempenho_entre_grupos": self.diferenca_desempenho_entre_grupos(),
                "inconsistencias_entre_perfis_equivalentes": self.inconsistencias_entre_perfis_equivalentes(),
                "intervencoes_obrigatorias_do_professor": self.intervencoes_obrigatorias_do_professor(),
            },
        }
