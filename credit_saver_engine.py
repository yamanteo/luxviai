from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from bug_intake_planner import build_bug_intake_preview
from codex_handoff_builder_preview import build_codex_handoff_preview
from root_flow_auditor_preview import build_root_flow_audit
from safe_self_check_runner_preview import build_self_check_preview


DECISION_PATHS: Dict[str, Dict[str, Any]] = {
    "lux_only": {
        "description": "Öncelikle güvenli okuyup analiz eder; doğrudan uygulama gerekmez.",
        "risk": "low",
        "complexity": "low",
        "estimated_credit_saving": 0.82,
        "codex_needed_for": [],
    },
    "lux_first_then_codex": {
        "description": "Lux ön analizi yapar, sonra netleşen noktada sınırlı Codex fix görevine geçilir.",
        "risk": "medium",
        "complexity": "medium",
        "estimated_credit_saving": 0.58,
        "codex_needed_for": [
            "implementation-level refactor",
            "state ownership changes",
            "code path boundary alignment",
        ],
    },
    "codex_direct": {
        "description": "Kök mantık yüksek riskli/karmaşıksa doğrudan Codex müdahalesi gerekiyor.",
        "risk": "high",
        "complexity": "high",
        "estimated_credit_saving": 0.26,
        "codex_needed_for": [
            "core stream/continuation state machine refactor",
            "runtime control-flow changes",
            "provider/router pipeline changes",
        ],
    },
    "manual_investigation_first": {
        "description": "Önce senaryo çoğaltılıp doğrulama beklenir, sonra karar verilir.",
        "risk": "medium",
        "complexity": "medium",
        "estimated_credit_saving": 0.32,
        "codex_needed_for": [
            "fielded reproduction data toplama",
            "çevresel log/şartların teyidi",
        ],
    },
}


SUPPORTED_CATEGORIES = {
    "typo",
    "missing_helper",
    "duplicate_branch",
    "stream_refactor",
    "architecture_redesign",
    "stop_continue",
    "workspace",
    "visual",
    "luxway",
    "model_router",
    "memory",
    "endpoint",
    "ui",
    "websocket",
    "permission_flow",
    "future_dev_agent",
    "core_refactor",
}


CATEGORY_ALIASES: Dict[str, List[str]] = {
    "typo": ["typo", "yazım", "düzelt", "harf", "kelime", "yazim", "imla", "yanlış", "yanlis", "metin bozul", "bozuldu"],
    "missing_helper": ["eksik", "yardımcı", "helper", "yardimci", "import", "modül", "module", "fonksiyon", "function", "bulunamadı", "not found"],
    "duplicate_branch": [
        "duplicate",
        "ikiz",
        "iki yol",
        "iki branch",
        "repeat",
        "tekrar",
        "çift",
        "çakış",
        "iki davranış",
    ],
    "stream_refactor": [
        "stream",
        "durdur",
        "devam",
        "continue",
        "resume",
        "ws",
        "websocket",
        "event",
        "fallback",
        "stopped",
        "duraklat",
        "interruption",
    ],
    "architecture_redesign": ["architecture", "core", "redesign", "yeniden", "tasarım", "yeniden yapı", "kernel", "refactor", "konteyner"],
    "workspace": ["workspace", "belge", "cv", "rapor", "sunum", "doküman", "paragraf"],
    "visual": ["görsel", "ambrosia", "rüya", "dream", "visual", "scene", "stil", "style"],
    "luxway": ["luxway", "telefon", "mail", "mesaj", "app", "uygulama", "takvim", "calendar", "notification", "bildirim"],
    "model_router": ["model", "router", "provider", "hint", "routing", "gpt", "deepseek", "mini", "model_hint", "image api"],
    "memory": ["hafıza", "memory", "özet", "summary", "retrieval", "hatırla", "kural", "context"],
    "endpoint": ["endpoint", "route", "api", "404", "not found", "kabul", "route missing", "yol"],
    "ui": ["ui", "arayüz", "frontend", "panel", "button", "buton", "debug panel", "interface", "tarayıcı"],
    "websocket": ["websocket", "ws", "socket", "stream", "late event", "gecikmiş", "late", "chunk", "chunked"],
    "permission_flow": ["izin", "permission", "onay", "confirmation", "sil", "delete", "send", "ara", "call"],
    "future_dev_agent": ["dev agent", "gelecek", "future", "katman", "handoff", "codex", "otomasyon"],
    "core_refactor": ["core", "stream", "pipeline", "state machine", "state", "continuation", "runtime"],
}


CATEGORY_TO_PATH = {
    "typo": "lux_only",
    "missing_helper": "lux_first_then_codex",
    "duplicate_branch": "lux_first_then_codex",
    "stream_refactor": "lux_first_then_codex",
    "architecture_redesign": "codex_direct",
    "core_refactor": "codex_direct",
    "stop_continue": "lux_first_then_codex",
    "workspace": "lux_first_then_codex",
    "visual": "lux_first_then_codex",
    "luxway": "lux_first_then_codex",
    "model_router": "lux_first_then_codex",
    "memory": "lux_first_then_codex",
    "endpoint": "lux_first_then_codex",
    "ui": "lux_first_then_codex",
    "websocket": "codex_direct",
    "permission_flow": "lux_first_then_codex",
    "future_dev_agent": "manual_investigation_first",
}


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _safe_unique(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in values:
        norm = str(item or "").strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def _detect_category(behavior: Optional[str], symptom: str, expected_result: str, actual_result: str, command: str) -> str:
    if behavior and _normalize(behavior) in SUPPORTED_CATEGORIES:
        return _normalize(behavior)

    haystack = _normalize(" ".join(part for part in [symptom, expected_result, actual_result, command] if part))
    for category, aliases in CATEGORY_ALIASES.items():
        if category in SUPPORTED_CATEGORIES and any(alias in haystack for alias in aliases):
            return category
    # fallback through root-flow owner hints
    if "stop" in haystack or "durdur" in haystack or "devam" in haystack:
        return "stop_continue"
    return "future_dev_agent"


def _pick_path(category: str, risk_level: str, confidence: float) -> str:
    path = CATEGORY_TO_PATH.get(category, "manual_investigation_first")
    if path == "lux_first_then_codex" and risk_level == "high" and confidence < 0.5:
        return "manual_investigation_first"
    return path


def _complexity_for(path: str, risk_level: str) -> str:
    if path == "lux_only":
        return "low"
    if path == "manual_investigation_first":
        return "medium" if risk_level == "low" else "high" if risk_level == "critical" else "medium"
    if path == "lux_first_then_codex":
        return "low" if risk_level == "low" else "medium"
    if path == "codex_direct":
        return "critical" if risk_level == "high" else "high"
    return "medium"


def credit_saver_status() -> Dict[str, Any]:
    return {
        "layer": "23.5",
        "name": "Credit Saver Engine Preview",
        "status": "scaffold_ready",
        "read_only": True,
        "analysis_only": True,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "git_write_enabled": False,
        "auto_fix_enabled": False,
        "can_modify_code": False,
        "can_commit": False,
        "can_push": False,
        "can_deploy": False,
        "root_flow_auditor_connected": True,
        "self_check_connected": True,
        "handoff_connected": True,
        "bug_intake_connected": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "real_fix_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": (
            "Read-only credit triage only. "
            "No file write, memory write, db write, git write, commit, push, deploy, or auto-fix."
        ),
    }


def credit_saver_registry() -> Dict[str, Any]:
    return {
        "layer": "23.5",
        "status": "registry_ready",
        "read_only": True,
        "analysis_only": True,
        "supported_bug_categories": sorted(SUPPORTED_CATEGORIES),
        "supported_paths": [
            {
                "id": path_id,
                "description": meta["description"],
                "risk_level": meta["risk"],
                "default_complexity": meta["complexity"],
                "estimated_credit_saving": meta["estimated_credit_saving"],
            }
            for path_id, meta in DECISION_PATHS.items()
        ],
        "keyword_aliases": CATEGORY_ALIASES,
        "available_endpoints": [
            "/debug/credit-saver-status",
            "/debug/credit-saver-registry",
            "/debug/credit-saver-preview",
        ],
        "safety_flags": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "git_write": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "auto_fix": False,
        },
    }


def _estimated_credit_saving(path: str, risk_level: str, confidence: float, self_checks: List[str]) -> float:
    base = DECISION_PATHS.get(path, DECISION_PATHS["lux_first_then_codex"])["estimated_credit_saving"]
    # if many checks are requested confidence gets slightly adjusted upward and credit estimate too
    adjusted = base + 0.03 * min(len(self_checks), 3)
    if confidence >= 0.85:
        adjusted += 0.08
    if risk_level == "critical":
        adjusted -= 0.15
    return round(max(0.1, min(0.95, adjusted)), 2)


def build_credit_saver_preview(
    behavior: Optional[str] = None,
    symptom: str = "",
    expected_result: str = "",
    actual_result: str = "",
    command: str = "",
) -> Dict[str, Any]:
    combined = _normalize(" ".join(part for part in [command, symptom, expected_result, actual_result] if part))

    bug_category = _detect_category(behavior, symptom, expected_result, actual_result, command)
    root_flow = build_root_flow_audit(
        command=combined,
        behavior=bug_category if bug_category in {"workspace", "visual", "ui", "endpoint", "workspace"} else behavior,
        observed_behavior=actual_result or symptom,
        expected_behavior=expected_result,
        smoke_tests=[],
    )
    detected = str(root_flow.get("detected_behavior", bug_category or "endpoint_regression"))
    risk_level = str(root_flow.get("risk_level", "medium")).lower()
    confidence = float(root_flow.get("confidence_score", 0.5) or 0.5)

    self_check = build_self_check_preview(
        command=combined,
        behavior=detected,
        observed_behavior=actual_result or symptom,
        expected_behavior=expected_result,
    )
    checks_run = [str(item.get("id")) for item in self_check.get("checks_run", []) if isinstance(item, dict)]
    if not checks_run:
        checks_run = ["behavior_owner_check", "manual_scenario_check"]

    handoff = build_codex_handoff_preview(
        behavior=detected,
        symptom=symptom,
        expected_result=expected_result,
        actual_result=actual_result,
        command=command,
        requested_checks=checks_run,
    )
    bug_intake = build_bug_intake_preview(
        behavior=bug_category,
        symptom=symptom,
        expected_result=expected_result,
        actual_result=actual_result,
        command=command,
    )

    if risk_level == "critical":
        confidence = min(0.99, confidence + 0.08)
    elif risk_level == "high":
        confidence = min(0.97, confidence + 0.06)
    else:
        confidence = min(0.95, confidence + 0.03)

    recommended_path = _pick_path(bug_category, risk_level, confidence)
    estimated_complexity = _complexity_for(recommended_path, risk_level)
    estimated_credit_saving = _estimated_credit_saving(recommended_path, risk_level, confidence, checks_run)

    path_meta = DECISION_PATHS.get(recommended_path, DECISION_PATHS["manual_investigation_first"])

    lux_only: List[str] = [
        "rule-based issue detection",
        "behavior-owner validation",
        "smoke-gap detection",
        "manual scenario planning",
        "initial file list suggestion",
    ]
    if risk_level == "low":
        lux_only.append("single-pass regression check recommendation")
    if risk_level in {"high", "critical"}:
        lux_only.append("severity-prioritized triage packaging")

    recommended_files = _safe_unique(
        [
            str(item) for item in root_flow.get("recommended_files", []) + handoff.get("recommended_files", []) + bug_intake.get("recommended_files", [])
        ]
    )

    return {
        "bug_category": bug_category,
        "detected_behavior": detected,
        "lux_can_handle": lux_only,
        "codex_needed_for": path_meta.get("codex_needed_for", []),
        "estimated_complexity": estimated_complexity,
        "recommended_path": recommended_path,
        "risk_level": risk_level,
        "confidence_score": round(confidence, 2),
        "estimated_credit_saving": estimated_credit_saving,
        "recommended_files": recommended_files,
        "recommended_self_checks": checks_run,
        "decision_matrix": {
            "path": recommended_path,
            "risk": path_meta.get("risk"),
            "default_complexity": path_meta.get("complexity"),
        },
        "root_flow_audit": root_flow,
        "self_check_preview": self_check,
        "codex_handoff_preview": handoff,
        "bug_intake_preview": bug_intake,
        "read_only": True,
        "analysis_only": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "real_fix_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Preview-only decision engine. No implementation, writes, or deployment actions are executed.",
    }
