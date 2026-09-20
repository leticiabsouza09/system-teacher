# Testes de integração / ponta-a-ponta

Cada app Django tem seus próprios testes unitários em `<app>/tests.py`
(models, serializers, regras de negócio isoladas). Esta pasta é para
testes que cruzam mais de um app — ex.: o fluxo completo "aluno faz
avaliação → IA diagnostica → professor aprova → plano é gerado" (Seção 20
do prompt original) — que não pertence a nenhum app isoladamente.

Criados a partir da Etapa 10.
