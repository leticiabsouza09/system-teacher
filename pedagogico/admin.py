from django.contrib import admin

from .models import LancamentoNota, ParecerPedagogico, RegistroFrequencia


@admin.register(LancamentoNota)
class LancamentoNotaAdmin(admin.ModelAdmin):
    list_display = ["aluno", "disciplina", "bimestre", "nota", "updated_at"]
    list_filter = ["disciplina", "bimestre"]


@admin.register(RegistroFrequencia)
class RegistroFrequenciaAdmin(admin.ModelAdmin):
    list_display = ["aluno", "disciplina", "data", "bimestre", "presente"]
    list_filter = ["disciplina", "bimestre", "presente"]


@admin.register(ParecerPedagogico)
class ParecerPedagogicoAdmin(admin.ModelAdmin):
    list_display = ["aluno", "bimestre", "aprovado_pelo_professor", "created_at"]
    list_filter = ["bimestre", "aprovado_pelo_professor"]
