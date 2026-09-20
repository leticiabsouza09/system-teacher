"""
Configuração do projeto — lê tudo sensível do .env via django-environ.
Nunca coloque SECRET_KEY, credenciais de banco ou chaves de API direto
aqui: isso é exatamente o que a Seção 13 (Segurança e Privacidade) do
escopo proíbe.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
# Lê o .env na raiz do projeto (mesmo nível de manage.py), se existir.
# Em produção (Docker/CI), as variáveis já vêm do ambiente e este read()
# simplesmente não encontra o arquivo — sem erro.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceiros
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    # Apps do domínio
    "users",
    "authentication",
    "students",
    "teachers",
    "subjects",
    "assessments",
    "learning",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # precisa vir antes do CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Banco de dados: lê DATABASE_URL do .env (Postgres via Docker Compose).
# Fallback para SQLite se DATABASE_URL não estiver definida — permite
# rodar localmente sem Docker/Postgres para desenvolvimento rápido do MVP.
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Contexto brasileiro (o escopo é explícito sobre considerar a LGPD)
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # usado só em produção (collectstatic)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework ---------------------------------------------
# Autenticação por Token para a API (simples para o MVP) + Session para o
# navegador acessar a API autenticado pelo login normal do Django (útil
# para os dashboards server-rendered da Etapa 9). JWT (via
# djangorestframework-simplejwt) é uma evolução natural se o frontend virar
# uma SPA React separada — não é necessário para o MVP.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "PAGE_SIZE": 20,
    # Throttling — Seção 13 (proteção contra acesso indevido). Sem isso,
    # nada impede um script tentando milhares de senhas por segundo contra
    # /api/auth/login/. "anon" cobre qualquer request sem autenticação
    # ainda (exatamente o caso de login/registro).
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10/min",
    },
}

# CORS: desabilitado por padrão (Django Templates não precisa). Se o
# frontend virar uma SPA React em outra origem, defina CORS_ALLOWED_ORIGINS
# no .env — nunca deixe CORS_ALLOW_ALL_ORIGINS=True em produção.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# --- Camada de IA ---------------------------------------------------------
# Lido pela implementação concreta de AIProvider (ai/provider.py, Etapa 6)
# — nenhuma outra parte do código acessa a chave de API diretamente.
AI_PROVIDER = env("AI_PROVIDER", default="anthropic")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")

# --- Logging ---------------------------------------------------------------
# Sem dado pessoal de aluno em log (Seção 13): logamos IDs, nunca nome/email.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
