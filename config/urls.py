"""
Roteamento raiz do projeto. Toda a API fica sob o prefixo /api/, cada app
mantendo suas próprias rotas em <app>/urls.py (incluídas aqui) — assim
nenhum app depende de saber o caminho completo de outro.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/", include("students.urls")),
    path("api/", include("subjects.urls")),
    path("api/", include("assessments.urls")),
    path("api/", include("learning.urls")),
    path("api/", include("dashboard.urls")),
]
