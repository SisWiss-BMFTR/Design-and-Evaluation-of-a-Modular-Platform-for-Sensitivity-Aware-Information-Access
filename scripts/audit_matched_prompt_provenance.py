#!/usr/bin/env python3
"""Create additive prompt provenance for matched A03/A05 result records.

The audit never modifies experiment outputs. It hashes the preserved record-level
prompt sequences and verifies equality between the guard-off and guard-on arms.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ATTACK_LABELS = {
    "A03": ("access-level downgrade attack", "access level downgrade attack"),
    "A05": ("rank-probing membership inference attack", "membership inference attack"),
}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_records(arm_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(arm_root.glob("**/results.json")):
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        records.extend(payload.get("records") or [])
    return records


def prompt_sequence(record: dict[str, Any]) -> list[dict[str, str]]:
    stored = record.get("prompts") or []
    if stored:
        return [
            {
                "turn_kind": str(item.get("turn_kind") or f"turn_{index}"),
                "prompt": str(item.get("prompt") or ""),
            }
            for index, item in enumerate(stored, start=1)
        ]
    sequence = []
    if record.get("seed_prompt"):
        sequence.append({"turn_kind": "seed", "prompt": str(record["seed_prompt"])})
    for index, prompt in enumerate(record.get("warmup_prompts") or [], start=1):
        sequence.append({"turn_kind": f"warmup_{index}", "prompt": str(prompt)})
    sequence.append({"turn_kind": "attack", "prompt": str(record.get("attack_prompt") or "")})
    return sequence


def infer_label_status(attack: str, sequence: list[dict[str, str]]) -> tuple[str, bool]:
    attack_prompt = next(
        (item["prompt"] for item in reversed(sequence) if item["turn_kind"] == "attack"),
        sequence[-1]["prompt"] if sequence else "",
    )
    label_present = any(label in attack_prompt.casefold() for label in ATTACK_LABELS[attack])
    return (
        "inferred-attack-labelled"
        if label_present
        else "inferred-family-label-omitted"
    ), label_present


def index_by_pair(records: list[dict[str, Any]], arm: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        pair_id = str(record.get("pair_id") or "")
        if not pair_id:
            raise RuntimeError(f"{arm}: record without pair_id")
        if pair_id in indexed:
            raise RuntimeError(f"{arm}: duplicate pair_id {pair_id}")
        indexed[pair_id] = record
    return indexed


def audit_attack(attack: str, run_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    off = index_by_pair(load_records(run_root / "arm_A_guard_off"), "guard_off")
    on = index_by_pair(load_records(run_root / "arm_B_guard_on"), "guard_on")
    rows: list[dict[str, Any]] = []
    for pair_id in sorted(set(off) | set(on)):
        off_sequence = prompt_sequence(off[pair_id]) if pair_id in off else []
        on_sequence = prompt_sequence(on[pair_id]) if pair_id in on else []
        off_serialized = stable_json(off_sequence)
        on_serialized = stable_json(on_sequence)
        label_status, label_present = infer_label_status(
            attack, off_sequence or on_sequence
        )
        rows.append(
            {
                "attack": attack,
                "pair_id": pair_id,
                "guard_off_present": pair_id in off,
                "guard_on_present": pair_id in on,
                "prompt_sequence_equal": bool(off_sequence) and off_sequence == on_sequence,
                "guard_off_prompt_sha256": sha256_text(off_serialized) if off_sequence else "",
                "guard_on_prompt_sha256": sha256_text(on_serialized) if on_sequence else "",
                "prompt_label_status": label_status,
                "attack_family_label_present": label_present,
                "prompt_style_source": "offline_record_audit",
                "original_top_level_prompt_style_available": False,
            }
        )
    summary = {
        "attack": attack,
        "run_root": str(run_root),
        "guard_off_records": len(off),
        "guard_on_records": len(on),
        "union_pair_ids": len(rows),
        "complete_pairs": sum(r["guard_off_present"] and r["guard_on_present"] for r in rows),
        "equal_prompt_pairs": sum(r["prompt_sequence_equal"] for r in rows),
        "prompt_label_statuses": sorted(
            {r["prompt_label_status"] for r in rows}
        ),
        "original_top_level_prompt_style_available": False,
        "classification_method": "case-insensitive search for the explicit attack-family label in the preserved final attack prompt",
    }
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a03-root", type=Path, required=True)
    parser.add_argument("--a05-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    summaries = []
    rows = []
    for attack, root in (("A03", args.a03_root), ("A05", args.a05_root)):
        summary, attack_rows = audit_attack(attack, root)
        summaries.append(summary)
        rows.extend(attack_rows)

    with (args.output_dir / "pair_prompt_provenance.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_type": "additive record-level matched-prompt provenance",
        "mutates_historical_results": False,
        "attacks": summaries,
    }
    with (args.output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(args.output_dir)


if __name__ == "__main__":
    main()
