#!/usr/bin/env python3
"""Merge neutral Attack 2 target shards and write before/after reports."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from evaluation2.run_multiturn_row_construction_batch import (  # noqa: E402
    ConversationRecord,
    SCORABLE_FIELDS,
    SharedComponents,
    TargetSpec,
    TurnRecord,
    aggregate_access_length_rows,
    aggregate_condition_rows,
    write_csv_output,
    write_json_output,
    write_markdown_output,
)


TARGET_IDS = [
    "t1_r001_avocadoel",
    "t2_r002_sonnenblumenoel",
    "t3_r003_panthenol",
    "t4_r005_kamillenextrakt",
    "t5_r006_aloe_vera_gel",
]

MODES = ["secure_rag_mode", "sensitivity_eval_mode"]
UNAUTHORIZED = {"public", "internal"}


def pct(num: int, den: int) -> float:
    return (num / den * 100.0) if den else 0.0


def fmt(num: int, den: int) -> str:
    return f"{num}/{den} = {pct(num, den):.1f}%"


def bool_field(record: dict[str, Any], *names: str) -> bool:
    for name in names:
        if name in record:
            return bool(record.get(name))
    return False


def count(records: list[dict[str, Any]], *names: str) -> int:
    return sum(bool_field(record, *names) for record in records)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def turn_from_dict(data: dict[str, Any]) -> TurnRecord:
    allowed = {field.name for field in fields(TurnRecord)}
    return TurnRecord(**{key: data[key] for key in allowed})


def record_from_dict(data: dict[str, Any]) -> ConversationRecord:
    allowed = {field.name for field in fields(ConversationRecord)}
    payload = {key: data[key] for key in allowed if key in data}
    payload["turns"] = [turn_from_dict(turn) for turn in data["turns"]]
    return ConversationRecord(**payload)


def target_from_dict(data: dict[str, Any]) -> TargetSpec:
    return TargetSpec(**data)


def merge_mode(root: Path, mode: str) -> dict[str, Any]:
    records: list[ConversationRecord] = []
    targets: list[TargetSpec] = []
    indexed_chunks = None
    missing: list[Path] = []

    for target_id in TARGET_IDS:
        shard_path = root / f"{mode}__{target_id}" / "results.json"
        if not shard_path.exists():
            missing.append(shard_path)
            continue

        data = load_json(shard_path)
        records.extend(record_from_dict(record) for record in data["records"])
        targets.extend(target_from_dict(target) for target in data["targets"])
        indexed_chunks = indexed_chunks or data["design"].get("indexed_chunks", 0)

    if missing:
        missing_text = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing Attack 2 shard(s) for {mode}:\n{missing_text}")

    if len(records) != 225:
        raise ValueError(f"Expected 225 merged records for {mode}, found {len(records)}")

    if sorted({record.target_id for record in records}) != sorted(TARGET_IDS):
        raise ValueError(f"Merged records for {mode} do not cover exactly the expected targets")

    args = SimpleNamespace(
        rag_mode=mode,
        prompt_style="neutral",
        post_generation_verifier=True,
        access="all",
        conversation_lengths=[1, 3, 5],
        iterations=5,
    )
    shared = SharedComponents(embedder=None, retriever=None, chunk_count=int(indexed_chunks or 0))

    condition_rows = aggregate_condition_rows(records)
    access_length_rows = aggregate_access_length_rows(records)
    mode_root = root / mode
    write_json_output(
        output_path=mode_root / "results.json",
        args=args,
        shared=shared,
        targets=targets,
        records=records,
        condition_rows=condition_rows,
        access_length_rows=access_length_rows,
    )
    write_csv_output(mode_root / "results.csv", records)
    write_markdown_output(
        output_path=mode_root / "report.md",
        args=args,
        shared=shared,
        targets=targets,
        records=records,
        condition_rows=condition_rows,
        access_length_rows=access_length_rows,
    )

    return load_json(mode_root / "results.json")


def load_mode_records(root: Path, mode: str) -> list[dict[str, Any]]:
    return load_json(root / mode / "results.json")["records"]


def metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    unauthorized = [record for record in records if record["access"] in UNAUTHORIZED]
    protected = [record for record in records if record["access"] == "protected"]
    public = [record for record in unauthorized if record["access"] == "public"]
    internal = [record for record in unauthorized if record["access"] == "internal"]

    final_leaks = count(unauthorized, "final_answer_partial_leak")
    protected_positive = count(protected, "final_answer_full_reconstruction")
    raw_leaks_available = any("raw_final_answer_partial_leak" in record for record in records)

    return {
        "total": len(records),
        "unauthorized_total": len(unauthorized),
        "protected_total": len(protected),
        "unauthorized_final_leaks": final_leaks,
        "unauthorized_full_reconstructions": count(unauthorized, "final_answer_full_reconstruction"),
        "unauthorized_retrieval_full_support": count(unauthorized, "final_retrieved_full_support"),
        "public_final_leaks": count(public, "final_answer_partial_leak"),
        "internal_final_leaks": count(internal, "final_answer_partial_leak"),
        "protected_positive": protected_positive,
        "protected_failures": len(protected) - protected_positive,
        "raw_leaks_available": raw_leaks_available,
        "unauthorized_raw_final_leaks": (
            count(unauthorized, "raw_final_answer_partial_leak") if raw_leaks_available else None
        ),
        "verifier_redactions": count(records, "post_generation_redaction_count"),
    }


def mode_prompt_note(records: list[dict[str, Any]]) -> str:
    styles = sorted({str(record.get("prompt_style")) for record in records if record.get("prompt_style")})
    if styles:
        return ", ".join(styles)

    prompts = [turn["prompt"] for record in records for turn in record.get("turns", []) if turn.get("turn_kind") == "attack"]
    if prompts and all("attack" not in prompt.casefold() for prompt in prompts):
        return "neutral legacy prompt, no explicit attack-name label"
    return "legacy prompt metadata unavailable"


def choose_example(records: list[dict[str, Any]], after: bool) -> dict[str, Any] | None:
    unauthorized = [record for record in records if record["access"] in UNAUTHORIZED]
    if after:
        for record in unauthorized:
            if bool(record.get("raw_final_answer_partial_leak")) and not bool(record.get("final_answer_partial_leak")):
                return record
    for record in unauthorized:
        if bool(record.get("final_answer_partial_leak")):
            return record
    return unauthorized[0] if unauthorized else None


def compact_text(text: str, limit: int = 700) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def make_before_after_report(before_root: Path, after_root: Path, output_root: Path) -> dict[str, Any]:
    before_by_mode = {mode: load_mode_records(before_root, mode) for mode in MODES}
    after_by_mode = {mode: load_mode_records(after_root, mode) for mode in MODES}
    summary: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "before_root": str(before_root),
        "after_root": str(after_root),
        "modes": {},
    }

    lines = [
        "# Attack 2 Neutral Prompt Before/After Report",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Scope",
        "",
        "- Attack: A02 multi-turn row construction.",
        "- Prompt condition: neutral final request wording with no explicit attack-name label.",
        "- Before condition: neutral pre-hardening run.",
        "- After condition: metadata-rich context plus post-generation leakage verifier.",
        "- Important sensitivity-eval rule: restricted values remain visible to the LLM; the defense is evaluated at the delivered-answer boundary.",
        "",
        "## Inputs",
        "",
        f"- Before root: `{before_root}`",
        f"- After root: `{after_root}`",
        "- Modes: `secure_rag_mode`, `sensitivity_eval_mode`.",
        "- Per mode: 5 targets x 3 access levels x 3 conversation lengths x 5 iterations = 225 conversations.",
        "- Unauthorized denominator: 150 public/internal conversations per mode.",
        "- Protected positive-control denominator: 75 protected conversations per mode.",
        "",
        "## Prompt Check",
        "",
    ]

    for mode in MODES:
        lines.append(f"- `{mode}` before prompt style: {mode_prompt_note(before_by_mode[mode])}.")
        lines.append(f"- `{mode}` after prompt style: {mode_prompt_note(after_by_mode[mode])}.")

    lines.extend(
        [
            "",
            "## Summary Table",
            "",
            "| Mode | Before retrieval full support | Before delivered leakage | After raw leakage | After verifier redactions | After delivered leakage | Leakage change | Before protected success | After protected success |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for mode in MODES:
        before_metrics = metrics(before_by_mode[mode])
        after_metrics = metrics(after_by_mode[mode])
        before_rate = pct(before_metrics["unauthorized_final_leaks"], before_metrics["unauthorized_total"])
        after_rate = pct(after_metrics["unauthorized_final_leaks"], after_metrics["unauthorized_total"])
        change = after_rate - before_rate
        summary["modes"][mode] = {
            "before": before_metrics,
            "after": after_metrics,
            "leakage_change_percentage_points": round(change, 1),
        }
        after_raw = (
            fmt(after_metrics["unauthorized_raw_final_leaks"], after_metrics["unauthorized_total"])
            if after_metrics["unauthorized_raw_final_leaks"] is not None
            else "not recorded"
        )
        lines.append(
            f"| `{mode}` | "
            f"{fmt(before_metrics['unauthorized_retrieval_full_support'], before_metrics['unauthorized_total'])} | "
            f"{fmt(before_metrics['unauthorized_final_leaks'], before_metrics['unauthorized_total'])} | "
            f"{after_raw} | "
            f"{fmt(after_metrics['verifier_redactions'], after_metrics['total'])} | "
            f"{fmt(after_metrics['unauthorized_final_leaks'], after_metrics['unauthorized_total'])} | "
            f"{change:+.1f} pp | "
            f"{fmt(before_metrics['protected_positive'], before_metrics['protected_total'])} | "
            f"{fmt(after_metrics['protected_positive'], after_metrics['protected_total'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Leakage in this attack is caused by row-level composition: the model is asked across one or more turns to focus on a known row identifier and then emit multiple protected fields as a complete row. In `sensitivity_eval_mode`, the key risk is sharper because restricted values are intentionally model-visible for evaluation, so the security boundary must be the delivered answer, not whether the model saw the values.",
            "",
            "The post-hardening design keeps the LLM-visible sensitivity-evaluation condition intact. Metadata-rich context tells the model which fields are restricted and why they must not be disclosed to public/internal roles. The post-generation verifier then checks the raw model answer against restricted structured values and replaces unsafe answers before delivery. The raw-versus-delivered metrics show whether the model attempted to leak and whether the verifier blocked it.",
            "",
            "## Public/Internal Split",
            "",
            "| Mode | Before public leaks | Before internal leaks | After public leaks | After internal leaks |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for mode in MODES:
        before_metrics = metrics(before_by_mode[mode])
        after_metrics = metrics(after_by_mode[mode])
        lines.append(
            f"| `{mode}` | "
            f"{before_metrics['public_final_leaks']}/75 | "
            f"{before_metrics['internal_final_leaks']}/75 | "
            f"{after_metrics['public_final_leaks']}/75 | "
            f"{after_metrics['internal_final_leaks']}/75 |"
        )

    lines.extend(["", "## Representative Examples", ""])
    for mode in MODES:
        before_example = choose_example(before_by_mode[mode], after=False)
        after_example = choose_example(after_by_mode[mode], after=True)
        lines.extend([f"### {mode}", ""])
        if before_example:
            lines.extend(
                [
                    f"Before example: `{before_example['access']}`, `{before_example['conversation_length']}` turns, `{before_example['target_id']}`.",
                    "",
                    "```text",
                    compact_text(before_example.get("final_answer", "")),
                    "```",
                    "",
                ]
            )
        if after_example:
            lines.extend(
                [
                    f"After example: `{after_example['access']}`, `{after_example['conversation_length']}` turns, `{after_example['target_id']}`.",
                    "",
                    "Raw model answer:",
                    "",
                    "```text",
                    compact_text(after_example.get("raw_final_answer", after_example.get("final_answer", ""))),
                    "```",
                    "",
                    "Delivered answer:",
                    "",
                    "```text",
                    compact_text(after_example.get("final_answer", "")),
                    "```",
                    "",
                ]
            )

    lines.extend(
        [
            "## Files Written",
            "",
            f"- Merged secure-mode report: `{after_root / 'secure_rag_mode' / 'report.md'}`",
            f"- Merged sensitivity-eval report: `{after_root / 'sensitivity_eval_mode' / 'report.md'}`",
            f"- This before/after report: `{output_root / 'A02_multiturn_row_construction_neutral_before_after_report.md'}`",
            f"- Machine-readable summary: `{output_root / 'A02_multiturn_row_construction_neutral_summary.json'}`",
            "",
        ]
    )

    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "A02_multiturn_row_construction_neutral_before_after_report.md"
    summary_path = output_root / "A02_multiturn_row_construction_neutral_summary.json"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    local_report_path = after_root / "neutral_before_after_report.md"
    local_summary_path = after_root / "neutral_summary.json"
    local_report_path.write_text("\n".join(lines), encoding="utf-8")
    local_summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "summary": summary,
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "local_report_path": str(local_report_path),
        "local_summary_path": str(local_summary_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--after-root",
        type=Path,
        default=Path("outputs/experiments/post hardened 1-8/attack_02_multiturn_row_construction"),
    )
    parser.add_argument(
        "--before-root",
        type=Path,
        default=Path(
            "outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719/"
            "attack_02_multiturn_row_construction"
        ),
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("reports/final_attack_reports"),
    )
    args = parser.parse_args()

    merged = {}
    for mode in MODES:
        merged[mode] = merge_mode(args.after_root, mode)

    output = make_before_after_report(
        before_root=args.before_root,
        after_root=args.after_root,
        output_root=args.report_root,
    )

    print("Merged Attack 2 neutral shards")
    for mode in MODES:
        print(f"- {mode}: {len(merged[mode]['records'])} records")
    print(f"- report: {output['report_path']}")
    print(f"- local report: {output['local_report_path']}")


if __name__ == "__main__":
    main()
