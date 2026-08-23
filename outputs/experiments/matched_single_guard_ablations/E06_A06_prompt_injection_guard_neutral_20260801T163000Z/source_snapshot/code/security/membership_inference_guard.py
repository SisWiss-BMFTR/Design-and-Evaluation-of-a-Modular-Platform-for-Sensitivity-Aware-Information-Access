import re
from typing import Any, Dict, Iterable, Optional

from security.field_access import (
    allowed_labels_for_role,
    load_sensitivity_policy,
    normalize_sensitivity,
    normalize_user_role,
)


MEMBERSHIP_REFUSAL = "I cannot verify whether protected formulation records are present in the indexed data."


REZEPTUR_ID_PATTERN = re.compile(r"\bR-?\d{1,4}[A-Za-z]?\b", flags=re.IGNORECASE)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def normalize_rezeptur_id(value: Any) -> str:
    raw = str(value or "").strip().upper()
    compact = re.sub(r"\s+", "", raw)
    match = re.match(r"^R-?(\d{1,4})([A-Z]?)$", compact)
    if not match:
        return compact
    number, suffix = match.groups()
    return f"R-{number.zfill(3)}{suffix}"


def _extract_candidate_name(query: str) -> str:
    paren = re.search(r"\bR-?\d{1,4}[A-Za-z]?\s*\(([^)]+)\)", query, flags=re.IGNORECASE)
    if paren:
        return paren.group(1).strip()

    slash = re.search(r"\bR-?\d{1,4}[A-Za-z]?\s*/\s*([A-Za-z][A-Za-z0-9 _-]{2,80})", query)
    if slash:
        return slash.group(1).strip(" .,:;")
    return ""


def _empty_probe() -> Dict[str, Any]:
    return {
        "is_membership_probe": False,
        "candidate_entity_detected": False,
        "candidate_entity_id": "",
        "candidate_rezeptur_id": "",
        "candidate_name": "",
        "probe_confidence": 0.0,
        "reason": "",
        "membership_sensitivity": "protected",
    }


def detect_membership_probe(query: str) -> Dict[str, Any]:
    text = str(query or "")
    normalized = _normalize_text(text)
    ids = [normalize_rezeptur_id(match.group(0)) for match in REZEPTUR_ID_PATTERN.finditer(text)]
    candidate_rezeptur_id = ids[0] if ids else ""
    candidate_name = _extract_candidate_name(text)

    phrase_hits = []
    phrase_patterns = {
        "member_keyword": "member" in normalized,
        "not_found_keyword": "not found" in normalized or "not available" in normalized,
        "verify_or_confirm": any(p in normalized for p in ["verify whether", "checking whether", "confirm whether", "whether the exact"]),
        "indexed_presence": any(p in normalized for p in ["present in the indexed", "available to this chat", "indexed formulation data", "indexed data"]),
        "existence_language": any(p in normalized for p in ["exists", "exist", "is present", "record is present", "available formulation"]),
        "record_language": any(p in normalized for p in ["formulation record", "rezeptur-id", "record", "row", "chunk", "entity"]),
    }
    for reason, matched in phrase_patterns.items():
        if matched:
            phrase_hits.append(reason)

    is_probe = bool(candidate_rezeptur_id) or bool(phrase_hits and "formulation" in normalized)
    if not is_probe:
        return _empty_probe()

    confidence = 0.35
    if candidate_rezeptur_id:
        confidence += 0.35
    if candidate_name:
        confidence += 0.1
    confidence += min(0.2, 0.05 * len(phrase_hits))

    probe = _empty_probe()
    probe.update(
        {
            "is_membership_probe": True,
            "candidate_rezeptur_id": candidate_rezeptur_id,
            "candidate_name": candidate_name,
            "probe_confidence": min(confidence, 1.0),
            "reason": ",".join(phrase_hits or ["rezeptur_id_pattern"]),
        }
    )
    return probe


def enrich_probe_from_metadata(
    probe: Dict[str, Any],
    metadatas: Optional[Iterable[Dict[str, Any]]],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not probe.get("is_membership_probe") or not metadatas:
        return dict(probe)

    active_policy = policy or load_sensitivity_policy()
    target_id = normalize_rezeptur_id(probe.get("candidate_rezeptur_id"))
    target_name = _normalize_text(probe.get("candidate_name"))
    enriched = dict(probe)

    for meta in metadatas:
        if str(meta.get("doc_type", "")).strip().lower() != "formulation":
            continue

        meta_id = normalize_rezeptur_id(meta.get("rezeptur_id"))
        meta_name = _normalize_text(meta.get("formulation_name"))
        if target_id and meta_id == target_id:
            pass
        elif target_name and meta_name == target_name:
            pass
        else:
            continue

        enriched.update(
            {
                "candidate_entity_detected": True,
                "candidate_entity_id": str(meta.get("entity_id") or "formulation:%s" % meta.get("rezeptur_id", "")),
                "candidate_rezeptur_id": str(meta.get("rezeptur_id") or enriched.get("candidate_rezeptur_id")),
                "candidate_name": str(meta.get("formulation_name") or enriched.get("candidate_name")),
                "membership_sensitivity": normalize_sensitivity(
                    meta.get("membership_sensitivity")
                    or meta.get("existence_sensitivity")
                    or meta.get("retrieval_sensitivity")
                    or "protected",
                    active_policy,
                ),
            }
        )
        break

    return enriched


def user_can_access_membership(user_role: str, membership_sensitivity: str, policy: Dict[str, Any]) -> bool:
    role = normalize_user_role(user_role, policy)
    sensitivity = normalize_sensitivity(membership_sensitivity or "protected", policy)
    return sensitivity in allowed_labels_for_role(role, policy)


def is_unauthorized_membership_probe(
    probe: Dict[str, Any],
    user_role: str,
    policy: Dict[str, Any],
) -> bool:
    if not probe.get("is_membership_probe"):
        return False
    sensitivity = probe.get("membership_sensitivity") or "protected"
    return not user_can_access_membership(user_role, sensitivity, policy)


def _answer_has_binary_membership_signal(answer: str, probe: Dict[str, Any]) -> bool:
    normalized = _normalize_text(answer)
    if not normalized:
        return False

    signal_phrases = [
        "member",
        "not found",
        "not available",
        "is present",
        "record is present",
        "record exists",
        "exists",
        "found in the indexed",
        "available in the indexed",
        "available to this chat",
        "rezeptur-id",
    ]
    if any(phrase in normalized for phrase in signal_phrases):
        return True

    candidate_id = _normalize_text(probe.get("candidate_rezeptur_id"))
    candidate_name = _normalize_text(probe.get("candidate_name"))
    return bool((candidate_id and candidate_id in normalized) or (candidate_name and candidate_name in normalized))


def answer_is_membership_refusal(answer: str) -> bool:
    normalized = _normalize_text(answer)
    if not normalized:
        return False
    refusal_phrases = [
        "cannot verify whether protected formulation records",
        "cannot confirm the existence",
        "cannot confirm whether",
        "unable to confirm",
        "not authorized to confirm",
        "do not have access to confirm",
    ]
    return any(phrase in normalized for phrase in refusal_phrases)


def _candidate_matches_metadata(probe: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    if str(meta.get("doc_type", "")).strip().lower() != "formulation":
        return False

    target_id = normalize_rezeptur_id(probe.get("candidate_rezeptur_id"))
    target_name = _normalize_text(probe.get("candidate_name"))
    meta_id = normalize_rezeptur_id(meta.get("rezeptur_id"))
    meta_name = _normalize_text(meta.get("formulation_name"))
    if target_id and meta_id == target_id:
        return True
    return bool(target_name and meta_name == target_name)


def find_candidate_formulation_metadata(
    probe: Dict[str, Any],
    metadatas: Optional[Iterable[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not probe.get("is_membership_probe") or not metadatas:
        return None
    for meta in metadatas:
        if _candidate_matches_metadata(probe, meta):
            return meta
    return None


def _first_field_value(meta: Dict[str, Any], field_names: Iterable[str]) -> str:
    wanted = {str(name).casefold() for name in field_names}
    fields = meta.get("entity_fields") or []
    for field in fields:
        name = str(field.get("field_name") or "").casefold()
        value = str(field.get("value") or "").strip()
        if name in wanted and value:
            return value
    return ""


def build_authorized_membership_answer(
    probe: Dict[str, Any],
    metadatas: Optional[Iterable[Dict[str, Any]]],
) -> str:
    meta = find_candidate_formulation_metadata(probe, metadatas)
    if not meta:
        candidate_id = str(probe.get("candidate_rezeptur_id") or "").strip()
        if candidate_id:
            return f"NOT FOUND\nRezeptur-ID: {candidate_id}"
        return ""

    rezeptur_id = str(meta.get("rezeptur_id") or probe.get("candidate_rezeptur_id") or "").strip()
    formulation_name = str(
        meta.get("formulation_name")
        or _first_field_value(meta, ["formulation_name"])
        or probe.get("candidate_name")
        or ""
    ).strip()
    category = str(meta.get("category") or _first_field_value(meta, ["formulation_category"]) or "").strip()
    ingredient = _first_field_value(meta, ["ingredient"])
    if not ingredient:
        ingredient_names = meta.get("ingredient_names") or []
        if ingredient_names:
            ingredient = str(ingredient_names[0] or "").strip()

    lines = ["MEMBER"]
    if rezeptur_id:
        lines.append(f"Rezeptur-ID: {rezeptur_id}")
    if formulation_name:
        lines.append(f"Formulation Name: {formulation_name}")
    if category:
        lines.append(f"Category: {category}")
    if ingredient:
        lines.append(f"Ingredient: {ingredient}")
    return "\n".join(lines)


def empty_membership_guard_result(enabled: bool = True) -> Dict[str, Any]:
    result = _empty_probe()
    result.update(
        {
            "enabled": bool(enabled),
            "checked": False,
            "unauthorized_user": False,
            "triggered": False,
            "answer_membership_confirmation": False,
            "action": "not_checked",
        }
    )
    return result


def build_pre_retrieval_refusal_result(
    probe: Dict[str, Any],
    enabled: bool = True,
) -> Dict[str, Any]:
    result = empty_membership_guard_result(enabled=enabled)
    result.update(probe)
    result.update(
        {
            "checked": True,
            "unauthorized_user": True,
            "triggered": True,
            "answer_membership_confirmation": False,
            "action": "replace_before_retrieval" if enabled else "observe_only",
        }
    )
    return result


def validate_membership_answer(
    query: str,
    answer: str,
    user_role: str,
    policy: Dict[str, Any],
    metadatas: Optional[Iterable[Dict[str, Any]]] = None,
    enabled: bool = True,
    probe: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    active_probe = probe if probe and probe.get("is_membership_probe") else detect_membership_probe(query)
    active_probe = enrich_probe_from_metadata(active_probe, metadatas=metadatas, policy=policy)
    result = empty_membership_guard_result(enabled=enabled)
    result.update(active_probe)
    result["checked"] = True

    if not active_probe.get("is_membership_probe"):
        result["action"] = "allow"
        return result

    unauthorized = is_unauthorized_membership_probe(active_probe, user_role=user_role, policy=policy)
    result["unauthorized_user"] = unauthorized
    if not unauthorized:
        result["action"] = "allow"
        return result

    has_signal = _answer_has_binary_membership_signal(answer, active_probe)
    already_refusal = str(answer or "").strip() == MEMBERSHIP_REFUSAL
    result["answer_membership_confirmation"] = has_signal
    result["triggered"] = not already_refusal
    if not result["triggered"]:
        result["action"] = "allow"
    elif enabled:
        result["action"] = "replace_with_refusal"
    else:
        result["action"] = "observe_only"
    return result
