from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import load_json, save_json


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _lc(value: Any) -> str:
    return _norm_text(value).lower()


def _topic_alias(topic: str) -> str:
    t = _lc(topic)
    if not t:
        return "general"
    if t in {"technical", "tech", "technical_guidance"}:
        return "technical_guidance"
    if t in {"confusion", "confusion_reduction"}:
        return "confusion_reduction"
    if t in {"repair", "trust_repair", "repair_quality"}:
        return "trust_repair"
    if t in {"safety", "safety_ethics"}:
        return "safety_ethics"
    if t in {"emotional", "emotional_support"}:
        return "emotional_support"
    if t in {"task", "task_success"}:
        return "task_success"
    return t


def _policy_entry(
    *,
    topic: str,
    rule: str,
    behavior: str | None = None,
    confidence: float = 0.75,
    source: str = "system",
    entry_id: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    r = _norm_text(rule)
    b = _norm_text(behavior) or r
    return {
        "id": _norm_text(entry_id) or f"pol_{uuid.uuid4().hex[:10]}",
        "topic": _topic_alias(topic),
        "rule": r,
        "behavior": b,
        "confidence": round(clamp(confidence), 4),
        "source": _norm_text(source) or "system",
        "updated_at": _norm_text(updated_at) or now_iso(),
    }


@dataclass
class BehaviorPolicyManager:
    base_dir: Path

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def users_dir(self) -> Path:
        return self.data_dir / "users"

    @property
    def global_dir(self) -> Path:
        return self.data_dir / "global"

    def user_policy_path(self, user_id: str) -> Path:
        return self.users_dir / user_id / "behavior_policy.json"

    def global_policy_path(self) -> Path:
        return self.global_dir / "global_behavior_policy.json"

    def default_user_policy(self) -> dict[str, Any]:
        rules = [
            "Kullanıcı adım adım isterse tek adım ver.",
            "Kullanıcı karışıksa kısa ve sade anlat.",
            "Güvenlik sinyali varsa sakin, net ve güvenli dil kullan.",
        ]
        return {
            "version": 2,
            "rules": rules,
            "style": {
                "tone": "warm_clear",
                "density": "adaptive",
                "pace": "adaptive",
            },
            "policies": [
                _policy_entry(
                    topic="confusion_reduction",
                    rule="Kullanıcı karıştığında tek adım ve sade açıklama kullan.",
                    behavior="Önce tek adım ver, sonra kullanıcı onayı bekle.",
                    confidence=0.86,
                    source="default_user",
                ),
                _policy_entry(
                    topic="technical_guidance",
                    rule="Teknik akışta önce doğrulama sorusu sor.",
                    behavior="Bir kontrol adımı ver ve çıktıyı kullanıcıdan doğrula.",
                    confidence=0.84,
                    source="default_user",
                ),
                _policy_entry(
                    topic="safety_ethics",
                    rule="Riskli durumda güvenlik ve sakinlik öncelikli olmalı.",
                    behavior="Klinik/tıbbi/dini kesinlikten kaçın; güvenli ve sakin dil kullan.",
                    confidence=0.9,
                    source="default_user",
                ),
            ],
        }

    def default_global_policy(self) -> dict[str, Any]:
        rules = [
            "Teknik rehberlikte önce doğrulama adımı ver.",
            "Uzun yanıt yerine uygun durumda kısa ve uygulanabilir adım öner.",
            "Kriz/risk sinyallerinde güvenlik ve sakinlik önceliklidir.",
        ]
        return {
            "version": 2,
            "rules": rules,
            "style": {
                "tone": "human_like",
                "density": "adaptive",
                "pace": "calm",
            },
            "policies": [
                _policy_entry(
                    topic="technical_guidance",
                    rule="Teknik kurulumlarda önce mevcut ekran durumunu doğrulatmak başarıyı artırır.",
                    behavior="İlk adım doğrulama + tek işlem + sonuç geri bildirimi iste.",
                    confidence=0.88,
                    source="default_global",
                ),
                _policy_entry(
                    topic="confusion_reduction",
                    rule="Karmaşa yükseldiğinde açıklama yoğunluğunu azaltmak gerekir.",
                    behavior="Kısa yanıt + tek net eylem ver.",
                    confidence=0.86,
                    source="default_global",
                ),
                _policy_entry(
                    topic="safety_ethics",
                    rule="Güvenlik çerçevesi her zaman önceliklidir.",
                    behavior="Tanı, ilaç, tedavi, dini hüküm ve manipülatif dilden kaçın.",
                    confidence=0.93,
                    source="default_global",
                ),
            ],
        }

    def _normalize_policy_doc(self, doc: dict[str, Any] | None, *, scope: str) -> dict[str, Any]:
        base = self.default_user_policy() if scope == "user" else self.default_global_policy()
        raw = doc if isinstance(doc, dict) else {}

        rules_raw = raw.get("rules", base.get("rules", []))
        rules = []
        if isinstance(rules_raw, list):
            for r in rules_raw:
                txt = _norm_text(r)
                if txt:
                    rules.append(txt)
        if not rules:
            rules = list(base.get("rules", []))

        style_raw = raw.get("style", base.get("style", {}))
        style = dict(style_raw) if isinstance(style_raw, dict) else dict(base.get("style", {}))

        policies_raw = raw.get("policies")
        policies: list[dict[str, Any]] = []
        if isinstance(policies_raw, list):
            for p in policies_raw:
                if not isinstance(p, dict):
                    continue
                entry = _policy_entry(
                    topic=str(p.get("topic", "general")),
                    rule=str(p.get("rule", p.get("behavior", ""))),
                    behavior=str(p.get("behavior", p.get("rule", ""))),
                    confidence=safe_float(p.get("confidence", 0.75), 0.75),
                    source=str(p.get("source", scope)),
                    entry_id=str(p.get("id", "")),
                    updated_at=str(p.get("updated_at", "")),
                )
                if entry["rule"] and entry["behavior"]:
                    policies.append(entry)

        if not policies:
            # Backfill from simple rule list
            for rule in rules:
                inferred_topic = "confusion_reduction" if "adım" in _lc(rule) or "karış" in _lc(rule) else "general"
                policies.append(
                    _policy_entry(
                        topic=inferred_topic,
                        rule=rule,
                        behavior=rule,
                        confidence=0.72,
                        source=f"{scope}_legacy_rules",
                    )
                )

        # Merge and dedupe policies by topic+behavior
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for p in policies:
            key = (_topic_alias(p.get("topic", "general")), _lc(p.get("behavior", "")))
            if key not in merged:
                merged[key] = p
                continue
            old = merged[key]
            # keep stronger confidence and latest update marker
            old["confidence"] = round(max(safe_float(old.get("confidence"), 0.0), safe_float(p.get("confidence"), 0.0)), 4)
            if _norm_text(p.get("rule")) and len(_norm_text(p.get("rule"))) > len(_norm_text(old.get("rule"))):
                old["rule"] = _norm_text(p.get("rule"))
            old["updated_at"] = _norm_text(p.get("updated_at")) or old.get("updated_at") or now_iso()
            merged[key] = old

        normalized_policies = sorted(
            merged.values(),
            key=lambda x: (safe_float(x.get("confidence"), 0.0), _norm_text(x.get("updated_at"))),
            reverse=True,
        )

        # Keep compatibility: rules should include top behaviors
        merged_rules: list[str] = []
        for p in normalized_policies:
            b = _norm_text(p.get("behavior"))
            if b and b not in merged_rules:
                merged_rules.append(b)
        for r in rules:
            if r not in merged_rules:
                merged_rules.append(r)

        return {
            "version": 2,
            "rules": merged_rules[:80],
            "style": style,
            "policies": normalized_policies[:120],
            "updated_at": _norm_text(raw.get("updated_at")) or now_iso(),
        }

    def load_user_policy(self, user_id: str) -> dict[str, Any]:
        doc = load_json(self.user_policy_path(user_id), self.default_user_policy())
        normalized = self._normalize_policy_doc(doc, scope="user")
        return normalized

    def load_global_policy(self) -> dict[str, Any]:
        doc = load_json(self.global_policy_path(), self.default_global_policy())
        normalized = self._normalize_policy_doc(doc, scope="global")
        return normalized

    def save_user_policy(self, user_id: str, policy: dict[str, Any]) -> None:
        normalized = self._normalize_policy_doc(policy, scope="user")
        save_json(self.user_policy_path(user_id), normalized)

    def save_global_policy(self, policy: dict[str, Any]) -> None:
        normalized = self._normalize_policy_doc(policy, scope="global")
        save_json(self.global_policy_path(), normalized)

    def merge_policy(self, existing_policy: dict[str, Any], new_policy: dict[str, Any]) -> dict[str, Any]:
        doc = self._normalize_policy_doc(existing_policy, scope="user")
        topic = _topic_alias(str(new_policy.get("topic", "general")))
        rule = _norm_text(new_policy.get("rule")) or _norm_text(new_policy.get("behavior"))
        behavior = _norm_text(new_policy.get("behavior")) or rule
        if not rule or not behavior:
            return doc

        incoming = _policy_entry(
            topic=topic,
            rule=rule,
            behavior=behavior,
            confidence=safe_float(new_policy.get("confidence", 0.78), 0.78),
            source=str(new_policy.get("source", "learning_signal")),
            entry_id=str(new_policy.get("id", "")),
            updated_at=str(new_policy.get("updated_at", "")),
        )
        merged = False
        policies = list(doc.get("policies", []))
        for idx, pol in enumerate(policies):
            if not isinstance(pol, dict):
                continue
            same_topic = _topic_alias(pol.get("topic", "general")) == incoming["topic"]
            same_behavior = _lc(pol.get("behavior", "")) == _lc(incoming["behavior"])
            if same_topic and same_behavior:
                old_conf = safe_float(pol.get("confidence"), 0.7)
                new_conf = clamp((old_conf * 0.6) + (safe_float(incoming.get("confidence"), 0.7) * 0.4))
                pol["confidence"] = round(new_conf, 4)
                pol["rule"] = incoming["rule"] if len(incoming["rule"]) > len(_norm_text(pol.get("rule"))) else _norm_text(pol.get("rule"))
                pol["updated_at"] = now_iso()
                pol["source"] = incoming["source"]
                policies[idx] = pol
                merged = True
                break
        if not merged:
            policies.append(incoming)

        doc["policies"] = policies
        return self._normalize_policy_doc(doc, scope="user")

    def update_policy_from_learning_signal(self, user_id: str, learning_signal: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(learning_signal, dict):
            return self.load_user_policy(user_id)

        user_doc = self.load_user_policy(user_id)
        global_doc = self.load_global_policy()

        topics = learning_signal.get("topics", [])
        if not isinstance(topics, list):
            topics = []
        topics = [_topic_alias(str(t)) for t in topics if _norm_text(t)]

        score = safe_float(learning_signal.get("score", 0.0), 0.0)
        quality_label = _lc(learning_signal.get("quality_label", "candidate"))
        base_conf = clamp(0.62 + score * 0.35)
        if quality_label == "elite":
            base_conf = clamp(base_conf + 0.08)
        elif quality_label == "premium":
            base_conf = clamp(base_conf + 0.04)

        behavior_update = _norm_text(learning_signal.get("behavior_update"))
        personal_update = _norm_text(learning_signal.get("personal_update"))
        global_update = _norm_text(learning_signal.get("global_update"))

        # update user policies
        for topic in (topics[:3] or ["general"]):
            if behavior_update:
                user_doc = self.merge_policy(
                    user_doc,
                    {
                        "topic": topic,
                        "rule": behavior_update,
                        "behavior": behavior_update,
                        "confidence": base_conf,
                        "source": "learning_signal",
                    },
                )
            if personal_update:
                user_doc = self.merge_policy(
                    user_doc,
                    {
                        "topic": topic,
                        "rule": personal_update,
                        "behavior": personal_update,
                        "confidence": clamp(base_conf - 0.02),
                        "source": "learning_signal_personal",
                    },
                )
        self.save_user_policy(user_id, user_doc)

        # optional global policy update (anonymous behavior only)
        if global_update:
            global_topic = topics[0] if topics else "general"
            g_new = _policy_entry(
                topic=global_topic,
                rule=global_update,
                behavior=global_update,
                confidence=clamp(base_conf - 0.03),
                source="learning_signal_global",
            )
            gdoc = self._normalize_policy_doc(global_doc, scope="global")
            gdoc["policies"] = list(gdoc.get("policies", [])) + [g_new]
            self.save_global_policy(gdoc)

        return user_doc

    def _score_policy(
        self,
        policy: dict[str, Any],
        *,
        topics: list[str],
        micro_signals: dict[str, Any] | None,
        response_needs: dict[str, Any] | None,
    ) -> float:
        topic = _topic_alias(policy.get("topic", "general"))
        behavior = _lc(policy.get("behavior", ""))
        confidence = safe_float(policy.get("confidence", 0.7), 0.7)
        score = confidence * 0.62

        if topic in topics:
            score += 0.28
        elif topic == "general":
            score += 0.06

        micro = micro_signals or {}
        confusion = safe_float(micro.get("confusion_level", 0.0), 0.0)
        patience = safe_float(micro.get("patience_level", 1.0), 1.0)
        trust = safe_float(micro.get("trust_shift", 0.5), 0.5)
        urgency = safe_float(micro.get("urgency_level", 0.0), 0.0)

        if confusion >= 0.35 and any(x in behavior for x in ("tek adim", "kisa", "sade")):
            score += 0.14
        if patience <= 0.55 and any(x in behavior for x in ("tek adim", "kisa", "sade")):
            score += 0.12
        if trust < 0.45 and any(x in behavior for x in ("repair", "haklisin", "sakin")):
            score += 0.12
        if urgency >= 0.45 and any(x in behavior for x in ("net", "dogrula", "adim")):
            score += 0.08

        rn = response_needs or {}
        if bool(rn.get("should_repair_first")) and any(x in behavior for x in ("repair", "haklisin")):
            score += 0.1
        if bool(rn.get("should_use_one_step")) and any(x in behavior for x in ("tek adim", "adim")):
            score += 0.1
        if bool(rn.get("should_slow_down")) and any(x in behavior for x in ("yavas", "sakin", "kisa")):
            score += 0.07

        # safety always gets a lift
        if topic == "safety_ethics":
            score += 0.09

        return clamp(score)

    def get_relevant_policies(
        self,
        user_id: str,
        topics: list[str] | None = None,
        micro_signals: dict[str, Any] | None = None,
        response_needs: dict[str, Any] | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        topics = [_topic_alias(str(t)) for t in (topics or []) if _norm_text(t)]

        user_policy = self.load_user_policy(user_id)
        global_policy = self.load_global_policy()

        candidates: list[dict[str, Any]] = []
        for source_label, doc in (("user", user_policy), ("global", global_policy)):
            for p in doc.get("policies", []):
                if not isinstance(p, dict):
                    continue
                conf = safe_float(p.get("confidence", 0.0), 0.0)
                if conf < 0.55:
                    continue
                score = self._score_policy(
                    p,
                    topics=topics,
                    micro_signals=micro_signals,
                    response_needs=response_needs,
                )
                enriched = dict(p)
                enriched["scope"] = source_label
                enriched["relevance"] = round(score, 4)
                candidates.append(enriched)

        candidates.sort(key=lambda x: (safe_float(x.get("relevance"), 0.0), safe_float(x.get("confidence"), 0.0)), reverse=True)

        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in candidates:
            key = (_topic_alias(item.get("topic", "general")), _lc(item.get("behavior", "")))
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)
            if len(selected) >= max(1, min(limit, 20)):
                break

        # Keep personal/global balance in prompt context when possible.
        has_user = any(x.get("scope") == "user" for x in selected)
        has_global = any(x.get("scope") == "global" for x in selected)
        if not has_global:
            for item in candidates:
                if item.get("scope") == "global":
                    selected.append(item)
                    break
        if not has_user:
            for item in candidates:
                if item.get("scope") == "user":
                    selected.append(item)
                    break
        selected = sorted(
            selected,
            key=lambda x: (safe_float(x.get("relevance"), 0.0), safe_float(x.get("confidence"), 0.0)),
            reverse=True,
        )[: max(1, min(limit, 20))]

        # After trimming, ensure at least one global + one user when possible.
        if selected:
            has_user_trim = any(x.get("scope") == "user" for x in selected)
            has_global_trim = any(x.get("scope") == "global" for x in selected)
            if not has_global_trim:
                for item in candidates:
                    if item.get("scope") == "global":
                        if len(selected) >= max(1, min(limit, 20)):
                            selected[-1] = item
                        else:
                            selected.append(item)
                        break
            if not has_user_trim:
                for item in candidates:
                    if item.get("scope") == "user":
                        if len(selected) >= max(1, min(limit, 20)):
                            selected[-1] = item
                        else:
                            selected.append(item)
                        break

        selected_user = [x for x in selected if x.get("scope") == "user"]
        selected_global = [x for x in selected if x.get("scope") == "global"]

        return {
            "selected": selected,
            "selected_user": selected_user,
            "selected_global": selected_global,
            "user_style": dict(user_policy.get("style", {})),
            "global_style": dict(global_policy.get("style", {})),
            "topics": topics,
        }

    def build_policy_context(
        self,
        user_id: str,
        topics: list[str] | None = None,
        micro_signals: dict[str, Any] | None = None,
        response_needs: dict[str, Any] | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        relevant = self.get_relevant_policies(
            user_id,
            topics=topics,
            micro_signals=micro_signals,
            response_needs=response_needs,
            limit=limit,
        )
        selected = relevant.get("selected", [])
        user_rules = [_norm_text(x.get("behavior", "")) for x in relevant.get("selected_user", []) if _norm_text(x.get("behavior", ""))]
        global_rules = [_norm_text(x.get("behavior", "")) for x in relevant.get("selected_global", []) if _norm_text(x.get("behavior", ""))]
        return {
            "user_rules": user_rules,
            "global_rules": global_rules,
            "selected_policies": selected,
            "user_style": relevant.get("user_style", {}),
            "global_style": relevant.get("global_style", {}),
            "topics": relevant.get("topics", []),
        }
