"""
Roteamento raiz do projeto. Toda a API fica sob o prefixo /api/, cada app
mantendo suas próprias rotas em <app>/urls.py (incluídas aqui) — assim
nenhum app depende de saber o caminho completo de outro.

As páginas web (landing page, dashboards) são views simples que só
servem o template — todo o dado vem do navegador chamando a própria API
via JavaScript (fetch), não de contexto renderizado no servidor. Ou seja,
a página web é só mais um CLIENTE da mesma API que testamos no Postman.
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/", include("students.urls")),
    path("api/", include("subjects.urls")),
    path("api/", include("assessments.urls")),
    path("api/", include("learning.urls")),
    path("api/", include("dashboard.urls")),
    path("api/pedagogico/", include("pedagogico.urls")),

    # Páginas web
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("dashboard/aluno/", TemplateView.as_view(template_name="dashboard_aluno.html"),
         name="dashboard-aluno"),
    path("dashboard/professor/", TemplateView.as_view(template_name="dashboard_professor.html"),
         name="dashboard-professor"),
]
