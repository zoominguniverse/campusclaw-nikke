from __future__ import annotations

import hashlib
import math
from typing import Protocol

import requests
from flask import current_app


class ProviderUnavailable(RuntimeError):
    pass


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]: ...


class ChatClient(Protocol):
    def answer(self, question: str, evidence: list[dict], history: list[dict]) -> str: ...


class DeterministicEmbeddingClient:
    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for character in text.casefold():
            bucket = int.from_bytes(hashlib.sha256(character.encode("utf-8")).digest()[:4], "big") % self.dimensions
            values[bucket] += 1.0
        magnitude = math.sqrt(sum(item * item for item in values)) or 1.0
        return [item / magnitude for item in values]


class OpenAICompatibleEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        config = current_app.config
        if not config["EMBEDDING_API_URL"] or not config["EMBEDDING_API_KEY"]:
            raise ProviderUnavailable("embedding provider configuration is unavailable")
        try:
            response = requests.post(
                f"{config['EMBEDDING_API_URL']}/embeddings",
                json={"model": config["EMBEDDING_MODEL"], "input": text},
                headers={"Authorization": f"Bearer {config['EMBEDDING_API_KEY']}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
        except (requests.RequestException, KeyError, IndexError, TypeError) as error:
            raise ProviderUnavailable("embedding provider is unavailable") from error


class DeterministicChatClient:
    def answer(self, question: str, evidence: list[dict], history: list[dict]) -> str:
        snippets = " ".join(item["chunk_text"].strip() for item in evidence[:2])
        return f"根据资料：{snippets} [1]"


class OpenAICompatibleChatClient:
    def answer(self, question: str, evidence: list[dict], history: list[dict]) -> str:
        config = current_app.config
        if not config["CHAT_API_URL"] or not config["CHAT_API_KEY"]:
            raise ProviderUnavailable("chat provider configuration is unavailable")
        context = "\n".join(f"[{index}] {item['material_title']} #{item['chunk_index']}: {item['chunk_text']}" for index, item in enumerate(evidence, 1))
        messages = [{"role": "system", "content": "Answer only from the supplied evidence and cite it with [n]."}]
        messages.extend(history)
        messages.append({"role": "user", "content": f"Evidence:\n{context}\n\nQuestion: {question}"})
        try:
            response = requests.post(
                f"{config['CHAT_API_URL']}/chat/completions",
                json={"model": config["CHAT_MODEL"], "messages": messages, "stream": False},
                headers={"Authorization": f"Bearer {config['CHAT_API_KEY']}"},
                timeout=20,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, TypeError) as error:
            raise ProviderUnavailable("chat provider is unavailable") from error


def embedding_client() -> EmbeddingClient:
    if current_app.config["EMBEDDING_PROVIDER"] == "deterministic":
        return DeterministicEmbeddingClient(current_app.config["EMBEDDING_DIMENSIONS"])
    if current_app.config["EMBEDDING_PROVIDER"] == "openai-compatible":
        return OpenAICompatibleEmbeddingClient()
    raise ProviderUnavailable("unsupported embedding provider")


def chat_client() -> ChatClient:
    if current_app.config["CHAT_PROVIDER"] == "deterministic":
        return DeterministicChatClient()
    if current_app.config["CHAT_PROVIDER"] == "openai-compatible":
        return OpenAICompatibleChatClient()
    raise ProviderUnavailable("unsupported chat provider")
