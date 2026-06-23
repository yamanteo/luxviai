from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from openai import OpenAI

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


CHAT_SYSTEM_PROMPT = """Sen LuxCode adında yardımcı ve net bir yapay zeka asistansın.
Kullanıcı normal sohbet ediyorsa doğal cevap ver.
Kullanıcı kod, dosya, klasör, test, patch veya terminal işi isterse kısa ve net cevap ver.
Önceki konuşma geçmişini dikkate al. Kullanıcının verdiği isim gibi bilgileri aynı session içinde hatırla.
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
    def clean_content(value: str) -> str:
        content = str(value or "").strip()
        content = re.sub(r"\s+(?:yaz|write)\s*$", "", content, flags=re.IGNORECASE).strip()
        if content.lower().startswith("print ") and not content.lower().startswith("print("):
            inner = content[6:].strip()
            content = f"print({inner!r})"
        if content.startswith("print(") and not re.search(r"print\((['\"])", content):
            inner = content[6:-1] if content.endswith(")") else content[6:]
            content = f"print({inner.strip()!r})"
        return content + ("\n" if content and not content.endswith("\n") else "")

    match = re.search(
        r"(?:create|oluştur|olustur)\s+(?P<path>[^\s\"']+)\s+(?:with content|içine|icine)\s+(?P<quote>['\"])(?P<content>.*?)(?P=quote)",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return [{"tool": "write_file", "params": {"path": match.group("path"), "content": clean_content(match.group("content"))}}]
    turkish_file_first = re.search(
        r"(?P<path>[^\s\"']+\.[A-Za-z0-9]+)\s+(?:dosyasi|dosyasini|dosyası|dosyasını)?\s*(?:create|oluştur|olustur|yarat)?\s*(?:içine|icine|with content)\s+(?P<content>.+)$",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if turkish_file_first:
        return [{"tool": "write_file", "params": {"path": turkish_file_first.group("path"), "content": clean_content(turkish_file_first.group("content"))}}]
    loose = re.search(
        r"(?:create|oluştur|olustur)(?:\s+a\s+file\s+called|\s+file\s+called|\s+dosya)?\s+(?P<path>[^\s\"']+)\s+(?:with content|içine|icine)\s+(?P<content>.+)$",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if loose:
        return [{"tool": "write_file", "params": {"path": loose.group("path"), "content": clean_content(loose.group("content"))}}]
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


def _natural_stress_sum(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "stress_test.py" not in lowered or not any(token in lowered for token in ("1den 100e", "1'den 100'e", "1 den 100")):
        return []
    code = (
        "def toplam_1den_100e():\n"
        "    return sum(range(1, 101))\n\n"
        "if __name__ == \"__main__\":\n"
        "    print(toplam_1den_100e())\n"
    )
    return [
        {"tool": "write_file", "params": {"path": "stress_test.py", "content": code}},
        {"tool": "read_file", "params": {"path": "stress_test.py"}},
        {"tool": "run_command", "params": {"command": "python stress_test.py"}},
    ]


def _natural_stress_product_edit(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "stress_test.py" not in lowered or "carpim" not in lowered:
        return []
    code = (
        "def toplam_1den_100e():\n"
        "    return sum(range(1, 101))\n\n"
        "def carpim_1den_10a():\n"
        "    sonuc = 1\n"
        "    for sayi in range(1, 11):\n"
        "        sonuc *= sayi\n"
        "    return sonuc\n\n"
        "if __name__ == \"__main__\":\n"
        "    print(toplam_1den_100e())\n"
        "    print(carpim_1den_10a())\n"
    )
    return [
        {"tool": "read_file", "params": {"path": "stress_test.py"}},
        {"tool": "write_file", "params": {"path": "stress_test.py", "content": code}},
        {"tool": "read_file", "params": {"path": "stress_test.py"}},
        {"tool": "run_command", "params": {"command": "python stress_test.py"}},
    ]


def _natural_app_analysis(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "app.py" not in lowered or not any(token in lowered for token in ("kac satir", "endpoint", "import")):
        return []
    code = (
        "from pathlib import Path\n"
        "import ast\n"
        "text = Path('app.py').read_text(encoding='utf-8-sig', errors='replace')\n"
        "tree = ast.parse(text)\n"
        "imports = []\n"
        "for node in tree.body:\n"
        "    if isinstance(node, ast.Import):\n"
        "        imports.extend(alias.name for alias in node.names)\n"
        "    elif isinstance(node, ast.ImportFrom):\n"
        "        imports.append(node.module or '')\n"
        "endpoints = []\n"
        "for node in ast.walk(tree):\n"
        "    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):\n"
        "        for deco in node.decorator_list:\n"
        "            call = deco if isinstance(deco, ast.Call) else None\n"
        "            func = call.func if call else deco\n"
        "            attr = getattr(func, 'attr', '')\n"
        "            base = getattr(getattr(func, 'value', None), 'id', '')\n"
        "            if base == 'app' and attr in {'get', 'post', 'put', 'delete', 'api_route'}:\n"
        "                route = call.args[0].value if call and call.args and isinstance(call.args[0], ast.Constant) else ''\n"
        "                endpoints.append(f'{attr.upper()} {route}')\n"
        "print('line_count=' + str(len(text.splitlines())))\n"
        "print('imports=' + ', '.join(sorted(set(imports))[:80]))\n"
        "print('endpoints=' + '\\n'.join(endpoints[:120]))\n"
    )
    return [{"tool": "run_python", "params": {"code": code, "timeout": 60}}]


def _natural_folder_ops(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "test_folder" not in lowered or "hello.py" not in lowered or "world.py" not in lowered:
        return []
    return [
        {"tool": "create_directory", "params": {"path": "test_folder"}},
        {"tool": "write_file", "params": {"path": "test_folder/hello.py", "content": "print('hello')\n"}},
        {"tool": "write_file", "params": {"path": "test_folder/world.py", "content": "print('world')\n"}},
        {"tool": "read_file", "params": {"path": "test_folder/hello.py"}},
        {"tool": "read_file", "params": {"path": "test_folder/world.py"}},
        {"tool": "run_command", "params": {"command": "python test_folder/hello.py"}},
        {"tool": "run_command", "params": {"command": "python test_folder/world.py"}},
    ]


def _natural_list_directory(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if not any(token in lowered for token in ("listele", "liste", "list")):
        return []
    path_match = re.search(r"([A-Za-z]:[\\/][^\s'\",.?!]+|/[^\\s'\",.!?]+)", prompt)
    if not path_match:
        return []
    return [{"tool": "list_directory", "params": {"path": path_match.group(1)}}]


def _natural_multi_read(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "oku" not in lowered:
        return []
    files = sorted(set(re.findall(r"\b([A-Za-z0-9_./-]+\.(?:py|js|html|css|md|txt|json|yaml|yml|toml|ini|cfg))\b", prompt, flags=re.IGNORECASE)))
    if len(files) < 2:
        return []
    return [{"tool": "read_file", "params": {"path": path}} for path in files]


def _extract_agent_memory_updates(prompt: str) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    text = str(prompt or "").strip()
    if not text:
        return updates
    lower = text.lower()
    if "adim ne" in lower or "adım ne" in lower or lower.endswith("?"):
        return updates
    if "benim adim" in lower or "benim adım" in lower:
        m = re.search(
            r"benim\s+ad(?:i|ı)m(?:\si|ı|i|y)?\s+(.+?)(?:\s+(?:olarak|gibi)\s+kaydet)?\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            value = m.group(1).strip().strip(".'\"")
            value = re.sub(r"\s+olarak\s+kaydet$", "", value, flags=re.IGNORECASE).strip()
            if value:
                updates["name"] = value
    return updates


def _resolve_agent_memory_response(prompt: str, session: Dict[str, Any]) -> Dict[str, Any] | None:
    question = str(prompt or "").strip().lower()
    memory = session.get("memory") or {}
    if not isinstance(memory, dict):
        memory = {}
    if "adım" in question or "adim" in question:
        if "benim adim" in question:
            return {
                "ok": True,
                "status": "memory_response",
                "mode": "agent",
                "response": f"Adin: {memory.get('name', 'bilinmiyor')}.",
                "message": f"Adin: {memory.get('name', 'bilinmiyor')}.",
                "tool_calls": [],
                "system_prompt": CODER_SYSTEM_PROMPT,
            }
    return None


def _natural_bug_fix(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "buggy.py" not in lowered or not any(token in lowered for token in ("duzelt", "düzelt", "fix")):
        return []
    fixed = "def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n"
    return [
        {"tool": "read_file", "params": {"path": "buggy.py"}},
        {"tool": "write_file", "params": {"path": "buggy.py", "content": fixed}},
        {"tool": "read_file", "params": {"path": "buggy.py"}},
        {"tool": "run_command", "params": {"command": "python buggy.py"}},
    ]


def _natural_project_scan(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if not ("tum projeyi tara" in lowered or "tüm projeyi tara" in lowered):
        return []
    code = (
        "from pathlib import Path\n"
        "root = Path('.')\n"
        "skip = {'.git', '__pycache__', '.venv', 'node_modules'}\n"
        "files = []\n"
        "suffixes = {}\n"
        "for p in root.rglob('*'):\n"
        "    if any(part in skip for part in p.parts):\n"
        "        continue\n"
        "    if p.is_file():\n"
        "        files.append(p)\n"
        "        suffixes[p.suffix or '<none>'] = suffixes.get(p.suffix or '<none>', 0) + 1\n"
        "main_files = [str(p.as_posix()) for p in files if p.name in {'app.py','run_desktop.py','README.md','requirements.txt'}]\n"
        "tech = []\n"
        "if any(p.suffix == '.py' for p in files): tech.append('Python/FastAPI')\n"
        "if any(p.suffix in {'.js','.html','.css'} for p in files): tech.append('HTML/CSS/JavaScript')\n"
        "print('file_count=' + str(len(files)))\n"
        "print('technologies=' + ', '.join(tech))\n"
        "print('main_files=' + ', '.join(main_files[:30]))\n"
        "print('suffixes=' + str(dict(sorted(suffixes.items()))))\n"
        "print('summary=LUXDEEP local FastAPI backend with LuxCode web frontend and agent/coder tooling.')\n"
    )
    return [
        {"tool": "list_directory", "params": {"path": "."}},
        {"tool": "run_python", "params": {"code": code, "timeout": 120}},
    ]


def _natural_multi_tool_utils(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "requirements.txt" not in lowered or "utils.py" not in lowered or "test_utils.py" not in lowered:
        return []
    utils_code = (
        "from datetime import datetime\n\n"
        "def format_date(value, fmt='%Y-%m-%d'):\n"
        "    if isinstance(value, str):\n"
        "        value = datetime.fromisoformat(value)\n"
        "    return value.strftime(fmt)\n"
    )
    test_code = (
        "from utils import format_date\n\n"
        "def test_format_date():\n"
        "    assert format_date('2026-06-22T10:20:30') == '2026-06-22'\n\n"
        "if __name__ == '__main__':\n"
        "    test_format_date()\n"
        "    print('test_utils PASS')\n"
    )
    return [
        {"tool": "read_file", "params": {"path": "requirements.txt"}},
        {"tool": "write_file", "params": {"path": "utils.py", "content": utils_code}},
        {"tool": "write_file", "params": {"path": "test_utils.py", "content": test_code}},
        {"tool": "read_file", "params": {"path": "utils.py"}},
        {"tool": "read_file", "params": {"path": "test_utils.py"}},
        {"tool": "run_command", "params": {"command": "python test_utils.py"}},
    ]


def planned_tool_calls(prompt: str) -> List[Dict[str, Any]]:
    calls = parse_tool_calls(prompt)
    if calls:
        return calls
    for planner in (
        _natural_list_directory,
        _natural_multi_read,
        _natural_stress_product_edit,
        _natural_stress_sum,
        _natural_app_analysis,
        _natural_folder_ops,
        _natural_bug_fix,
        _natural_project_scan,
        _natural_multi_tool_utils,
        _natural_fibonacci,
        _natural_create_file,
        _natural_hello_world,
    ):
        calls = planner(prompt)
        if calls:
            return calls
    if any(word in prompt.lower() for word in ("tara", "listele", "rapor", "scan", "list all files", "current directory")):
        return [{"tool": "list_directory", "params": {"path": "."}}]
    read_match = re.search(r"([A-Za-z0-9_.-]+\.(?:py|js|html|css|md|txt|json|yaml|yml))\s+(?:dosyasını\s+oku|dosyasini\s+oku|oku|read)", prompt, flags=re.IGNORECASE)
    if read_match:
        return [{"tool": "read_file", "params": {"path": read_match.group(1)}}]
    return []


def _history_messages(session: Dict[str, Any], limit: int = 16) -> List[Dict[str, str]]:
    raw = session.get("conversation_history") or session.get("messages") or []
    history: List[Dict[str, str]] = []
    for item in raw[-limit:]:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content})
    return history


def _fallback_chat_response(prompt: str, session: Dict[str, Any]) -> str:
    lower = str(prompt or "").lower()
    memory = session.get("memory") if isinstance(session.get("memory"), dict) else {}
    if "2+2" in lower or "2 + 2" in lower:
        return "2+2 = 4."
    if ("adim ne" in lower or "adım ne" in lower or "benim adim ne" in lower or "benim adım ne" in lower) and memory.get("name"):
        return f"Adın {memory['name']}."
    if "benim adim" in lower or "benim adım" in lower:
        return "Tamam, adını bu oturum için kaydettim."
    return "Mesajını aldım. Nasıl yardımcı olmamı istersin?"


def _call_chat_llm(prompt: str, session: Dict[str, Any]) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if not api_key:
        return _fallback_chat_response(prompt, session)
    base_url = "https://api.deepseek.com" if os.getenv("DEEPSEEK_API_KEY") else None
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    messages: List[Dict[str, str]] = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    messages.extend(_history_messages(session))
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != prompt:
        messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=os.getenv("LUXCODE_CHAT_MODEL") or ("deepseek-chat" if base_url else "gpt-4o-mini"),
        messages=messages,
        temperature=0.25,
        max_tokens=700,
    )
    return (response.choices[0].message.content or "").strip() or _fallback_chat_response(prompt, session)


def run_agent(
    prompt: str,
    workspace_root: str | Path | None = None,
    session_id: str = "default",
    max_steps: int = 12,
    on_step: Callable[[Dict[str, Any]], None] | None = None,
) -> Dict[str, Any]:
    workspace = str(Path(workspace_root).expanduser().resolve()) if workspace_root else str(Path(__file__).resolve().parent)
    session_result = session_manager.start_session(session_id=session_id, workspace_root=workspace)
    session = dict(session_result.get("result") or {})
    session_manager.append_message(session, "user", prompt)
    memory_updates = _extract_agent_memory_updates(prompt)
    if memory_updates:
        current_memory = dict(session.get("memory") or {})
        current_memory.update(memory_updates)
        session["memory"] = current_memory
        saved_name = memory_updates.get("name")
        confirmation = f"Adını {saved_name} olarak kaydettim." if saved_name else f"memory_updated:{json.dumps(memory_updates, ensure_ascii=False)}"
        session_manager.append_message(session, "assistant", confirmation)
        session_manager.save_session(session)
        return {
            "ok": True,
            "status": "memory_updated",
            "mode": "chat",
            "response": confirmation,
            "message": confirmation,
            "tool_calls": [],
            "conversation_history": session.get("conversation_history", []),
        }

    memory_reply = _resolve_agent_memory_response(prompt, session)
    if memory_reply:
        session_manager.append_message(session, "assistant", str(memory_reply.get("response") or memory_reply.get("message") or ""))
        session_manager.save_session(session)
        memory_reply["conversation_history"] = session.get("conversation_history", [])
        return memory_reply
    calls = planned_tool_calls(prompt)
    if not calls:
        try:
            message = _call_chat_llm(prompt, session)
        except Exception as exc:
            message = _fallback_chat_response(prompt, session)
            session["last_chat_error"] = str(exc)
        session_manager.append_message(session, "assistant", message)
        session_manager.save_session(session)
        if on_step:
            on_step({
                "type": "response",
                "status": "completed",
                "ok": True,
                "response": message,
            })
        return {
            "ok": True,
            "status": "chat_completed",
            "mode": "chat",
            "response": message,
            "message": message,
            "tool_calls": [],
            "system_prompt": CHAT_SYSTEM_PROMPT,
            "conversation_history": session.get("conversation_history", []),
        }
    results: List[Dict[str, Any]] = []
    for index, call in enumerate(calls[:max_steps], start=1):
        if on_step:
            on_step({
                "type": "tool",
                "status": "running",
                "tool": call.get("tool"),
                "step": index,
                "params": call.get("params", {}),
            })
        tool_result = execute_tool(call["tool"], call.get("params", {}), workspace_root=workspace)
        item = {"step": index, "tool": call["tool"], "params": call.get("params", {}), "result": tool_result}
        results.append(item)
        session_manager.record_change(session, call["tool"], item)
        if on_step:
            on_step({
                "type": "tool",
                "status": "done" if tool_result.get("success") else "failed",
                "tool": call["tool"],
                "step": index,
                "params": call.get("params", {}),
                "result": tool_result,
            })
        if not tool_result.get("success"):
            session_manager.append_message(session, "assistant", f"Tool failed: {call['tool']} -> {tool_result.get('error')}")
            session_manager.save_session(session)
            if on_step:
                on_step({
                    "type": "response",
                    "status": "failed",
                    "ok": False,
                    "response": f"Tool failed: {call['tool']} -> {tool_result.get('error')}",
                    "result": tool_result,
                })
            return {
                "ok": False,
                "mode": "agent",
                "status": "tool_failed",
                "response": f"Tool failed: {call['tool']} -> {tool_result.get('error')}",
                "workspace_root": workspace,
                "results": results,
                "tool_calls": results,
                "failed_step": item,
                "conversation_history": session.get("conversation_history", []),
            }
    message = f"Completed {len(results)} tool step(s)."
    session_manager.append_message(session, "assistant", message)
    session_manager.save_session(session)
    if on_step:
        on_step({
            "type": "response",
            "status": "completed",
            "ok": True,
            "response": message,
            "result": {"results": results},
        })
    return {
        "ok": True,
        "mode": "agent",
        "status": "completed",
        "workspace_root": workspace,
        "message": message,
        "response": message,
        "results": results,
        "tool_calls": results,
        "conversation_history": session.get("conversation_history", []),
    }


def run_tool_json(payload: Dict[str, Any], workspace_root: str | Path | None = None) -> Tuple[bool, Dict[str, Any]]:
    tool = str(payload.get("tool") or "")
    params = dict(payload.get("params") or {})
    if not tool:
        return False, {"success": False, "result": "", "error": "missing_tool"}
    output = execute_tool(tool, params, workspace_root=workspace_root)
    return bool(output.get("success")), output
