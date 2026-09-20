# Personalized Learning — Plataforma de Aprendizagem Personalizada com IA

MVP de uma plataforma que identifica lacunas de aprendizagem de um aluno,
gera um plano de estudo personalizado, adapta a dificuldade conforme o
desempenho, e mantém o professor como autoridade final em cada decisão
importante — a IA é apoio à decisão, nunca quem decide sozinha.

## Stack

- **Backend**: Django 5 + Django REST Framework, autenticação por Token.
- **Banco**: PostgreSQL via Docker Compose (SQLite como fallback automático
  para rodar local sem Docker — ver `.env.example`).
- **IA**: camada abstrata (`ai/provider.py`, interface `AIProvider`) com uma
  implementação concreta para a API da Anthropic. O núcleo de cada serviço
  de IA (`ai/diagnostic.py`, `ai/activity_generator.py`) funciona **sem**
  nenhuma chave configurada — a IA entra só como enriquecimento opcional de
  texto, nunca dos números/evidências.
- **Frontend**: nenhum ainda — o projeto é API-first (Django REST
  Framework); Django Templates ou uma SPA React consumiriam a mesma API
  sem mudança nenhuma no backend.

## Como rodar localmente

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # edite pelo menos o SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py test             # deve terminar em "OK"
python manage.py runserver
```

Sem `DATABASE_URL` definida no `.env`, o projeto cai automaticamente em
SQLite — não precisa de Postgres/Docker só para explorar o código.

### Com Docker

```bash
docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Arquitetura

```
config/          settings, urls raiz
users/           User customizado (role: student/teacher/admin)
authentication/  registro, login, /me/ (Token auth)
students/        StudentProfile + API de aluno (/students/, /skills/, /progress/)
teachers/        TeacherProfile
subjects/        Subject, Skill (grafo de pré-requisitos M2M)
assessments/     Assessment, AssessmentQuestion (dado item-a-item)
learning/        StudentSkill, Diagnostic, StudyPlan, StudyActivity,
                 ActivityAttempt, ProgressRecord, TeacherFeedback
dashboard/       agregados só-leitura (/dashboard/student/, /dashboard/teacher/)
core/            permissões DRF customizadas, reutilizadas por todos os apps
ai/              camada de serviço de IA — provider.py, diagnostic.py,
                 activity_generator.py, recommendation.py
```

`ai/` não é um Django app (não tem models/migrations) — é um pacote de
serviços puros, chamado pelas views de `learning/`.

## Fluxo completo (do jeito que foi testado de ponta a ponta)

```
Aluno responde avaliação (AssessmentQuestion, com is_correct)
        ↓
POST /api/diagnostics/generate/   → ai.diagnostic.DiagnosticService
        ↓  (mastery_level/evidence SEMPRE calculados em código, nunca pela IA)
Diagnostic criado com status=PENDING
        ↓
PATCH /api/diagnostics/{id}/approve/   → só professor (testado: aluno recebe 403)
        ↓
POST /api/study-plans/generate/   → ai.activity_generator.ActivityGeneratorService
        ↓  (sequência de atividades por prioridade: 6 tipos para "high", 3 para "low" —
        ↓   os 8 tipos de atividade da Seção 7 são todos usados, nenhum fica só no papel)
StudyPlan (status=DRAFT) com StudyActivity geradas
        ↓
PATCH /api/study-plans/{id}/approve/   → professor aprova
        ↓
POST /api/activities/{id}/attempt/   → ai.recommendation.AdaptationService
        ↓  (score >=85 sobe dificuldade | 60-84 mantém | <60 reduz;
        ↓   3 tentativas ruins seguidas → sinaliza professor via novo Diagnostic,
        ↓   nunca ajusta a dificuldade sozinho)
        ↓  subir/reduzir dificuldade JÁ CRIA a próxima StudyActivity no plano,
        ↓  no nível ajustado — não fica só como texto informativo na resposta
GET /api/dashboard/student/ · /api/dashboard/teacher/ · /api/dashboard/metrics/
```

## Segurança (Seção 13)

- Autenticação por Token; senha nunca aparece em nenhum serializer de
  leitura (`write_only`), validada com `django.contrib.auth.password_validation`.
- **Throttling** em `/api/auth/login/` e `/api/auth/register/`: 10
  tentativas/minuto por IP (`ScopedRateThrottle`, escopo `"auth"`) — testado
  na prática (10 tentativas = 400, a 11ª = 429).
- Toda `ViewSet` filtra o `queryset` por dono antes de qualquer permissão de
  objeto rodar — um aluno **não consegue listar** dados de outro aluno,
  não é só um 403 tardio.
- Campos sensíveis (`student` em `Assessment`, `status`/`validated_by` em
  `Diagnostic`) são `read_only` nos serializers principais e só mudam via
  actions dedicadas (`approve`) com sua própria permissão — testado que
  forjar o campo no corpo da requisição não funciona.
- Variáveis sensíveis só em `.env` (nunca no código); `.env` está no
  `.gitignore`.
- CORS fechado por padrão (`CORS_ALLOWED_ORIGINS=[]`) — só abre se
  explicitamente configurado.

## Métricas do Sistema (Seção 15)

`GET /api/dashboard/metrics/` (só professor/admin) — `ai/progress_analyzer.py`
calcula as métricas agrupadas nas 5 categorias do escopo (aprendizagem,
qualidade da IA, engajamento, eficiência docente, segurança e equidade).

Princípio seguido: **nunca fabricar um número que os dados não sustentam**.
Cada métrica retorna `{"value": ..., "proxy": bool, "not_implemented": str|null}`:

- `value` preenchido + `proxy: false` → cálculo direto e fiel à definição
  original (ex.: `ganho_medio_aprendizagem`, a partir de `ProgressRecord` real).
- `value` preenchido + `proxy: true` → aproximação razoável na ausência do
  dado ideal (ex.: `precisao_diagnostica` usa a nota do `TeacherFeedback`
  como substituto de uma confirmação formal de acerto que o schema não tem).
- `value: null` + `not_implemented` com o motivo → a métrica exigiria um
  dado que o sistema não coleta hoje (ex.: `retencao` precisaria de
  reavaliação agendada semanas depois; `retorno_ao_sistema` precisaria de
  log de sessão, que o Token auth não gera).

## Admin do Django

Todos os models têm `list_display`, `list_filter` e `search_fields`
configurados (não só `admin.site.register()` simples) — `Assessment` tem
suas `AssessmentQuestion` como inline, e `StudyPlan` suas `StudyActivity`.

## Limitações conhecidas (deliberadas, para manter o MVP enxuto)

- **Sem conceito de "turma"**: qualquer professor autenticado vê todos os
  alunos (`core/permissions.py:IsTeacherOfStudent` tem um `TODO` explícito
  sobre isso).
- **Correção automática de atividade** só funciona por comparação exata de
  string (`expected_answer`) — sem gabarito, a atividade fica sem nota até
  correção manual do professor (nunca inventa uma nota).
- **Alerta de dificuldade persistente** no dashboard do professor identifica
  o `Diagnostic` gerado pelo `AdaptationService` por um trecho de texto na
  evidência (`"dificuldade persistente"`) — funciona, mas um campo
  dedicado (`Diagnostic.source`) seria mais robusto numa próxima iteração.
- **Sem frontend renderizado** — só API. Templates Django ou uma SPA
  consumiriam os mesmos endpoints.
- **AnthropicProvider requer variável de ambiente exclusiva**: se
  `ANTHROPIC_API_KEY` estiver definida no SO (não só no `.env`), o sistema
  tenta usá-la — isso pode "vazar" de ferramentas que rodam com sua própria
  chave configurada no ambiente (ex.: um agente de codificação). Sem o
  pacote `anthropic` instalado, isso derruba a chamada; com o pacote
  instalado, uma chave de terceiro ativa faria o app tentar usá-la de
  verdade. Se isso for uma preocupação, rode os testes num ambiente sem
  essa variável no sistema, ou torne a leitura de `ANTHROPIC_API_KEY`
  explicitamente restrita ao arquivo `.env` (não ao ambiente do SO).

## Testes

84 testes automatizados (`python manage.py test`), cobrindo:

- Models: criação, relacionamentos (grafo M2M de pré-requisitos), validações
  (`unique_together`).
- Diagnóstico: evidência suficiente/insuficiente, múltiplas habilidades na
  mesma chamada, cálculo de `mastery_level`/`priority` a partir de dados
  reais, fallback de IA (sem provider / provider que falha / provider
  funcional).
- Geração de atividades: as 3 sequências por prioridade (agora cobrindo
  os 8 tipos de atividade da Seção 7, não só 5), tempo respeitando
  `study_time_available` do aluno.
- Adaptação: as 3 faixas de score + a regra de dificuldade persistente
  (3 tentativas seguidas, nunca 1 isolada) — e que `increase_difficulty`/
  `reduce_difficulty_temporarily` de fato criam a próxima `StudyActivity`
  no plano (não é só um valor informativo na resposta da API).
- Permissões: isolamento aluno↔aluno em 5 apps diferentes, aluno bloqueado
  de aprovar diagnóstico/plano, mass-assignment (aluno não força `student`
  no corpo da requisição).
- Segurança: throttling de login testado com 11 requisições reais.
- `TeacherFeedback`: criação exclusiva do professor, bloqueio de aluno,
  validação de rating (1-5) e de diagnóstico↔aluno cruzado.
- **Sincronização de `StudentSkill`/`ProgressRecord`** (achado em teste
  manual via Postman, não pelos testes automatizados — ver seção abaixo):
  aprovar diagnóstico ou corrigir atividade com gabarito real atualiza o
  domínio do aluno; atividade sem gabarito nunca zera o `mastery_level`
  real; `createsuperuser` agora define `role=ADMIN` corretamente.

## Bugs reais encontrados em teste manual (não pelos 76 testes automatizados)

Rodar o sistema de ponta a ponta via Postman (não só os testes unitários)
revelou 2 lacunas que a suíte automatizada não pegava, porque os testes
criavam `StudentSkill` manualmente no `setUp` — nunca exercitavam o
caminho real de escrita:

1. **`StudentSkill`/`ProgressRecord` nunca eram escritos em lugar nenhum
   do sistema.** Diagnóstico e plano eram gerados normalmente, mas o
   "domínio atual do aluno" (o que os dashboards e métricas leem) ficava
   sempre vazio. Corrigido: aprovar um diagnóstico agora sincroniza
   `StudentSkill` (fonte de verdade mais recente); corrigir uma atividade
   com gabarito real ajusta o `mastery_level` em ±5 e registra
   `ProgressRecord`. Atividade **sem** gabarito nunca toca em
   `StudentSkill` — evita que um "0 disfarçado" (não corrigido) zere o
   domínio real do aluno.
2. **`createsuperuser` criava o superusuário com `role=STUDENT`** (o
   default do campo, já que o comando não sabe nada sobre esse campo
   customizado). Um `admin` real aparecia como "aluno" nos dashboards.
   Corrigido com uma sobrescrita de `UserManager.create_superuser()`.

Isso é um lembrete útil pra qualquer projeto: testes automatizados que
criam estado manualmente no `setUp` podem mascarar exatamente os pontos
de integração que só o uso real do sistema revela.
- Métricas (`ProgressAnalyzerService`): valores calculados batendo com
  dados reais, e cada métrica genuinamente não-computável retornando
  `not_implemented` com o motivo, nunca um número inventado.

## Próximos passos sugeridos

- Model de `Turma`, vinculando professor↔aluno de verdade — destrava
  também `diferenca_desempenho_entre_grupos` nas métricas (Seção 15).
- Correção de atividades com IA (hoje é string exata ou manual).
- Campo dedicado para "tipo" de diagnóstico (persistente vs. inicial) em
  vez de buscar por texto na evidência (`icontains` em `Diagnostic.evidence`
  — usado tanto no dashboard do professor quanto em `intervencoes_
  obrigatorias_do_professor`).
- `frequencia_de_estudos` e `retencao` (Seção 15) exigem, respectivamente,
  agregação por semana (dá pra fazer sem mudar o schema) e um mecanismo de
  reavaliação agendada (esse sim exigiria model novo).
- Frontend (Django Templates para o MVP, ou React consumindo a API já
  pronta).
