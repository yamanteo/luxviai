from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .group3_signals import MemoryWriteCandidate
from .memory_layer import MemoryLayerEngine


def _candidate(
    *,
    should_write: bool,
    confidence: float,
    reason_bucket: str,
    sensitivity: str = "low",
    evidence_count: int = 3,
    requires_repeat_evidence: bool = False,
    safe_summary: str = "",
    risk_flags: list[str] | None = None,
) -> MemoryWriteCandidate:
    return MemoryWriteCandidate(
        should_write=should_write,
        confidence=confidence,
        reason_bucket=reason_bucket,
        sensitivity=sensitivity,
        evidence_count=evidence_count,
        requires_repeat_evidence=requires_repeat_evidence,
        safe_summary=safe_summary or "group3_safe_candidate",
        risk_flags=list(risk_flags or []),
    )


def run_memory_gate_regression(base_dir: Path, *, user_id: str = "debug_group3_regression") -> dict[str, Any]:
    """
    Internal regression helper for Group-3 memory gate.
    No global/fine-tune write operations are performed in this helper.
    """
    engine = MemoryLayerEngine()
    results: dict[str, Any] = {}

    low_conf = _candidate(
        should_write=True,
        confidence=0.41,
        reason_bucket="emerging_pattern",
        safe_summary="Tek seferlik düşük güvenli sinyal",
    )
    results["low_confidence_block"] = engine.evaluate_memory_write_candidate("bugün biraz garip hissettim", low_conf)

    crisis = _candidate(
        should_write=True,
        confidence=0.95,
        reason_bucket="repeating_pattern",
        sensitivity="high",
        risk_flags=["crisis_risk"],
        safe_summary="kriz ifadesi",
    )
    results["crisis_block"] = engine.evaluate_memory_write_candidate("şu an kendime zarar vereceğim", crisis)

    pii = _candidate(
        should_write=True,
        confidence=0.93,
        reason_bucket="repeating_pattern",
        safe_summary="Telefon numarası 0532 111 22 33",
    )
    results["pii_block"] = engine.evaluate_memory_write_candidate("telefonum 0532 111 22 33", pii)

    safe_pref = _candidate(
        should_write=True,
        confidence=0.92,
        reason_bucket="repeating_pattern",
        safe_summary="Kullanıcı kısa ve adım adım anlatımı tercih ediyor olabilir.",
    )
    safe_pref_gate = engine.evaluate_memory_write_candidate("kısa ve adım adım anlatınca anlıyorum", safe_pref)
    results["safe_repeated_preference"] = safe_pref_gate
    if bool(safe_pref_gate.get("allow_write")):
        anchor = engine.build_safe_memory_anchor(candidate=safe_pref, gate=safe_pref_gate)
        first = engine.persist_memory_anchor(base_dir=base_dir, user_id=user_id, anchor=anchor)
        second = engine.persist_memory_anchor(base_dir=base_dir, user_id=user_id, anchor=anchor)
        results["duplicate_anchor_check"] = {"first": first, "second": second}
    else:
        results["duplicate_anchor_check"] = {"first": {"written": False}, "second": {"written": False}}

    safe_symbolic = _candidate(
        should_write=True,
        confidence=0.89,
        reason_bucket="repeating_pattern",
        safe_summary="Tekrarlayan eşik/kapı imgesi olabilir.",
    )
    results["safe_repeated_symbolic"] = engine.evaluate_memory_write_candidate("yine kapı ve eşik gördüm", safe_symbolic)

    # Stable compact pass/fail map for quick smoke checks.
    verdict = {
        "low_confidence_block_ok": not bool(results["low_confidence_block"].get("allow_write")),
        "crisis_block_ok": not bool(results["crisis_block"].get("allow_write")),
        "pii_block_ok": not bool(results["pii_block"].get("allow_write")),
        "safe_pref_allowed": bool(results["safe_repeated_preference"].get("allow_write")),
        "safe_symbolic_allowed": bool(results["safe_repeated_symbolic"].get("allow_write")),
        "duplicate_block_ok": str((results["duplicate_anchor_check"]["second"] or {}).get("reason", "")) == "duplicate_anchor",
    }
    return {
        "verdict": verdict,
        "results": results,
        "user_id": user_id,
    }

