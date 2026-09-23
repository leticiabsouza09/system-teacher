"""
Views do app `pedagogico` — versão integrada.

Diferença importante da versão standalone: lá, nenhuma view tinha
permission_classes — qualquer requisição autenticada (ou até anônima,
dependendo do DEFAULT_PERMISSION_CLASSES do projeto) conseguiria lançar
nota/frequência de qualquer turma. Aqui, cada view exige IsTeacher E
confere que o professor logado realmente leciona a turma pedida — mesmo
padrão de vínculo real (`Classroom`) usado no resto do System Teacher
(core.permissions.teacher_has_classroom_with).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from classrooms.models import Classroom
from core.permissions import IsTeacher
from users.models import User

from .models import LancamentoNota
from .serializers import (
    ChamadaEmLoteSerializer,
    GridNotasSerializer,
    NotaGridItemSerializer,
    PainelRiscoItemSerializer,
)
from .services import calcular_alertas_aluno, processar_chamada_em_lote, salvar_grid_notas_em_lote


def _professor_leciona_a_turma(user, turma: Classroom) -> bool:
    return turma.teachers.filter(pk=user.pk).exists()


class FrequenciaEmLoteView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        entrada = ChamadaEmLoteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        if not _professor_leciona_a_turma(request.user, dados["turma"]):
            return Response({"detail": "Você não leciona esta turma."}, status=status.HTTP_403_FORBIDDEN)

        resultado = processar_chamada_em_lote(
            turma=dados["turma"], disciplina=dados["disciplina"],
            data=dados["data"], bimestre=dados["bimestre"],
            lista_ausentes_ids=dados["ausentes"],
        )
        return Response(resultado, status=status.HTTP_200_OK)


class NotasGridView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        turma_id = request.query_params.get("turma")
        bimestre = request.query_params.get("bimestre")
        if not turma_id or not bimestre:
            return Response({"detail": "Parâmetros 'turma' e 'bimestre' são obrigatórios."},
                             status=status.HTTP_400_BAD_REQUEST)

        try:
            turma = Classroom.objects.get(pk=turma_id)
        except Classroom.DoesNotExist:
            return Response({"detail": "Turma não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if not _professor_leciona_a_turma(request.user, turma):
            return Response({"detail": "Você não leciona esta turma."}, status=status.HTTP_403_FORBIDDEN)

        notas = (LancamentoNota.objects
                 .filter(aluno__classrooms_enrolled=turma, bimestre=bimestre)
                 .select_related("aluno", "disciplina"))
        linhas = [
            {
                "aluno_id": n.aluno_id,
                "username": n.aluno.username,
                "disciplina_id": n.disciplina_id,
                "disciplina_nome": n.disciplina.name,
                "bimestre": n.bimestre,
                "nota": str(n.nota),
            }
            for n in notas
        ]
        return Response({"celulas": linhas})

    def post(self, request):
        entrada = GridNotasSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        # Confere vínculo de turma pra CADA aluno citado — um professor não
        # pode aproveitar este endpoint pra lançar nota de aluno de outra
        # turma, mesmo sabendo o id de disciplina certo.
        alunos_ids = {item["aluno_id"] for item in entrada.validated_data["notas"]}
        turmas_do_professor = Classroom.objects.filter(teachers=request.user)
        alunos_vinculados = set(
            User.objects.filter(id__in=alunos_ids, classrooms_enrolled__in=turmas_do_professor)
            .values_list("id", flat=True)
        )
        if alunos_ids - alunos_vinculados:
            return Response({"detail": "Um ou mais alunos não pertencem às suas turmas."},
                             status=status.HTTP_403_FORBIDDEN)

        try:
            salvos = salvar_grid_notas_em_lote(entrada.validated_data["notas"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        resultado = NotaGridItemSerializer(
            [{"aluno_id": n.aluno_id, "disciplina_id": n.disciplina_id,
              "bimestre": n.bimestre, "nota": n.nota} for n in salvos],
            many=True,
        )
        return Response({"salvos": resultado.data}, status=status.HTTP_200_OK)


class PainelRiscoView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        turma_id = request.query_params.get("turma")
        bimestre = request.query_params.get("bimestre")
        if not turma_id or not bimestre:
            return Response({"detail": "Parâmetros 'turma' e 'bimestre' são obrigatórios."},
                             status=status.HTTP_400_BAD_REQUEST)
        bimestre = int(bimestre)

        try:
            turma = Classroom.objects.get(pk=turma_id)
        except Classroom.DoesNotExist:
            return Response({"detail": "Turma não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if not _professor_leciona_a_turma(request.user, turma):
            return Response({"detail": "Você não leciona esta turma."}, status=status.HTTP_403_FORBIDDEN)

        linhas = []
        for aluno in turma.students.all():
            alertas = calcular_alertas_aluno(aluno, bimestre)
            if not alertas:
                continue
            motivos = alertas.split(" | ")
            nivel = "alto" if len(motivos) >= 2 or "Frequência crítica" in alertas else "medio"
            matricula = getattr(getattr(aluno, "student_profile", None), "matricula", None)
            linhas.append({
                "aluno_id": aluno.id,
                "username": aluno.username,
                "matricula": matricula,
                "alertas": alertas,
                "nivel_risco": nivel,
            })

        resultado = PainelRiscoItemSerializer(linhas, many=True)
        return Response(resultado.data)
