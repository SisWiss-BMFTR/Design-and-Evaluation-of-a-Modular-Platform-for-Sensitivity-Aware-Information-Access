#!/usr/bin/env python3
"""Compare stored pre/post experiment prompts without mutating result folders."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ATTACK_DIRS = {
    "A01": "attack_01_direct_cell_extraction",
    "A02": "attack_02_multiturn_row_construction",
    "A03": "attack_03_access_level_downgrade_task",
    "A04": "attack_04_relational_join_path_inference",
    "A05": "attack_05_rank_probing_membership_inference",
    "A06": "attack_06_prompt_injection_poisoned_row",
    "A07": "attack_07_backdoor_triggered_extraction",
    "A08": "attack_08_embedding_side_leakage",
}
MODES = ("secure_rag_mode", "sensitivity_eval_mode")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def locate_result(root: Path, attack_id: str, mode: str) -> Optional[Path]:
    expected = ATTACK_DIRS[attack_id]
    matches = sorted(root.glob(f"**/{expected}/{mode}/results.json"))
    if len(matches) > 1:
        raise RuntimeError(f"ambiguous {attack_id}/{mode} under {root}: {matches}")
    return matches[0] if matches else None


def prompts_from_record(attack_id: str, record: Dict[str, Any]) -> List[Tuple[str, str]]:
    if attack_id == "A02":
        return [
            (str(turn.get("turn_kind") or f"turn_{index}"), str(turn.get("prompt") or ""))
            for index, turn in enumerate(record.get("turns") or [], start=1)
        ]
    if attack_id == "A03":
        prompts = [("seed", str(record.get("seed_prompt") or ""))]
        prompts.append(("attack", str(record.get("attack_prompt") or "")))
        return prompts
    if attack_id in {"A05", "A06", "A07"}:
        prompts = [
            (f"warmup_{index}", str(prompt))
            for index, prompt in enumerate(record.get("warmup_prompts") or [], start=1)
        ]
        prompts.append(("attack", str(record.get("attack_prompt") or "")))
        return prompts
    return []


def record_key(record: Dict[str, Any]) -> Tuple[str, str, int, int]:
    role = str(record.get("access", record.get("access_after", "")))
    length = int(record.get("conversation_length", record.get("pre_attack_history_length", 0)))
    return str(record.get("target_id") or ""), role, length, int(record.get("iteration", 0))


def index_records(records: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str, int, int], Dict[str, Any]]:
    indexed = {}  # type: Dict[Tuple[str, str, int, int], Dict[str, Any]]
    for record in records:
        key = record_key(record)
        if key in indexed:
            raise RuntimeError(f"duplicate condition key: {key}")
        indexed[key] = record
    return indexed


def difference_summary(pre: str, post: str) -> str:
    if pre == post:
        return "exact match"
    if not pre or not post:
        return "prompt unavailable in one or both records"
    pre_words = pre.split()
    post_words = post.split()
    removed = list((Counter(pre_words) - Counter(post_words)).elements())
    added = list((Counter(post_words) - Counter(pre_words)).elements())
    return f"removed={removed[:12]}; added={added[:12]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-root", type=Path, required=True)
    parser.add_argument("--post-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path("outputs/audits") / f"prompt_equivalence_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)

    rows = []  # type: List[Dict[str, Any]]
    coverage = []  # type: List[Dict[str, Any]]
    for attack_id in ATTACK_DIRS:
        for mode in MODES:
            pre_path = locate_result(args.pre_root, attack_id, mode)
            post_path = locate_result(args.post_root, attack_id, mode)
            if not pre_path or not post_path:
                coverage.append({"attack_id": attack_id, "mode": mode, "status": "result file missing"})
                continue
            pre_data, post_data = load_json(pre_path), load_json(post_path)
            pre_records = index_records(pre_data.get("records") or [])
            post_records = index_records(post_data.get("records") or [])
            common = sorted(set(pre_records) & set(post_records))
            stored = 0
            for key in common:
                pre_prompts = prompts_from_record(attack_id, pre_records[key])
                post_prompts = prompts_from_record(attack_id, post_records[key])
                if pre_prompts or post_prompts:
                    stored += 1
                max_turns = max(len(pre_prompts), len(post_prompts))
                for index in range(max_turns):
                    pre_kind, pre_prompt = pre_prompts[index] if index < len(pre_prompts) else ("missing", "")
                    post_kind, post_prompt = post_prompts[index] if index < len(post_prompts) else ("missing", "")
                    rows.append({
                        "attack_id": attack_id,
                        "mode": mode,
                        "target_id": key[0],
                        "role": key[1],
                        "conversation_length": key[2],
                        "iteration": key[3],
                        "prompt_index": index + 1,
                        "pre_prompt_kind": pre_kind,
                        "post_prompt_kind": post_kind,
                        "pre_prompt": pre_prompt,
                        "post_prompt": post_prompt,
                        "pre_prompt_hash": stable_hash(pre_prompt) if pre_prompt else "",
                        "post_prompt_hash": stable_hash(post_prompt) if post_prompt else "",
                        "exact_match": bool(pre_prompt) and pre_prompt == post_prompt,
                        "difference_summary": difference_summary(pre_prompt, post_prompt),
                    })
            coverage.append({
                "attack_id": attack_id,
                "mode": mode,
                "pre_records": len(pre_records),
                "post_records": len(post_records),
                "common_conditions": len(common),
                "conditions_with_stored_prompts": stored,
                "status": "comparable" if stored else "exact prompts not stored",
                "pre_result": str(pre_path),
                "post_result": str(post_path),
            })

    fieldnames = list(rows[0]) if rows else []
    with (output_dir / "prompt_equivalence.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    exact = sum(bool(row["exact_match"]) for row in rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pre_root": str(args.pre_root),
        "post_root": str(args.post_root),
        "prompt_rows": len(rows),
        "exact_matches": exact,
        "differences": len(rows) - exact,
        "coverage": coverage,
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(output_dir)


if __name__ == "__main__":
    main()
