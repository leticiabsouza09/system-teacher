"""Serializadores do app `pedagogico` — versão integrada."""
from rest_framework import serializers

from classrooms.models import Classroom
from subjects.models import Subject
from users.models import User

from .models import LancamentoNota, ParecerPedagogico, RegistroFrequencia


class LancamentoNotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = LancamentoNota
        fields = ["id", "aluno", "disciplina", "bimestre", "nota", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class RegistroFrequenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroFrequencia
        fields = ["id", "aluno", "disciplina", "data", "bimestre", "presente"]


class ParecerPedagogicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParecerPedagogico
        fields = ["id", "aluno", "bimestre", "causa_raiz", "acao_recomendada",
                  "aprovado_pelo_professor", "created_at"]
        read_only_fields = ["created_at"]


class ChamadaEmLoteSerializer(serializers.Serializer):
    turma = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())
    disciplina = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    data = serializers.DateField()
    bimestre = serializers.IntegerField(min_value=1, max_value=4)
    ausentes = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class NotaGridItemSerializer(serializers.Serializer):
    aluno_id = serializers.IntegerField()
    disciplina_id = serializers.IntegerField()
    bimestre = serializers.IntegerField(min_value=1, max_value=4)
    nota = serializers.DecimalField(max_digits=3, decimal_places=1, min_value=0, max_value=10)


class GridNotasSerializer(serializers.Serializer):
    notas = NotaGridItemSerializer(many=True)


class PainelRiscoItemSerializer(serializers.Serializer):
    aluno_id = serializers.IntegerField()
    username = serializers.CharField()
    matricula = serializers.CharField(allow_null=True)
    alertas = serializers.CharField(allow_blank=True)
    nivel_risco = serializers.ChoiceField(choices=["alto", "medio", "baixo"])
