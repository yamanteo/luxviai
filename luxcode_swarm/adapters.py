from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schemas import ModelResult, ToolCall


class ToolCallNormalizer:
    @staticmethod
    def from_openai(item: Dict[str, Any]) -> ToolCall:
        function = item.get("function") or {}
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            arguments = json.loads(arguments or "{}")
        return ToolCall(
            id=str(item.get("id") or "tool-" + uuid.uuid4().hex[:12]),
            name=str(function.get("name") or item.get("name") or ""),
            arguments=dict(arguments),
        )

    @staticmethod
    def normalize_ollama(raw_output: str) -> List[ToolCall]:
        raw_output = str(raw_output or "").strip()
        if not raw_output:
            return []
        payload = json.loads(raw_output)
        items = payload if isinstance(payload, list) else [payload]
        calls = []
        for item in items:
            if "tool_calls" in item:
                calls.extend(ToolCallNormalizer.from_openai(call) for call in item["tool_calls"])
                continue
            name = item.get("tool") or item.get("name")
            args = item.get("arguments") or item.get("args") or {}
            if name:
                calls.append(ToolCall(id="tool-" + uuid.uuid4().hex[:12], name=str(name), arguments=dict(args)))
        return calls

    @staticmethod
    def normalize_gemini(function_call: Dict[str, Any]) -> ToolCall:
        return ToolCall(
            id="tool-" + uuid.uuid4().hex[:12],
            name=str(function_call.get("name") or ""),
            arguments=dict(function_call.get("args") or function_call.get("arguments") or {}),
        )

    @staticmethod
    def normalize_claude(tool_use: Dict[str, Any]) -> ToolCall:
        return ToolCall(
            id=str(tool_use.get("id") or "tool-" + uuid.uuid4().hex[:12]),
            name=str(tool_use.get("name") or ""),
            arguments=dict(tool_use.get("input") or tool_use.get("arguments") or {}),
        )


class BaseModelAdapter(ABC):
    model_name: str

    @abstractmethod
    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        raise NotImplementedError


class OllamaAdapter(BaseModelAdapter):
    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://127.0.0.1:11434", timeout: int = 60) -> None:
        self.model_name = "ollama"
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": (
                "You are a coding agent. If a tool is needed, return JSON "
                "{\"tool\":\"tool_name\",\"arguments\":{...}}. Otherwise return "
                "{\"content\":\"answer\"}. Available tools: "
                + json.dumps(tools, ensure_ascii=False)
                + "\nContext: "
                + json.dumps(context, ensure_ascii=False)
                + "\nUser: "
                + prompt
            ),
        }
        try:
            request = Request(self.base_url + "/api/generate", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            raw = str(data.get("response") or "")
            try:
                calls = ToolCallNormalizer.normalize_ollama(raw)
                content = "" if calls else str(json.loads(raw).get("content") or raw)
            except Exception:
                calls = []
                content = raw
            return ModelResult(ok=True, model=self.model_name, content=content, tool_calls=calls, usage_tokens=int(data.get("eval_count") or 0))
        except (OSError, URLError, HTTPError, json.JSONDecodeError) as exc:
            fallback = self._deterministic_local_plan(prompt)
            if fallback is not None:
                return fallback
            return ModelResult(ok=False, model=self.model_name, error=str(exc), finish_reason="error")

    def _deterministic_local_plan(self, prompt: str) -> ModelResult | None:
        lower = str(prompt or "").lower()
        if any(phrase in lower for phrase in ("list files", "list directory", "show files", "dosyalari listele", "dosya listele")):
            return ModelResult(
                ok=True,
                model=self.model_name,
                content="local fallback planned filesystem_list",
                tool_calls=[ToolCall(id="local-list-" + uuid.uuid4().hex[:8], name="filesystem_list", arguments={"dir": "."})],
                finish_reason="tool_calls",
            )
        read_match = re.search(r"(?:read|oku)\s+([A-Za-z0-9_.\\/-]+)", lower)
        if read_match:
            return ModelResult(
                ok=True,
                model=self.model_name,
                content="local fallback planned filesystem_read",
                tool_calls=[ToolCall(id="local-read-" + uuid.uuid4().hex[:8], name="filesystem_read", arguments={"path": read_match.group(1)})],
                finish_reason="tool_calls",
            )
        create_match = re.search(r"(?:create|touch|olustur)\s+([A-Za-z0-9_.\\/-]+)", lower)
        if create_match:
            target_path = create_match.group(1)
            content = self._compact_file_content(target_path, prompt)
            return ModelResult(
                ok=True,
                model=self.model_name,
                content="local fallback planned filesystem_write",
                tool_calls=[
                    ToolCall(
                        id="local-write-" + uuid.uuid4().hex[:8],
                        name="filesystem_write",
                        arguments={"path": target_path, "content": content},
                    )
                ],
                finish_reason="tool_calls",
            )
        return None

    def _compact_file_content(self, target_path: str, prompt: str) -> str:
        normalized = str(target_path or "").replace("\\", "/").lower()
        prompt_text = str(prompt or "")
        content_match = re.search(r"(?i)(?:with\s+content|icerik)\s+['\\\"](.*?)['\\\"]", prompt_text)
        if content_match:
            return content_match.group(1)
        if normalized.endswith("coder.html"):
            return (
                "<!doctype html><html lang=\"tr\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                "<title>LuxCode Coder</title>"
                "<link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css\">"
                "<style>body{max-width:1100px;margin:24px auto}#editor{height:62vh;border:1px solid #333}</style>"
                "</head><body><main><h1>LuxCode Coder</h1><p>Minimal editor shell.</p>"
                "<div id=\"editor\">// Start coding...</div><button id=\"save\">Save</button></main>"
                "<script src=\"https://cdn.jsdelivr.net/npm/monaco-editor@0.49.0/min/vs/loader.js\"></script>"
                "<script>require.config({paths:{vs:'https://cdn.jsdelivr.net/npm/monaco-editor@0.49.0/min/vs'}});"
                "require(['vs/editor/editor.main'],()=>{const e=monaco.editor.create(document.getElementById('editor'),"
                "{value:'// Start coding...\\n',language:'javascript',theme:'vs-dark',automaticLayout:true});"
                "document.getElementById('save').onclick=()=>console.log(e.getValue())});</script></body></html>\n"
            )
        return ""


class UnconfiguredAdapter(BaseModelAdapter):
    def __init__(self, model_name: str, env_hint: str) -> None:
        self.model_name = model_name
        self.env_hint = env_hint

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        return ModelResult(
            ok=False,
            model=self.model_name,
            error=f"adapter_not_configured:{self.env_hint}",
            finish_reason="configuration_required",
        )


def default_adapters() -> Dict[str, BaseModelAdapter]:
    return {
        "ollama": OllamaAdapter(),
        "gemini": UnconfiguredAdapter("gemini", "GEMINI_API_KEY"),
        "cloud_models": UnconfiguredAdapter("cloud_models", "CLOUD_MODEL_PROVIDER"),
        "deepseek": UnconfiguredAdapter("deepseek", "DEEPSEEK_API_KEY"),
        "whale": UnconfiguredAdapter("whale", "WHALE_API_KEY"),
        "codex": UnconfiguredAdapter("codex", "OPENAI_API_KEY"),
    }
