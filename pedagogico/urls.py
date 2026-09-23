from django.urls import path

from . import views

urlpatterns = [
    path("minhas-turmas/", views.MinhasTurmasView.as_view(), name="minhas-turmas"),
    path("frequencia/em-lote/", views.FrequenciaEmLoteView.as_view(), name="frequencia-em-lote"),
    path("notas/grid/", views.NotasGridView.as_view(), name="notas-grid"),
    path("painel-risco/", views.PainelRiscoView.as_view(), name="painel-risco"),
]
