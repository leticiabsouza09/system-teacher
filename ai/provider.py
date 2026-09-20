"""
Camada de abstração do provedor de IA.
----------------------------------------
Todo o resto do pacote `ai/` depende SOMENTE da interface `AIProvider`
definida aqui — nunca de um SDK de provedor específico diretamente. Isso é
o que permite trocar de modelo/provedor depois sem tocar na lógica de
diagnóstico, geração de atividades, etc.
"""
import json
from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Interface abstrata que qualquer provedor de IA precisa implementar."""

    @abstractmethod
    def generate_structured(self, system_prompt: str, user_prompt: str,
                             response_schema: dict) -> dict[str, Any]:
        """Envia um prompt e devolve JSON estruturado já validado contra
        `response_schema`. Implementações concretas tratam retries,
        parsing e erros do provedor específico aqui dentro — quem chama
        nunca vê exceção de SDK, só ValueError/TimeoutError genéricos."""
        raise NotImplementedError


def _extrair_json(texto: str) -> dict:
    """Providers de IA às vezes envolvem o JSON em ```json ... ``` mesmo
    quando instruídos a não fazer isso."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return json.loads(texto)


class AnthropicProvider(AIProvider):
    """Implementação concreta usando a API da Anthropic. Só é instanciada
    (ver ai/diagnostic.py) quando settings.ANTHROPIC_API_KEY está
    preenchida — o resto do sistema funciona sem ela (modo determinístico)."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate_structured(self, system_prompt: str, user_prompt: str,
                             response_schema: dict) -> dict:
        try:
            resposta = self._client.messages.create(
                model=self._model,
                max_tokens=1536,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:  # nunca deixa exceção de SDK vazar pra quem chama
            raise TimeoutError(f"Falha ao chamar o provedor de IA: {e}") from e

        texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text")
        try:
            return _extrair_json(texto)
        except (json.JSONDecodeError, IndexError) as e:
            raise ValueError(f"Provedor de IA não retornou JSON válido: {e}") from e


def get_default_provider() -> "AIProvider | None":
    """Fábrica: lê a configuração do Django e devolve o provider certo, ou
    None se nenhuma chave estiver configurada — quem chama SEMPRE precisa
    tratar o caso None (modo determinístico, sem enriquecimento de IA)."""
    from django.conf import settings

    if settings.AI_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
    return None
