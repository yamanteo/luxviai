from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_constitution_engine_preview import build_constitution_preview


RULE_CATEGORIES: List[str] = [
    "protected_runtime",
    "protected_files",
    "required_tests",
    "approval_rules",
    "deployment_rules",
    "safety_rules",
]


PROJECT_RULES: Dict[str, Dict[str, Any]] = {
    "protected_runtime": {
        "rule_name": "stop_continue_protection",
        "rule_priority": "high",
        "aliases": ["runtime", "chat", "stream", "websocket", "typewriter", "stop", "continue", "dur", "devam"],
        "protected_areas": ["chat", "stream", "websocket", "typewriter", "stop_continue"],
        "required_checks": ["smoke_check", "manual_scenario", "constitution_preview", "change_boundary_review"],
        "recommended_actions": ["analysis", "read_only_preview", "manual_test_plan"],
        "blocked_actions": ["auto_patch", "auto_commit", "auto_push", "auto_deploy", "runtime_change_without_approval"],
    },
    "protected_files": {
        "rule_name": "static_and_runtime_file_guard",
        "rule_priority": "high",
        "aliases": ["file", "static", "index", "app.py", "runtime"],
        "protected_areas": ["static/index.html", "app.py runtime sections", "stream handlers"],
        "required_checks": ["py_compile", "smoke_check", "endpoint_coverage"],
        "recommended_actions": ["narrow_diff", "read_only_plan", "explicit_scope_check"],
        "blocked_actions": ["broad_refactor", "unrequested_static_edit", "auto_patch", "auto_commit"],
    },
    "required_tests": {
        "rule_name": "layer_close_test_gate",
        "rule_priority": "medium",
        "aliases": ["test", "smoke", "compile", "verification"],
        "protected_areas": ["layer_completion", "endpoint_contracts", "debug_panel"],
        "required_checks": ["python -m py_compile", "python scripts/smoke_check.py", "targeted_endpoint_check"],
        "recommended_actions": ["run_required_tests", "report_pass_fail", "preserve_existing_tests"],
        "blocked_actions": ["skip_smoke_without_notice", "ignore_compile_failure"],
    },
    "approval_rules": {
        "rule_name": "protected_change_approval_gate",
        "rule_priority": "high",
        "aliases": ["approval", "permission", "onay", "protected", "critical"],
        "protected_areas": ["protected_runtime", "private_data", "write_operations", "deployment"],
        "required_checks": ["safe_change_boundary", "constitution_preview", "user_scope_confirmation"],
        "recommended_actions": ["ask_before_real_write", "plan_before_patch", "show_risk"],
        "blocked_actions": ["auto_patch", "auto_send", "auto_delete", "auto_deploy"],
    },
    "deployment_rules": {
        "rule_name": "deploy_preview_only_gate",
        "rule_priority": "medium",
        "aliases": ["deploy", "render", "push", "github"],
        "protected_areas": ["deployment", "render", "github main"],
        "required_checks": ["git_status", "smoke_check", "push_result_check"],
        "recommended_actions": ["commit_after_tests", "push_after_clean_status", "report_commit_hash"],
        "blocked_actions": ["deploy_without_push", "force_push", "unverified_release"],
    },
    "safety_rules": {
        "rule_name": "strict_no_write_preview_guard",
        "rule_priority": "critical",
        "aliases": ["safety", "read only", "strict", "no write", "preview"],
        "protected_areas": ["file_write", "memory_write", "db_write", "git_write", "subprocess_execution"],
        "required_checks": ["read_only_flags", "write_flags_false", "constitution_preview"],
        "recommended_actions": ["analysis_only", "preview_only", "explicit_safety_note"],
        "blocked_actions": ["file_write", "memory_write", "db_write", "auto_fix", "patch_apply", "subprocess_execution"],
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_category(command: str, requested_category: Optional[str]) -> str:
    if requested_category in PROJECT_RULES:
        return str(requested_category)
    haystack = _normalize(f"{requested_category or ''} {command or ''}")
    for category, rule in PROJECT_RULES.items():
        if any(str(alias).lower() in haystack for alias in rule.get("aliases", [])):
            return category
    return "protected_runtime"


def project_rules_status() -> Dict[str, Any]:
    return {
        "layer": "26.2",
        "name": "Project Rules Loader Preview",
        "status": "project_rules_loader_preview_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_file_read_performed": False,
        "real_action_performed": False,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "git_write_enabled": False,
        "commit_enabled": False,
        "push_enabled": False,
        "deploy_enabled": False,
        "auto_fix_enabled": False,
        "patch_apply_enabled": False,
        "subprocess_execution_enabled": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "rule_categories": RULE_CATEGORIES,
        "available_endpoints": [
            "/debug/project-rules-status",
            "/debug/project-rules-registry",
            "/debug/project-rules-preview",
        ],
        "connected_layers": ["26.1 Agent Constitution Engine"],
        "future_direction": ["Explorer Agent", "Planner Agent", "Verifier Agent", "Coordinator Agent"],
        "safety_note": "Project Rules Loader is preview-only and does not read real files, write files, run subprocesses, apply patches, commit, push, or deploy.",
    }


def project_rules_registry() -> Dict[str, Any]:
    return {
        "layer": "26.2",
        "name": "Project Rules Registry",
        "status": "project_rules_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_file_read_performed": False,
        "rule_categories": RULE_CATEGORIES,
        "rules": [
            {
                "project_rule_category": category,
                "rule_name": rule["rule_name"],
                "rule_priority": rule["rule_priority"],
                "protected_areas": rule["protected_areas"],
                "required_checks": rule["required_checks"],
                "recommended_actions": rule["recommended_actions"],
                "blocked_actions": rule["blocked_actions"],
            }
            for category, rule in PROJECT_RULES.items()
        ],
        "safety_flags": {
            "real_file_read": False,
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "git_write": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "auto_fix": False,
            "patch_apply": False,
            "subprocess_execution": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_project_rules_preview(
    command: str = "",
    project_rule_category: Optional[str] = None,
    target_area: Optional[str] = None,
) -> Dict[str, Any]:
    category = _select_category(command, project_rule_category)
    rule = PROJECT_RULES[category]
    constitution = build_constitution_preview(
        command=command or category,
        rule_source="project_rules",
        conflicting_rules=["project_layer_rule", "read_only_mode"],
        target_area=target_area or category,
    )
    return {
        "project_rule_category": category,
        "rule_name": rule["rule_name"],
        "rule_priority": rule["rule_priority"],
        "protected_areas": list(rule["protected_areas"]),
        "required_checks": list(rule["required_checks"]),
        "recommended_actions": list(rule["recommended_actions"]),
        "blocked_actions": list(rule["blocked_actions"]),
        "confidence_score": 0.9,
        "constitution_signal": {
            "selected_rule": constitution.get("selected_rule"),
            "rule_source": constitution.get("rule_source"),
            "rule_priority": constitution.get("rule_priority"),
            "resolution_reason": constitution.get("resolution_reason"),
        },
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_file_read_performed": False,
        "real_action_performed": False,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "patch_apply_performed": False,
        "subprocess_execution_performed": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "This is a strict read-only project rules preview. It uses an internal preview registry and does not read project files or modify runtime behavior.",
    }
