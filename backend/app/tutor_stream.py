"""Streaming text protocol, independent of the grounded single-answer protocol."""
import json
import threading
from urllib.parse import urlsplit

import requests
from flask import current_app
from sqlalchemy import text

from .extensions import db
from .providers import ProviderUnavailable


class CitationFilter:
    def __init__(self, count):
        self.count, self.pending, self.discard = count, "", False

    def feed(self, value):
        output = []
        for character in value:
            if self.discard:
                if character == "]":
                    self.discard = False
                elif not character.isascii() or not character.isdigit():
                    self.discard = False
                    if character == "[":
                        self.pending = "["
                    else:
                        output.append(character)
                continue
            if not self.pending:
                if character == "[":
                    self.pending = "["
                else:
                    output.append(character)
            elif character.isascii() and character.isdigit():
                self.pending += character
                if len(self.pending) > 11:
                    self.pending, self.discard = "", True
            elif character == "]" and len(self.pending) > 1:
                number = int(self.pending[1:])
                if 1 <= number <= self.count:
                    output.append(f"[{number}]")
                self.pending = ""
            else:
                output.append(self.pending)
                self.pending = "[" if character == "[" else ""
                if character != "[":
                    output.append(character)
        return "".join(output)

    def finish(self):
        remainder = self.pending if self.pending == "[" else ""
        self.pending, self.discard = "", False
        return remainder


class DemoTutorStream:
    demo_mode = True

    def __init__(self, messages):
        guide = "解题引导" in messages[0]["content"]
        answer = "演示模式：请先说明题目的条件和你已经尝试的方法。接下来我们逐步检查思路。" if guide else "演示模式：我已收到你的问题。请补充你的思路，我们可以逐步讨论。"
        self.parts = iter(answer[i:i + 5] for i in range(0, len(answer), 5))

    def __iter__(self):
        return self.parts

    def close(self):
        pass


class ProviderTutorStream:
    demo_mode = False

    def __init__(self, messages):
        config = current_app.config
        payload = {"model": config["CHAT_MODEL"], "messages": messages, "stream": True, "max_tokens": 2048}
        if urlsplit(config["CHAT_API_URL"]).hostname == "api.deepseek.com":
            payload["reasoning_effort"] = "none"
        try:
            self.response = requests.post(f"{config['CHAT_API_URL']}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {config['CHAT_API_KEY']}"}, stream=True,
                timeout=(min(10, config["CHAT_TIMEOUT_SECONDS"]), config["CHAT_TIMEOUT_SECONDS"]))
            self.response.raise_for_status()
        except requests.RequestException as error:
            if hasattr(self, "response"):
                self.response.close()
            raise ProviderUnavailable("chat provider is unavailable") from error

    def __iter__(self):
        finished = False
        total = 0
        data = []
        size = 0
        try:
            # A small read size ensures the first token is not buffered until EOF.
            for line in self.response.iter_lines(chunk_size=1):
                size += len(line)
                if size > 65536:
                    raise ProviderUnavailable("provider frame exceeds budget")
                if line.startswith(b"data:"):
                    data.append(line[5:].lstrip())
                elif not line:
                    if not data:
                        size = 0
                        continue
                    raw, data, size = b"\n".join(data), [], 0
                    if raw == b"[DONE]":
                        if not finished:
                            raise ProviderUnavailable("provider did not finish normally")
                        return
                    item = json.loads(raw.decode("utf-8"))
                    if item.get("error"):
                        raise ProviderUnavailable("provider stream failed")
                    for choice in item.get("choices", []):
                        if choice.get("index", 0) != 0:
                            continue
                        reason = choice.get("finish_reason")
                        if reason is not None:
                            if reason != "stop":
                                raise ProviderUnavailable("provider output was interrupted")
                            finished = True
                        content = choice.get("delta", {}).get("content")
                        if content is not None:
                            if not isinstance(content, str):
                                raise ProviderUnavailable("invalid provider text")
                            if content:
                                total += len(content)
                                if total > 16000:
                                    raise ProviderUnavailable("provider text exceeds budget")
                                yield content
            raise ProviderUnavailable("provider stream ended without DONE")
        except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
            raise ProviderUnavailable("chat provider stream is unavailable") from error
        finally:
            self.close()

    def close(self):
        self.response.close()


def stream_tutor(messages):
    if current_app.config["CHAT_PROVIDER"] == "deterministic":
        return DemoTutorStream(messages)
    return ProviderTutorStream(messages)


_guard = threading.Lock()
_locks = {}


class GenerationLock:
    """Session advisory locks survive short commits, never a stream-long transaction."""
    def __init__(self, conversation_id):
        self.ident, self.connection, self.acquired = conversation_id, None, False
        self.local = None

    def acquire(self):
        if db.engine.dialect.name == "postgresql":
            self.connection = db.engine.connect().execution_options(isolation_level="AUTOCOMMIT")
            try:
                self.acquired = self.connection.execute(text("SELECT pg_try_advisory_lock(1128485937, :id)"), {"id": self.ident}).scalar()
            except Exception:
                self.connection.close()
                self.connection = None
                raise
            if not self.acquired:
                self.connection.close()
                self.connection = None
        else:
            with _guard:
                key = (id(db.engine), self.ident)
                entry = _locks.setdefault(key, [threading.Lock(), 0])
                entry[1] += 1
                self.local = (key, entry)
            self.acquired = entry[0].acquire(blocking=False)
            if not self.acquired:
                self.close()
        return self.acquired

    def close(self):
        if self.connection is not None:
            try:
                self.connection.execute(text("SELECT pg_advisory_unlock(1128485937, :id)"), {"id": self.ident})
            except Exception:
                # A broken connection must never return a session lock to the pool.
                self.connection.invalidate()
            finally:
                self.connection.close()
                self.connection = None
        if self.local:
            key, entry = self.local
            with _guard:
                if self.acquired:
                    entry[0].release()
                entry[1] -= 1
                if not entry[1]:
                    _locks.pop(key, None)
                self.local = None
        self.acquired = False
