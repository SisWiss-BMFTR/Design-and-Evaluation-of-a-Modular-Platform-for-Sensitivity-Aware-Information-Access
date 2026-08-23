from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Sequence


@dataclass(frozen=True)
class LeakageVerificationResult:
    leakage_detected: bool
    matched_fields: List[str]
    matched_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leakage_detected": self.leakage_detected,
            "matched_fields": list(self.matched_fields),
            "matched_count": self.matched_count,
        }


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _matchable_value(value: str) -> bool:
    text = _normalize_value(value)
    if not text or text.casefold() in {"n/a", "none", "nan", "unknown"}:
        return False
    return len(text) >= 3


_NUMERIC_VALUE_RE = re.compile(r"^[+-]?\d+(?:[.,]\d+)?\s*%?$")
_ANSWER_NUMBER_RE = re.compile(r"(?<![\d.,])[+-]?\d+(?:[.,]\d+)?\s*%?(?!\d|[.,]\d)")


def _numeric_value(value: str) -> Decimal | None:
    normalized = _normalize_value(value)
    if not _NUMERIC_VALUE_RE.fullmatch(normalized):
        return None
    normalized = normalized.rstrip().removesuffix("%").strip().replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _value_occurs_in_answer(answer: str, value: str) -> bool:
    normalized_answer = str(answer or "").casefold()
    normalized_value = _normalize_value(value).casefold()
    if not normalized_value:
        return False

    expected_number = _numeric_value(normalized_value)
    if expected_number is not None:
        return any(
            _numeric_value(match.group(0)) == expected_number
            for match in _ANSWER_NUMBER_RE.finditer(normalized_answer)
        )

    return normalized_value in normalized_answer


def _field_identity(field: Dict[str, Any]) -> tuple[str, str, str, str, str]:
    source = field.get("source") if isinstance(field.get("source"), dict) else {}
    return (
        str(field.get("field_name") or "").casefold(),
        str(field.get("entity_id") or "").casefold(),
        str(source.get("sheet") or field.get("source_sheet") or "").casefold(),
        str(source.get("row") or field.get("source_row") or "").casefold(),
        str(source.get("column") or field.get("source_column") or "").casefold(),
    )


def verify_answer_against_restricted_fields(
    answer: str,
    restricted_fields: Sequence[Dict[str, Any]],
    allowed_fields: Sequence[Dict[str, Any]] = (),
) -> LeakageVerificationResult:
    # Only exempt the same structured field if it appears in both inventories. A
    # coincidental value in an unrelated public field must not authorize disclosure
    # of a restricted field with that value.
    allowed_field_values = {
        (_field_identity(field), _normalize_value(field.get("value")).casefold())
        for field in allowed_fields
        if _matchable_value(_normalize_value(field.get("value")))
    }

    matched_fields: List[str] = []
    seen_fields = set()
    matched_count = 0

    for field in restricted_fields:
        value = _normalize_value(field.get("value"))
        if not _matchable_value(value):
            continue
        if (_field_identity(field), value.casefold()) in allowed_field_values:
            continue
        if not _value_occurs_in_answer(answer, value):
            continue

        matched_count += 1
        field_name = str(field.get("field_name") or "unknown")
        if field_name not in seen_fields:
            matched_fields.append(field_name)
            seen_fields.add(field_name)

    return LeakageVerificationResult(
        leakage_detected=matched_count > 0,
        matched_fields=matched_fields,
        matched_count=matched_count,
    )
