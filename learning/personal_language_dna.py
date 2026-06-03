from __future__ import annotations

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


def fold_tr_ascii(text: str) -> str:
    mapping = str.maketrans(
        {
            "c": "c",
            "C": "c",
            "g": "g",
            "G": "g",
            "i": "i",
            "I": "i",
            "o": "o",
            "O": "o",
            "s": "s",
            "S": "s",
            "u": "u",
            "U": "u",
            "ç": "c",
            "Ç": "c",
            "ğ": "g",
            "Ğ": "g",
            "ı": "i",
            "İ": "i",
            "ö": "o",
            "Ö": "o",
            "ş": "s",
            "Ş": "s",
            "ü": "u",
            "Ü": "u",
        }
    )
    out = (text or "").translate(mapping)
    # mojibake fallbacks
    out = (
        out.replace("Ã§", "c")
        .replace("Ã‡", "c")
        .replace("ÄŸ", "g")
        .replace("Ä", "g")
        .replace("Ä±", "i")
        .replace("Ä°", "i")
        .replace("Ã¶", "o")
        .replace("Ã–", "o")
        .replace("ÅŸ", "s")
        .replace("Å", "s")
        .replace("Ã¼", "u")
        .replace("Ãœ", "u")
    )
    return out.lower()


TERM_LIBRARY: dict[str, dict[str, Any]] = {
    "premium": {
        "patterns": ("premium", "en premium", "high-end", "ust seviye", "en ust seviye"),
        "meaning": "en ust seviye, profesyonel, derin, uygulanabilir, vizyoner",
        "preferred_response": "once vizyon, sonra mimari, sonra uygulanabilir adim",
        "response_adjustment": {
            "depth": "deep",
            "structure": "vision_then_architecture_then_steps",
            "pace": "controlled",
        },
        "base_confidence": 0.78,
    },
    "adim_adim": {
        "patterns": ("adim adim", "tek tek", "tek adim", "yavas git", "yavasca"),
        "meaning": "tek islem, onay almadan sonraki adıma gecme",
        "preferred_response": "kisa, tek gorevli, kontrollu ilerleme",
        "response_adjustment": {
            "depth": "short",
            "structure": "single_step",
            "pace": "slow",
            "use_one_step": True,
        },
        "base_confidence": 0.82,
    },
    "sinirlari_zorla": {
        "patterns": ("sinirlari zorla", "sinirlari zorlayalim", "daha iddiali", "daha vizyoner"),
        "meaning": "normal cevabin otesinde stratejik ve yaratici derinlik",
        "preferred_response": "derin mimari + yaratici strateji + uygulanabilir plan",
        "response_adjustment": {
            "depth": "deep",
            "structure": "strategy_then_execution",
            "pace": "controlled",
        },
        "base_confidence": 0.74,
    },
    "karistirdin": {
        "patterns": ("karistirdin", "cok karisti", "anlamadim", "karmasik oldu", "fazla hizli"),
        "meaning": "cevap yogunlugu fazla geldi, sade yeniden kurulum gerekiyor",
        "preferred_response": "repair_first + one_step + kisa aciklama",
        "response_adjustment": {
            "depth": "short",
            "structure": "repair_then_single_step",
            "pace": "slow",
            "repair_first": True,
            "use_one_step": True,
        },
        "base_confidence": 0.8,
    },
}


@dataclass
class PersonalLanguageDNAEngine:
    base_dir: Path

    @property
    def users_dir(self) -> Path:
        return self.base_dir / "data" / "users"

    def _path(self, user_id: str) -> Path:
        return self.users_dir / user_id / "personal_language_dna.json"

    def ensure_file(self, user_id: str) -> None:
        path = self._path(user_id)
        if path.exists():
            return
        save_json(
            path,
            {
                "terms": {},
                "temporary_signals": [],
                "updated_at": now_iso(),
            },
        )

    def get_language_dna(self, user_id: str) -> dict[str, Any]:
        self.ensure_file(user_id)
        data = load_json(self._path(user_id), {"terms": {}, "temporary_signals": []})
        if not isinstance(data, dict):
            data = {"terms": {}, "temporary_signals": []}
        if not isinstance(data.get("terms"), dict):
            data["terms"] = {}
        if not isinstance(data.get("temporary_signals"), list):
            data["temporary_signals"] = []
        data.setdefault("updated_at", now_iso())
        return data

    def _detect_terms(self, message: str) -> list[dict[str, Any]]:
        text = fold_tr_ascii(message)
        out: list[dict[str, Any]] = []
        for term_key, rule in TERM_LIBRARY.items():
            patterns = tuple(str(x) for x in rule.get("patterns", ()))
            hit_count = sum(1 for p in patterns if p and p in text)
            if hit_count <= 0:
                continue
            base_conf = safe_float(rule.get("base_confidence", 0.72), 0.72)
            confidence = clamp(base_conf + min(0.18, hit_count * 0.06))
            out.append(
                {
                    "term": term_key,
                    "meaning": str(rule.get("meaning", "")),
                    "preferred_response": str(rule.get("preferred_response", "")),
                    "response_adjustment": dict(rule.get("response_adjustment", {})),
                    "confidence": round(confidence, 4),
                    "detected_at": now_iso(),
                }
            )
        return out

    def analyze_language_dna(
        self,
        user_id: str,
        message: str,
        response: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = response, context
        dna = self.get_language_dna(user_id)
        detected = self._detect_terms(message)
        terms = dna.get("terms", {}) if isinstance(dna.get("terms"), dict) else {}
        msg = fold_tr_ascii(message)

        hints: list[str] = []
        seen_hint: set[str] = set()
        for row in detected:
            term = str(row.get("term", "")).strip()
            meaning = str(row.get("meaning", "")).strip()
            if not term or not meaning:
                continue
            hint = f'"{term}" = {meaning}.'
            if hint not in seen_hint:
                seen_hint.add(hint)
                hints.append(hint)

        # Stable historical hints (do not flood prompt)
        ranked_history: list[tuple[float, str, dict[str, Any]]] = []
        for term, row in terms.items():
            if not isinstance(row, dict):
                continue
            stable = bool(row.get("stable"))
            conf = safe_float(row.get("confidence", 0.0), 0.0)
            seen_count = int(row.get("seen_count", 0))
            if not stable and not (conf >= 0.78 and seen_count >= 2):
                continue
            score = conf + min(0.1, seen_count * 0.01)
            ranked_history.append((score, term, row))
        ranked_history.sort(key=lambda x: x[0], reverse=True)

        for _, term, row in ranked_history[:5]:
            patterns = TERM_LIBRARY.get(term, {}).get("patterns", ())
            if patterns and not any(str(p) in msg for p in patterns):
                # keep only if high confidence even without explicit term in this message
                if safe_float(row.get("confidence"), 0.0) < 0.9:
                    continue
            meaning = str(row.get("meaning", "")).strip()
            if not meaning:
                continue
            hint = f'"{term}" = {meaning}.'
            if hint not in seen_hint:
                seen_hint.add(hint)
                hints.append(hint)

        response_adjustment: dict[str, Any] = {
            "depth": "adaptive",
            "structure": "adaptive",
            "pace": "adaptive",
        }
        for row in detected:
            adj = row.get("response_adjustment", {})
            if isinstance(adj, dict):
                for k, v in adj.items():
                    response_adjustment[k] = v

        return {
            "detected_terms": [str(x.get("term", "")) for x in detected if str(x.get("term", "")).strip()],
            "term_signals": detected,
            "language_hints": hints[:5],
            "response_adjustment": response_adjustment,
            "updated_at": now_iso(),
        }

    def update_language_dna(self, user_id: str, signals: dict[str, Any]) -> dict[str, Any]:
        dna = self.get_language_dna(user_id)
        terms = dna.setdefault("terms", {})
        term_signals = signals.get("term_signals", []) if isinstance(signals, dict) else []
        if not isinstance(term_signals, list):
            term_signals = []

        # Always keep raw detections in temporary memory first.
        temp = dna.setdefault("temporary_signals", [])
        if not isinstance(temp, list):
            temp = []
            dna["temporary_signals"] = temp
        for sig in term_signals[-12:]:
            if not isinstance(sig, dict):
                continue
            temp.append(
                {
                    "term": str(sig.get("term", "")),
                    "confidence": round(safe_float(sig.get("confidence", 0.0), 0.0), 4),
                    "detected_at": str(sig.get("detected_at", now_iso())),
                }
            )
        if len(temp) > 80:
            dna["temporary_signals"] = temp[-80:]
            temp = dna["temporary_signals"]

        for sig in term_signals:
            if not isinstance(sig, dict):
                continue
            term = str(sig.get("term", "")).strip()
            if not term:
                continue

            # Count recent temporary evidence for this term.
            term_recent = [
                t
                for t in temp[-40:]
                if isinstance(t, dict) and str(t.get("term", "")).strip() == term
            ]
            recent_hits = len(term_recent)
            recent_avg_conf = (
                sum(safe_float(t.get("confidence", 0.0), 0.0) for t in term_recent) / max(1, recent_hits)
            )

            old = terms.get(term, {}) if isinstance(terms.get(term), dict) else {}
            had_old = bool(old)
            old_conf = safe_float(old.get("confidence", 0.0), 0.0)
            incoming_conf = safe_float(sig.get("confidence", 0.0), 0.0)

            # Promotion policy:
            # - Existing term: update normally
            # - New term: do NOT persist unless confidence is high OR repeated evidence exists
            promote_new = incoming_conf >= 0.82 or (recent_hits >= 2 and recent_avg_conf >= 0.68)
            if not had_old and not promote_new:
                continue

            if had_old:
                seen_count = int(old.get("seen_count", 0)) + 1
            else:
                # Newly promoted: derive seen_count from temporary evidence.
                seen_count = max(1, recent_hits)

            new_conf = clamp((old_conf * 0.7) + (incoming_conf * 0.3)) if old_conf > 0 else clamp(
                max(incoming_conf, recent_avg_conf)
            )
            stable = bool(old.get("stable")) or (seen_count >= 2 and new_conf >= 0.68)

            terms[term] = {
                "meaning": str(sig.get("meaning", old.get("meaning", ""))),
                "preferred_response": str(sig.get("preferred_response", old.get("preferred_response", ""))),
                "response_adjustment": dict(sig.get("response_adjustment", old.get("response_adjustment", {}))),
                "confidence": round(new_conf, 4),
                "seen_count": seen_count,
                "stable": stable,
                "last_seen_at": now_iso(),
            }

        dna["updated_at"] = now_iso()
        save_json(self._path(user_id), dna)
        return dna

    def get_relevant_language_hints(self, user_id: str, message: str, limit: int = 5) -> list[str]:
        dna = self.get_language_dna(user_id)
        terms = dna.get("terms", {}) if isinstance(dna.get("terms"), dict) else {}
        msg = fold_tr_ascii(message)
        ranked: list[tuple[float, str]] = []
        for term, row in terms.items():
            if not isinstance(row, dict):
                continue
            conf = safe_float(row.get("confidence", 0.0), 0.0)
            stable = bool(row.get("stable"))
            seen_count = int(row.get("seen_count", 0))
            if not stable and conf < 0.82:
                continue
            match_boost = 0.0
            patterns = TERM_LIBRARY.get(term, {}).get("patterns", ())
            if any(str(p) in msg for p in patterns):
                match_boost = 0.2
            score = conf + min(0.1, seen_count * 0.01) + match_boost
            meaning = str(row.get("meaning", "")).strip()
            if not meaning:
                continue
            ranked.append((score, f'"{term}" = {meaning}.'))
        ranked.sort(key=lambda x: x[0], reverse=True)
        hints: list[str] = []
        seen_hint: set[str] = set()
        for _, hint in ranked:
            if hint in seen_hint:
                continue
            seen_hint.add(hint)
            hints.append(hint)
            if len(hints) >= max(1, min(limit, 10)):
                break
        return hints

    def build_language_context(self, user_id: str, message: str) -> dict[str, Any]:
        analysis = self.analyze_language_dna(user_id=user_id, message=message)
        hints = self.get_relevant_language_hints(user_id=user_id, message=message, limit=5)
        merged_hints = list(dict.fromkeys((analysis.get("language_hints") or []) + hints))
        return {
            "detected_terms": analysis.get("detected_terms", []),
            "language_hints": merged_hints[:5],
            "response_adjustment": analysis.get("response_adjustment", {}),
        }
