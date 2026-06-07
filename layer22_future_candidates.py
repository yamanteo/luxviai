from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("ı", "i")


def _candidate(
    candidate_id: str,
    name: str,
    category: str,
    one_line: str,
    user_value: str,
    lux_identity_fit: str,
    practical_use_cases: List[str],
    required_existing_layers: List[str],
    risk_level: str,
    safety_boundary: str,
    implementation_stage: str = "future_candidate",
) -> Dict[str, Any]:
    return {
        "id": candidate_id,
        "name": name,
        "category": category,
        "one_line": one_line,
        "user_value": user_value,
        "lux_identity_fit": lux_identity_fit,
        "practical_use_cases": practical_use_cases,
        "required_existing_layers": required_existing_layers,
        "risk_level": risk_level,
        "safety_boundary": safety_boundary,
        "implementation_stage": implementation_stage,
        "real_action_enabled": False,
        "read_only": True,
    }


FUTURE_CANDIDATES: List[Dict[str, Any]] = [
    _candidate(
        "lux_time_twin",
        "Lux Time Twin",
        "personal_time_intelligence",
        "A future-facing personal time twin for energy rhythm, habits, and upcoming work.",
        "Helps the user see what their week may feel like before overcommitting.",
        "Strong fit: az tus cok is, personal agent, premium calm planning.",
        ["week preview", "energy-aware planning", "calendar-readiness concept"],
        ["Layer 14", "Layer 17", "Layer 18", "Layer 19"],
        "medium",
        "No real calendar, device, location, or memory access in this scaffold.",
    ),
    _candidate(
        "future_self_council",
        "Future Self Council",
        "self_reflection",
        "Decision support through multiple future-self perspectives.",
        "Turns a hard decision into a few clearer perspectives without pretending certainty.",
        "Adds emotional premium depth without becoming therapy.",
        ["decision reflection", "life rehearsal", "priority comparison"],
        ["Layer 21", "Layer 14"],
        "medium",
        "No therapy or clinical claim; only reflective preview language.",
    ),
    _candidate(
        "reality_layer",
        "Reality Layer",
        "reality_context",
        "A reality filter for current constraints, energy, time, and environment.",
        "Stops plans from becoming fantasy by checking real constraints supplied by the user.",
        "Very Lux: practical elegance and low-friction context awareness.",
        ["plan feasibility", "constraint check", "low-energy alternative"],
        ["Layer 15", "Layer 21"],
        "low",
        "No fabricated environment, calendar, or device facts.",
    ),
    _candidate(
        "memory_cinema",
        "Memory Cinema",
        "memory_experience",
        "A cinematic, controlled way to revisit past project, visual, audio, and document memories.",
        "Makes past work easier to understand and reuse as safe summaries.",
        "Premium identity fit: memory becomes a calm experience, not a database dump.",
        ["project recap", "visual memory tour", "document journey"],
        ["Layer 14", "Layer 16", "Layer 19"],
        "high",
        "No real memory retrieval and no raw sensitive content returned.",
    ),
    _candidate(
        "cognitive_mirror",
        "Cognitive Mirror",
        "cognition_support",
        "A meta mirror for thinking style, repeated decision patterns, and output style.",
        "Helps the user notice how they work without labeling them clinically.",
        "Matches Lux's quality core and self-understanding direction.",
        ["work pattern preview", "decision style reflection", "output habit review"],
        ["Layer 21", "Layer 19"],
        "medium",
        "No clinical analysis, diagnosis, or identity claim.",
    ),
    _candidate(
        "dream_os",
        "Dream OS",
        "dream_symbolic_layer",
        "A personal creative system for dreams, symbols, inner states, and visual language.",
        "Turns dream or symbolic material into creative states and prompts.",
        "Strong Lux Visual and Ambrosia identity fit.",
        ["dream scene system", "symbol-to-visual preview", "creative ritual"],
        ["Layer 16", "Layer 21"],
        "medium",
        "Creative expression only; no therapy claim or dream diagnosis.",
    ),
    _candidate(
        "personal_mythology",
        "Personal Mythology",
        "personal_identity",
        "Organizes repeated themes, symbols, goals, and character arcs as a personal mythology.",
        "Helps the user name recurring life themes without forcing identity.",
        "Distinctive premium layer for personal meaning and visual identity.",
        ["theme naming", "symbol library preview", "personal narrative map"],
        ["Layer 16", "Layer 21"],
        "high",
        "No identity manipulation or fixed claims about who the user is.",
    ),
    _candidate(
        "adaptive_interface",
        "Adaptive Interface",
        "adaptive_ui",
        "A UI that quietly expands or simplifies based on context and fatigue.",
        "Reduces user burden by showing fewer controls at the right time.",
        "Directly supports az tus cok is and premium simplicity.",
        ["low-stress workspace", "contextual controls", "fatigue-aware panel"],
        ["Layer 15", "Layer 21"],
        "low",
        "No real UI runtime change in this scaffold.",
    ),
    _candidate(
        "silent_companion_mode",
        "Silent Companion Mode",
        "silent_agent",
        "A calm support mode where Lux helps with fewer words and no unnecessary chatter.",
        "Lets the user feel supported without being interrupted.",
        "Highly aligned with Lux as a premium personal companion.",
        ["one-line nudges", "low-noise chat", "quiet workspace support"],
        ["Layer 17", "Layer 21"],
        "low",
        "No background action and no hidden monitoring.",
    ),
    _candidate(
        "personal_world_model",
        "Personal World Model",
        "world_model",
        "A permissioned map of projects, preferences, goals, routines, and working style.",
        "Makes Lux feel coherent across contexts when explicitly permitted.",
        "Central to personal agent identity, but must stay permission-first.",
        ["project map", "preference summary", "routine-aware planning"],
        ["Layer 14", "Layer 19", "Layer 21"],
        "high",
        "No real memory write, no raw private retrieval, and no hidden profiling.",
    ),
    _candidate(
        "emotional_weather",
        "Emotional Weather",
        "emotional_context",
        "A simple weather-like view of daily or weekly emotional energy.",
        "Gives gentle self-orientation without heavy analysis.",
        "Fits Lux's emotional reflection layer with a premium visual surface.",
        ["energy check-in", "week mood preview", "gentle pacing suggestion"],
        ["Layer 17", "Layer 21"],
        "medium",
        "No clinical diagnosis, therapy claim, or stored raw emotional history.",
    ),
    _candidate(
        "ambient_workspace",
        "Ambient Workspace",
        "ambient_productivity",
        "Workspace intelligence that quietly reduces clutter and surfaces the next useful tool.",
        "Makes work feel smoother without forcing a full editor mode.",
        "Strong practical value for LuxWorkspace.",
        ["contextual tools", "document cleanup preview", "quiet next-step support"],
        ["Layer 15", "Layer 21"],
        "low",
        "No real export, file creation, or editor mutation.",
    ),
    _candidate(
        "memory_sculpting",
        "Memory Sculpting",
        "memory_control",
        "A controlled tool for shaping what is remembered, summarized, forgotten, or never stored.",
        "Gives the user explicit agency over memory boundaries.",
        "Premium trust feature and strong privacy identity fit.",
        ["memory rule preview", "forget/summarize plan", "safe retention controls"],
        ["Layer 14", "Layer 19", "Layer 21"],
        "high",
        "No real memory read/write in this scaffold.",
    ),
    _candidate(
        "intention_timeline",
        "Intention Timeline",
        "intention_planning",
        "A future planning layer for intentions, decisions, and unresolved next steps.",
        "Keeps plans visible without committing them to calendar or tasks.",
        "Turns Lux into a calm planning companion.",
        ["decision timeline", "next-step preview", "future intent grouping"],
        ["Layer 14", "Layer 15", "Layer 21"],
        "medium",
        "No real calendar write or task automation.",
    ),
    _candidate(
        "autonomy_dial",
        "Autonomy Dial",
        "autonomy_control",
        "A user-controlled dial for how independently Lux may act.",
        "Makes agent autonomy visible and adjustable.",
        "Essential for safe premium personal agent behavior.",
        ["permission level preview", "action boundary UI", "confirmation policy"],
        ["Layer 14", "Layer 18", "Layer 21"],
        "high",
        "No real agent action; explicit permission and confirmation remain required.",
    ),
    _candidate(
        "ethical_boundary_soul",
        "Ethical Boundary Soul",
        "ethics_boundary",
        "A boundary system where privacy and trust feel like part of Lux's character.",
        "Makes safety understandable, not hidden in fine print.",
        "Very strong Lux identity fit: trust as product feel.",
        ["privacy explanation", "risk guard preview", "safe refusal style"],
        ["Layer 19", "Layer 21"],
        "medium",
        "Guard registry only; no enforcement pipeline change in this scaffold.",
    ),
    _candidate(
        "invisible_operator",
        "Invisible Operator",
        "invisible_operations",
        "A background operator concept for small preparations without leaving visible consent.",
        "Prepares drafts, checklists, and options without doing the real action.",
        "High practical and advertising value if permission boundaries stay clear.",
        ["draft prep", "pre-flight checklist", "non-executing assistant"],
        ["Layer 18", "Layer 21"],
        "high",
        "No send, delete, export, call, print, or device action.",
    ),
    _candidate(
        "context_rooms",
        "Context Rooms",
        "context_environment",
        "Separate rooms for different projects, moods, work modes, or learning contexts.",
        "Reduces context mixing and helps the user resume the right mental place.",
        "Strong premium UI and context intelligence fit.",
        ["project room preview", "visual context room", "workspace grouping"],
        ["Layer 15", "Layer 16", "Layer 21"],
        "medium",
        "No real cross-page retrieval or hidden history read.",
    ),
    _candidate(
        "aura_system",
        "Aura System",
        "personal_aura",
        "A tone, visual, voice, and UI atmosphere layer for work, rest, and creation modes.",
        "Makes Lux feel emotionally and aesthetically coherent.",
        "Signature premium layer combining visual, voice, and support systems.",
        ["calm aura", "focus aura", "creative aura"],
        ["Layer 16", "Layer 17", "Layer 21"],
        "medium",
        "No real theme, audio, or UI change in this scaffold.",
    ),
    _candidate(
        "finality_sense",
        "Finality Sense",
        "decision_closure",
        "A closure intelligence that detects whether work is complete, missing, or needs final review.",
        "Helps the user stop polishing too late or shipping too early.",
        "Practical premium value for work, documents, and decisions.",
        ["completion review", "missing piece check", "done/not-done preview"],
        ["Layer 15", "Layer 21"],
        "low",
        "No real task completion action or file export.",
    ),
]


ALIASES = {
    "lux_time_twin": ["time twin", "zaman", "zaman ikizi", "week", "gelecek"],
    "future_self_council": ["future self", "gelecek benlik", "council", "karar deste"],
    "reality_layer": ["reality", "gerceklik", "kisiti", "enerji", "durum"],
    "memory_cinema": ["memory cinema", "hafiza sinemasi", "gecmis", "ani"],
    "cognitive_mirror": ["cognitive mirror", "dusunme", "ayna", "karar kalibi"],
    "dream_os": ["dream os", "ruya", "sembol", "yaratici"],
    "personal_mythology": ["mythology", "mitoloji", "tema", "karakter"],
    "adaptive_interface": ["adaptive", "arayuz", "ui", "sadelestir"],
    "silent_companion_mode": ["silent", "sessiz", "refakat", "az kelime"],
    "personal_world_model": ["world model", "dunya modeli", "baglam haritasi"],
    "emotional_weather": ["emotional weather", "duygu hava", "enerji havasi"],
    "ambient_workspace": ["ambient workspace", "workspace", "ortam", "daginiklik"],
    "memory_sculpting": ["memory sculpting", "hafiza", "unut", "hatirla", "ozetle"],
    "intention_timeline": ["intention", "niyet", "timeline", "zaman cizgisi"],
    "autonomy_dial": ["autonomy", "otonomi", "bagimsiz", "kontrol dugmesi"],
    "ethical_boundary_soul": ["ethical", "etik", "boundary", "guvenlik", "gizlilik"],
    "invisible_operator": ["invisible operator", "gorunmez operator", "arka plan", "hazirlik"],
    "context_rooms": ["context room", "oda", "baglam odasi", "proje odasi"],
    "aura_system": ["aura", "ton", "gorsel", "ses", "mod hissi"],
    "finality_sense": ["finality", "tamamlandi", "bitis", "kapanis", "eksik"],
}


def future_candidates_registry() -> Dict[str, Any]:
    return {
        "layer": "22",
        "name": "Future / Near-Future Premium Candidates registry",
        "status": "future_candidates_ready",
        "candidate_count": len(FUTURE_CANDIDATES),
        "candidates": FUTURE_CANDIDATES,
        "read_only": True,
        "real_action_enabled": False,
    }


def _find_candidate(command: str, candidate_id: str = "", category: str = "") -> Dict[str, Any] | None:
    if candidate_id:
        wanted = _normalize(candidate_id)
        for candidate in FUTURE_CANDIDATES:
            if _normalize(candidate["id"]) == wanted or _normalize(candidate["name"]) == wanted:
                return candidate
    if category:
        wanted_category = _normalize(category)
        for candidate in FUTURE_CANDIDATES:
            if _normalize(candidate["category"]) == wanted_category:
                return candidate
    normalized = _normalize(command)
    for candidate in FUTURE_CANDIDATES:
        if _normalize(candidate["name"]) in normalized or candidate["id"] in normalized:
            return candidate
        for alias in ALIASES.get(candidate["id"], []):
            if _normalize(alias) in normalized:
                return candidate
    return None


def _candidate_ranking(command: str) -> List[Dict[str, Any]]:
    normalized = _normalize(command)
    if any(key in normalized for key in ["reklam", "advert", "pazar", "market"]):
        preferred = ["aura_system", "lux_time_twin", "memory_cinema", "silent_companion_mode", "invisible_operator"]
    elif any(key in normalized for key in ["pratik", "useful", "gunluk", "kolay"]):
        preferred = ["lux_time_twin", "ambient_workspace", "finality_sense", "reality_layer", "silent_companion_mode"]
    elif any(key in normalized for key in ["guvenlik", "risk", "yuksek", "ayir"]):
        preferred = ["memory_cinema", "personal_world_model", "memory_sculpting", "autonomy_dial", "invisible_operator"]
    elif any(key in normalized for key in ["ozel", "kimlik", "identity", "farkli"]):
        preferred = ["ethical_boundary_soul", "aura_system", "dream_os", "personal_mythology", "silent_companion_mode"]
    else:
        preferred = ["lux_time_twin", "ambient_workspace", "autonomy_dial"]

    by_id = {candidate["id"]: candidate for candidate in FUTURE_CANDIDATES}
    return [by_id[item] for item in preferred if item in by_id]


def preview_future_candidate(
    command: str,
    candidate_id: str = "",
    category: str = "",
    user_goal: str = "",
    risk_level: str = "",
    implementation_depth: str = "",
) -> Dict[str, Any]:
    matched = _find_candidate(command, candidate_id, category)
    ranking = _candidate_ranking(command)
    if matched is None and ranking:
        matched = ranking[0]

    candidate_summary = matched["one_line"] if matched else "No confident candidate match; keep this as a low-confidence idea preview."
    suggested_next_step = "Keep this as a read-only concept card; choose one narrow preview before any real implementation."
    normalized = _normalize(command)
    if "ilk" in normalized or "sec" in normalized or "uygulanacak" in normalized:
        suggested_next_step = "Preview recommendation: start with Ambient Workspace or Finality Sense because they are practical and low-risk."

    return {
        "raw_command": command,
        "matched_candidate": matched,
        "matched_category": matched.get("category") if matched else category,
        "candidate_summary": candidate_summary,
        "practical_value": matched.get("user_value") if matched else "Clarify the desired user value before ranking.",
        "required_layers": matched.get("required_existing_layers", []) if matched else [],
        "safety_boundary": matched.get("safety_boundary") if matched else "Preview only; no implementation or data access.",
        "candidate_ranking_preview": [
            {
                "id": item["id"],
                "name": item["name"],
                "category": item["category"],
                "risk_level": item["risk_level"],
                "reason": item["lux_identity_fit"],
            }
            for item in ranking
        ],
        "suggested_next_step": suggested_next_step,
        "input_context": {
            "user_goal": user_goal,
            "requested_risk_level": risk_level,
            "implementation_depth": implementation_depth or "registry_preview_only",
        },
        "real_action_enabled": False,
        "action_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_created": False,
        "export_performed": False,
        "device_control_performed": False,
        "read_only": True,
    }


def layer22_status_snapshot() -> Dict[str, Any]:
    return {
        "layer": "22",
        "name": "Future / Near-Future Premium Candidates registry",
        "status": "future_candidates_ready",
        "read_only": True,
        "candidate_count": len(FUTURE_CANDIDATES),
        "available_endpoints": [
            "GET /future/candidates",
            "POST /future/preview",
            "GET /debug/layer22-status",
        ],
        "candidate_names": [candidate["name"] for candidate in FUTURE_CANDIDATES],
        "safety_boundaries": {
            "real_action_enabled": False,
            "action_performed": False,
            "memory_read_performed": False,
            "memory_write_performed": False,
            "db_write_performed": False,
            "file_created": False,
            "export_performed": False,
            "device_control_performed": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
        "layer_approach": "Idea registry only; not a fixed roadmap and not a real feature implementation.",
        "next_recommended_step": "Layer 22.2 candidate ranking and feasibility preview",
        "backlog": ["stop/durdur final block leak"],
    }
