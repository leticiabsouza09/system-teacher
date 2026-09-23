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
- **Frontend**: landing page + dashboards funcionais, servidos como Django
  Templates em `templates/`. O HTML não recebe dado renderizado pelo
  servidor — cada página chama a própria API REST via `fetch()`
  (`static/js/auth.js`), exatamente os mesmos endpoints testados no
  Postman. Login/cadastro são modais na landing page; token fica em
  `localStorage`. O painel do aluno tem botões que disparam a IA de
  verdade (**Analisar meu desempenho** → `/api/diagnostics/generate/`,
  **Gerar meu plano** → `/api/study-plans/generate/`), mostrando o estado
  de "processando" enquanto a chamada roda. O painel do professor lista
  diagnósticos pendentes e planos aguardando aprovação com ações reais
  (**Aprovar** / editar o `mastery_level` antes de aprovar / **Rejeitar**),
  e uma seção de **anotações sobre alunos** (`TeacherFeedback`) — o
  professor escreve uma observação, escolhe uma nota de 1 a 5, e vê o
  histórico do que já escreveu. Um botão **"Analisar anotações com IA"**
  sintetiza o histórico e sugere próximos passos — sempre com um filtro
  de segurança que descarta qualquer linguagem de diagnóstico clínico/
  psicológico (fora do papel desta ferramenta) e cai de volta pra um
  resumo determinístico se a IA tropeçar nisso ou falhar.

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

## Deploy (Render)

O projeto tem um `render.yaml` (Blueprint) que provisiona o serviço web +
um banco PostgreSQL gratuito num clique só — sem precisar configurar nada
manualmente no painel do Render.

1. Faça um fork ou garanta que o repositório está no seu GitHub.
2. Em [dashboard.render.com/blueprints](https://dashboard.render.com/blueprints),
   clique em **New Blueprint Instance** e conecte o repositório.
3. O Render lê o `render.yaml`, cria o banco e o serviço web automaticamente
   (gera uma `SECRET_KEY` segura sozinho — você não precisa colar nada).
4. Espere o build (`build.sh`: instala dependências, `collectstatic`,
   `migrate`, e `seed_demo_data` — o banco já sobe com os dados de
   demonstração, prontos pra qualquer visitante testar).
5. Pronto — acesse a URL que o Render gerou (algo como
   `https://system-teacher-xxxx.onrender.com`).

**Sem custo, sem cartão de crédito.** Duas limitações do tier gratuito
vale saber: o serviço "dorme" depois de 15 min sem acesso (a próxima
visita demora uns 30-60s pra acordar — normal, não é bug), e o banco
Postgres gratuito expira 30 dias após criado (dá pra recriar de graça de
novo, só não é permanente).

Se quiser ativar a IA de verdade em produção, edite a variável de
ambiente `ANTHROPIC_API_KEY` direto no painel do Render (Settings →
Environment) — sem isso, o sistema continua funcionando normalmente com
o fallback determinístico, como já validamos localmente.

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

- **Turma sem interface própria**: o model `Classroom` existe e já é
  aplicado de verdade em todos os pontos de acesso (ver seção acima), mas
  só é editável pelo Django Admin ou pelo `seed_demo_data` — ainda não
  existe uma tela para o professor (ou admin) criar/gerenciar turmas.
- **Correção automática de atividade** só funciona por comparação exata de
  string (`expected_answer`) — sem gabarito, a atividade fica sem nota até
  correção manual do professor (nunca inventa uma nota).
- **Alerta de dificuldade persistente** no dashboard do professor identifica
  o `Diagnostic` gerado pelo `AdaptationService` por um trecho de texto na
  evidência (`"dificuldade persistente"`) — funciona, mas um campo
  dedicado (`Diagnostic.source`) seria mais robusto numa próxima iteração.
- **AnthropicProvider requer variável de ambiente exclusiva**: se
  `ANTHROPIC_API_KEY` estiver definida no SO (não só no `.env`), o sistema
  tenta usá-la — isso pode "vazar" de ferramentas que rodam com sua própria
  chave configurada no ambiente (ex.: um agente de codificação). Sem o
  pacote `anthropic` instalado, isso derruba a chamada; com o pacote
  instalado, uma chave de terceiro ativa faria o app tentar usá-la de
  verdade. `manage.py test` já se protege disso sozinho (força a chave
  vazia durante os testes, veja `config/settings.py`); rodar o servidor
  normal continua exposto a esse risco.

## Turma (`classrooms`)

Vínculo real entre professor e aluno — sem isso, "professor só vê os
próprios alunos" (Seção 16) era impossível de impor de verdade. Um
professor só acessa/aprova/anota dados de um aluno que está numa
`Classroom` que ele leciona; fora disso, o aluno nem aparece nas listagens
(querysets já filtram antes de qualquer permissão de objeto rodar — em
geral resulta em 404, não 403, o mesmo padrão já usado no isolamento
aluno↔aluno). Administrador continua sem essa restrição.

Afeta: `StudentViewSet`, `AssessmentViewSet`/`AssessmentQuestionViewSet`,
`DiagnosticViewSet`/`StudyPlanViewSet`/`StudyActivityViewSet` (via
`_filtrar_por_dono_ou_professor`), as actions `generate` de diagnóstico/
plano (um professor não gera nada para aluno sem vínculo), o
`TeacherDashboardView`, e `TeacherFeedbackSerializer` (só registra
anotação sobre aluno da própria turma).

## Boletim do dia a dia (`pedagogico`)

Módulo de produtividade diária do professor — lançamento de frequência
por exceção, grid de notas, e painel de risco (frequência <75%, média
<6.0, queda de rendimento ≥20%). Nasceu como um projeto separado
(script/SaaS de automação de boletim), depois integrado aqui.

**Não tem model próprio de aluno/turma/disciplina** — usa `users.User`
(role=student), `classrooms.Classroom` e `subjects.Subject` que já
existem, evitando duas identidades paralelas pro mesmo aluno. O único
campo novo é `StudentProfile.matricula` (opcional, único) — pensado pra
quando um export precisar de um identificador que não seja o username
(LGPD), sem afetar login/permissão em nada.

Endpoints (`/api/pedagogico/`), todos exigindo professor **com vínculo de
Classroom com a turma pedida** (403 se não tiver — testado explicitamente,
inclusive o caso de um professor tentar lançar nota de aluno que não é
seu passando o id certo de outra turma):
- `GET minhas-turmas/` — turmas do professor logado, com a lista de alunos
- `POST frequencia/em-lote/` — lançamento por exceção (todos presentes,
  só quem está em `ausentes` vira falta)
- `GET/POST notas/grid/` — matriz aluno×disciplina×nota; POST faz upsert
  em lote, tudo dentro de uma transação atômica (se uma linha for
  inválida, nada é salvo, nem as linhas válidas)
- `GET painel-risco/` — só lista quem tem alerta ativo

**Limitação conhecida**: `analisar_causa_raiz` funciona por `Subject`
(disciplina), não por micro-habilidade BNCC como o `GRAFO_CONHECIMENTO`
dos scripts de automação anteriores — vincular `LancamentoNota` a `Skill`
seria o próximo passo pra ter a granularidade fina de novo.

### Frontend do grid (`frontend-grid/`, React + Vite)

Tela real do professor pra frequência/notas/painel de risco — três abas,
consumindo os endpoints acima. Fica em `/professor/grid/`.

```bash
cd frontend-grid
npm install
npm run dev       # localhost:5173, com proxy pra localhost:8000 (Django)
npm run build     # gera static/grid/ — é o que o Django serve em produção
```

**O build (`static/grid/`) é versionado no git**, ao contrário do resto de
`staticfiles/`. Isso é deliberado: o ambiente Python nativo do Render (ver
seção de Deploy) não tem Node.js, então gerar o build ali quebraria o
`build.sh`. Rodar `npm run build` de novo e commitar o resultado sempre
que mexer em `frontend-grid/src/` é manual, mas evita configurar Node no
provedor só pra isso.
## Testes

94 testes automatizados (`python manage.py test`), cobrindo:

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
- `NotesAnalysisService`: evidência insuficiente com menos de 2 anotações,
  isolamento entre professores (um professor nunca vê a análise baseada
  em anotações de outro), e o filtro de segurança descartando qualquer
  sugestão de IA com linguagem clínica/psicológica.
- Turma (`classrooms`): isolamento real ponta a ponta — professor sem
  vínculo não vê o aluno em nenhuma listagem, não aprova diagnóstico
  (404), não gera diagnóstico/plano para ele (403), não vê no dashboard,
  e não registra anotação sobre ele (400).

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
