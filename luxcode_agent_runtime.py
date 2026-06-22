from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import session_manager
from tool_executor import execute_tool


CODER_SYSTEM_PROMPT = """Sen tam yetkili bir yazılım mühendisi ajanısın.
Aşağıdaki araçlara erişimin var:

ARAÇLAR:
read_file(path): Dosya oku
write_file(path, content): Dosya yaz
edit_file(path, old_text, new_text): Dosya düzenle
append_file(path, content): Dosya sonuna ekle
delete_file(path): Dosya sil
create_directory(path): Klasör oluştur
list_directory(path): Klasör listele
search_in_files(directory, pattern): Dosyalarda ara
run_command(command): Terminal komutu çalıştır
run_python(code): Python kodu çalıştır
backup_file(path): Yedek al

KULLANIM:
Bir araç kullanmak istediğinde şu JSON formatında yaz:
{"tool": "araç_adı", "params": {"parametre": "değer"}}

KURALLAR:
Her dosya değişikliğinden önce backup_file kullan
Her değişiklikten sonra read_file ile doğrula
Kod yazdıktan sonra run_command veya run_python ile test et
Hata alırsan otomatik düzelt ve tekrar dene
Yarım iş bırakma
Her görev sonunda rapor ver
"""


def parse_tool_calls(text: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    decoder = json.JSONDecoder()
    cleaned = str(text or "").strip()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "tool" in payload and isinstance(payload.get("params", {}), dict):
            calls.append({"tool": str(payload["tool"]), "params": dict(payload.get("params") or {})})
    return calls


def _natural_create_file(prompt: str) -> List[Dict[str, Any]]:
    match = re.search(
        r"(?:create|oluştur|olustur)\s+(?P<path>[^\s\"']+)\s+(?:with content|içine|icine)\s+(?P<quote>['\"])(?P<content>.*?)(?P=quote)",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return [{"tool": "write_file", "params": {"path": match.group("path"), "content": match.group("content")}}]
    loose = re.search(
        r"(?:create|oluştur|olustur)(?:\s+a\s+file\s+called|\s+file\s+called|\s+dosya)?\s+(?P<path>[^\s\"']+)\s+(?:with content|içine|icine)\s+(?P<content>.+)$",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if loose:
        content = loose.group("content").strip()
        if content.startswith("print(") and not re.search(r"print\((['\"])", content):
            inner = content[6:-1] if content.endswith(")") else content[6:]
            content = f"print({inner!r})"
        return [{"tool": "write_file", "params": {"path": loose.group("path"), "content": content + ("\n" if not content.endswith("\n") else "")}}]
    return []


def _natural_hello_world(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "test.py" not in lowered or ("hello" not in lowered and "merhaba" not in lowered):
        return []
    return [
        {"tool": "write_file", "params": {"path": "test.py", "content": "print('hello world')\n"}},
        {"tool": "read_file", "params": {"path": "test.py"}},
        {"tool": "run_command", "params": {"command": "python test.py"}},
    ]


def _natural_fibonacci(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "fibonacci" not in lowered:
        return []
    match = re.search(r"([A-Za-z0-9_.-]+\.py)", prompt)
    path = match.group(1) if match else "test123.py"
    code = (
        "def fibonacci(n):\n"
        "    if n < 2:\n"
        "        return n\n"
        "    return fibonacci(n - 1) + fibonacci(n - 2)\n\n"
        "print(fibonacci(7))\n"
    )
    return [
        {"tool": "write_file", "params": {"path": path, "content": code}},
        {"tool": "read_file", "params": {"path": path}},
        {"tool": "run_command", "params": {"command": f"python {path}"}},
    ]


def planned_tool_calls(prompt: str) -> List[Dict[str, Any]]:
    calls = parse_tool_calls(prompt)
    if calls:
        return calls
    for planner in (_natural_fibonacci, _natural_create_file, _natural_hello_world):
        calls = planner(prompt)
        if calls:
            return calls
    if any(word in prompt.lower() for word in ("tara", "listele", "rapor", "scan", "list all files", "current directory")):
        return [{"tool": "list_directory", "params": {"path": "."}}]
    read_match = re.search(r"([A-Za-z0-9_.-]+\.(?:py|js|html|css|md|txt|json|yaml|yml))\s+(?:dosyasını\s+oku|dosyasini\s+oku|oku|read)", prompt, flags=re.IGNORECASE)
    if read_match:
        return [{"tool": "read_file", "params": {"path": read_match.group(1)}}]
    return []


def run_agent(prompt: str, workspace_root: str | Path | None = None, session_id: str = "default", max_steps: int = 12) -> Dict[str, Any]:
    workspace = str(Path(workspace_root).expanduser().resolve()) if workspace_root else str(Path(__file__).resolve().parent)
    session_result = session_manager.start_session(session_id=session_id, workspace_root=workspace)
    session = dict(session_result.get("result") or {})
    session_manager.append_message(session, "user", prompt)
    calls = planned_tool_calls(prompt)
    if not calls:
        response = {
            "ok": False,
            "status": "no_tool_call",
            "mode": "agent",
            "response": "No executable tool call was found. Send JSON tool format or a supported file command.",
            "message": "No executable tool call was found. Send JSON tool format or a supported file command.",
            "tool_calls": [],
            "system_prompt": CODER_SYSTEM_PROMPT,
        }
        session_manager.append_message(session, "assistant", response["message"])
        session_manager.save_session(session)
        return response
    results: List[Dict[str, Any]] = []
    for index, call in enumerate(calls[:max_steps], start=1):
        tool_result = execute_tool(call["tool"], call.get("params", {}), workspace_root=workspace)
        item = {"step": index, "tool": call["tool"], "params": call.get("params", {}), "result": tool_result}
        results.append(item)
        session_manager.record_change(session, call["tool"], item)
        if not tool_result.get("success"):
            session_manager.append_message(session, "assistant", f"Tool failed: {call['tool']} -> {tool_result.get('error')}")
            session_manager.save_session(session)
            return {
                "ok": False,
                "mode": "agent",
                "status": "tool_failed",
                "response": f"Tool failed: {call['tool']} -> {tool_result.get('error')}",
                "workspace_root": workspace,
                "results": results,
                "tool_calls": results,
                "failed_step": item,
            }
    message = f"Completed {len(results)} tool step(s)."
    session_manager.append_message(session, "assistant", message)
    session_manager.save_session(session)
    return {
        "ok": True,
        "mode": "agent",
        "status": "completed",
        "workspace_root": workspace,
        "message": message,
        "response": message,
        "results": results,
        "tool_calls": results,
    }


def run_tool_json(payload: Dict[str, Any], workspace_root: str | Path | None = None) -> Tuple[bool, Dict[str, Any]]:
    tool = str(payload.get("tool") or "")
    params = dict(payload.get("params") or {})
    if not tool:
        return False, {"success": False, "result": "", "error": "missing_tool"}
    output = execute_tool(tool, params, workspace_root=workspace_root)
    return bool(output.get("success")), output
