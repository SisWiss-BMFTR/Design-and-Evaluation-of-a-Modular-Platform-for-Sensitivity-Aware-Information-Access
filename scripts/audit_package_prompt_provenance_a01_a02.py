#!/usr/bin/env python3
"""Evidence-level package-prompt audit for historical A01 and A02 runs.

This audit does not mutate historical results.  It distinguishes directly
stored prompt evidence from a code-backed reconstruction and from unavailable
historical request provenance.
"""

from __future__ import annotations

import argparse
import ast
import csv
import difflib
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODES = ("secure_rag_mode", "sensitivity_eval_mode")

A01_BASELINE_ROOT = (
    ROOT
    / "outputs/experiments/"
    "gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719/"
    "attack_01_direct_cell_extraction"
)
A01_HARDENED_ROOT = (
    ROOT
    / "outputs/experiments/post hardened 1-8/"
    "gpt4o_mini_slurm_attack01_neutral_posthardened_20260720/"
    "attack_01_direct_cell_extraction"
)
A01_HARDENED_JOB_ROOT = A01_HARDENED_ROOT.parent / "slurm"

A02_BASELINE_ROOT = (
    ROOT
    / "outputs/experiments/"
    "gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719/"
    "attack_02_multiturn_row_construction"
)
A02_HARDENED_ROOT = (
    ROOT
    / "outputs/experiments/post hardened 1-8/"
    "attack_02_multiturn_row_construction"
)

# The hardened A01 job ran on 20--21 July.  Its working tree was not captured.
# The exact renderer call and result schema seen in the job logs were next
# preserved in this commit on 22 July.
A01_RENDERER_COMMIT = "e66ee5a22b49886317362b9b577c22d3be248831"
A01_RENDERER_PATH = "code/evaluation2/run_direct_cell_extraction.py"
A01_NEUTRAL_PATTERN = (
    r"^Direct cell extraction attack\.\s*"
    r"Extract the exact XLSX cell value only\.\s*"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def git_show(commit: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout


def git_blob(commit: str, path: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            if node.end_lineno is None:
                raise RuntimeError(f"missing end line for {function_name}")
            return "".join(lines[node.lineno - 1 : node.end_lineno])
    raise RuntimeError(f"function {function_name} not found")


def exact_diff(before: str, after: str) -> dict[str, Any]:
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    operations = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        operations.append(
            {
                "operation": tag,
                "baseline_text": before[i1:i2],
                "hardened_text": after[j1:j2],
                "baseline_span": [i1, i2],
                "hardened_span": [j1, j2],
            }
        )
    return {
        "identical": before == after,
        "operations": operations,
        "unified_diff": "\n".join(
            difflib.unified_diff(
                [before + "\n"],
                [after + "\n"],
                fromfile="baseline",
                tofile="hardened_reconstructed",
                lineterm="",
            )
        ),
    }


def index_records(records: list[dict[str, Any]]) -> dict[tuple[str, str, int, int], dict[str, Any]]:
    indexed: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record["target_id"]),
            str(record["access"]),
            int(record["conversation_length"]),
            int(record["iteration"]),
        )
        if key in indexed:
            raise RuntimeError(f"duplicate condition {key}")
        indexed[key] = record
    return indexed


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def audit_a01(output_dir: Path) -> dict[str, Any]:
    baseline_documents = {
        mode: load_json(A01_BASELINE_ROOT / mode / "results.json") for mode in MODES
    }
    hardened_documents = {
        mode: load_json(A01_HARDENED_ROOT / mode / "results.json") for mode in MODES
    }

    baseline_targets_by_mode = {
        mode: {item["target_id"]: item for item in document["targets"]}
        for mode, document in baseline_documents.items()
    }
    hardened_targets_by_mode = {
        mode: {item["target_id"]: item for item in document["targets"]}
        for mode, document in hardened_documents.items()
    }
    target_ids = sorted(baseline_targets_by_mode[MODES[0]])
    if len(target_ids) != 5:
        raise RuntimeError(f"A01 expected five targets, found {target_ids}")

    renderer_source = git_show(A01_RENDERER_COMMIT, A01_RENDERER_PATH)
    renderer_function = function_source(renderer_source, "attack_prompt")
    expected_function_fragment = (
        "return re.sub(\n"
        '            r"^Direct cell extraction attack\\.\\s*Extract the exact XLSX cell value only\\.\\s*",'
    )
    if expected_function_fragment not in renderer_function:
        raise RuntimeError("preserved A01 renderer no longer matches expected neutral transform")

    rows: list[dict[str, Any]] = []
    detailed_rows: list[dict[str, Any]] = []
    for target_id in target_ids:
        baseline_variants = {
            baseline_targets_by_mode[mode][target_id]["prompt"] for mode in MODES
        }
        hardened_variants = {
            hardened_targets_by_mode[mode][target_id]["prompt"] for mode in MODES
        }
        if len(baseline_variants) != 1 or len(hardened_variants) != 1:
            raise RuntimeError(f"A01 target prompt differs across modes for {target_id}")
        baseline_prompt = next(iter(baseline_variants))
        hardened_base = next(iter(hardened_variants))
        reconstructed = re.sub(A01_NEUTRAL_PATTERN, "", hardened_base)
        if reconstructed == hardened_base:
            raise RuntimeError(f"neutral renderer made no change for {target_id}")
        diff = exact_diff(baseline_prompt, reconstructed)
        operations = diff["operations"]
        difference_text = "; ".join(
            f"{item['operation']}: baseline={item['baseline_text']!r}; "
            f"hardened={item['hardened_text']!r}"
            for item in operations
        )
        rows.append(
            {
                "target_id": target_id,
                "baseline_target_prompt": baseline_prompt,
                "hardened_base_template": hardened_base,
                "reconstructed_hardened_final_attack_prompt": reconstructed,
                "identical": diff["identical"],
                "exact_textual_difference": difference_text,
                "baseline_prompt_sha256": sha256_text(baseline_prompt),
                "hardened_final_prompt_sha256": sha256_text(reconstructed),
            }
        )
        detailed_rows.append({**rows[-1], "diff": diff})

    if any(row["identical"] for row in rows):
        raise RuntimeError("A01 audit expected all five package prompts to differ")

    hardened_styles = {
        mode: hardened_documents[mode].get("design", {}).get("prompt_style")
        for mode in MODES
    }
    if set(hardened_styles.values()) != {"neutral"}:
        raise RuntimeError(f"unexpected A01 hardened prompt style: {hardened_styles}")

    log_paths = sorted(A01_HARDENED_JOB_ROOT.glob("*.out")) + sorted(
        A01_HARDENED_JOB_ROOT.glob("*.err")
    )
    neutral_logs = []
    renderer_trace_logs = []
    for path in log_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "PROMPT_STYLE=neutral" in text:
            neutral_logs.append(relative(path))
        if (
            A01_RENDERER_PATH in text
            and "delivered_answer = run_query(pipeline, attack_prompt(target, prompt_style))"
            in text
        ):
            renderer_trace_logs.append(relative(path))
    if not neutral_logs or not renderer_trace_logs:
        raise RuntimeError("A01 hardened logs do not corroborate renderer/style")

    write_csv(output_dir / "a01_target_prompt_comparison.csv", rows)
    (output_dir / "a01_target_prompt_comparison.json").write_text(
        json.dumps(detailed_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown = [
        "# A01 target-level package prompt comparison",
        "",
        "| Target | Baseline target prompt | Reconstructed hardened final attack prompt | Identical | Exact textual difference |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        esc = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        markdown.append(
            f"| `{esc(row['target_id'])}` | {esc(row['baseline_target_prompt'])} | "
            f"{esc(row['reconstructed_hardened_final_attack_prompt'])} | "
            f"{str(row['identical']).lower()} | {esc(row['exact_textual_difference'])} |"
        )
    (output_dir / "a01_target_prompt_comparison.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )

    return {
        "status": "PASS",
        "interpretation": (
            "A01 target-level prompts are partially preserved/reconstructable and "
            "are not package-equivalent. The complete historical prompt is unavailable."
        ),
        "baseline_result_files": {
            mode: {
                "path": relative(A01_BASELINE_ROOT / mode / "results.json"),
                "sha256": sha256_file(A01_BASELINE_ROOT / mode / "results.json"),
                "prompt_location": "top-level targets[].prompt",
            }
            for mode in MODES
        },
        "hardened_result_files": {
            mode: {
                "path": relative(A01_HARDENED_ROOT / mode / "results.json"),
                "sha256": sha256_file(A01_HARDENED_ROOT / mode / "results.json"),
                "base_template_location": "top-level targets[].prompt",
                "prompt_style_location": "top-level design.prompt_style",
                "prompt_style": hardened_styles[mode],
            }
            for mode in MODES
        },
        "renderer": {
            "file_path": A01_RENDERER_PATH,
            "preserved_commit": A01_RENDERER_COMMIT,
            "preserved_file_sha256": sha256_text(renderer_source),
            "preserved_git_blob": git_blob(A01_RENDERER_COMMIT, A01_RENDERER_PATH),
            "function": "attack_prompt",
            "function_source_sha256": sha256_text(renderer_function),
            "neutral_regex": A01_NEUTRAL_PATTERN,
            "correspondence_status": (
                "corroborated reconstruction; not a cryptographic run snapshot"
            ),
            "correspondence_evidence": {
                "job_logs_recording_prompt_style_neutral": neutral_logs,
                "job_logs_recording_renderer_call_site": renderer_trace_logs,
                "result_schema_and_design_match_preserved_renderer_version": True,
                "limitation": (
                    "The hardened-package job did not record its exact Git commit, "
                    "dirty-tree patch, or source manifest. The renderer used by the "
                    "job was later preserved at the cited commit and is corroborated "
                    "by the run traceback and result schema, but byte identity of the "
                    "entire historical source tree cannot be proved."
                ),
            },
        },
        "target_comparison": {
            "targets": len(rows),
            "identical": sum(bool(row["identical"]) for row in rows),
            "different": sum(not bool(row["identical"]) for row in rows),
            "csv": "a01_target_prompt_comparison.csv",
            "json": "a01_target_prompt_comparison.json",
            "markdown": "a01_target_prompt_comparison.md",
        },
        "availability": {
            "baseline_target_level_attack_prompt": "directly stored in targets[].prompt",
            "hardened_base_template": "directly stored in targets[].prompt",
            "hardened_final_attack_prompt": (
                "reconstructed from stored base template, recorded neutral style, "
                "and corroborated deterministic renderer"
            ),
            "complete_per_conversation_user_prompt_sequence": "unavailable",
            "exact_system_prompt": "unavailable",
            "exact_api_message_payload": "unavailable",
        },
    }


def audit_a02(output_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    final_pairs: Counter[tuple[str, str]] = Counter()
    result_files: dict[str, dict[str, dict[str, str]]] = {
        "baseline": {},
        "hardened": {},
    }

    for mode in MODES:
        baseline_path = A02_BASELINE_ROOT / mode / "results.json"
        hardened_path = A02_HARDENED_ROOT / mode / "results.json"
        baseline_document = load_json(baseline_path)
        hardened_document = load_json(hardened_path)
        baseline = index_records(baseline_document.get("records") or [])
        hardened = index_records(hardened_document.get("records") or [])
        if len(baseline) != 225 or len(hardened) != 225:
            raise RuntimeError(
                f"A02 {mode}: expected 225 records per package, found "
                f"{len(baseline)} and {len(hardened)}"
            )
        if set(baseline) != set(hardened):
            raise RuntimeError(f"A02 {mode}: condition sets differ")

        result_files["baseline"][mode] = {
            "path": relative(baseline_path),
            "sha256": sha256_file(baseline_path),
        }
        result_files["hardened"][mode] = {
            "path": relative(hardened_path),
            "sha256": sha256_file(hardened_path),
        }

        for key in sorted(baseline):
            baseline_turns = baseline[key].get("turns") or []
            hardened_turns = hardened[key].get("turns") or []
            baseline_sequence = [str(turn.get("prompt") or "") for turn in baseline_turns]
            hardened_sequence = [str(turn.get("prompt") or "") for turn in hardened_turns]
            if not baseline_sequence or not hardened_sequence:
                raise RuntimeError(f"A02 {mode}/{key}: missing turns[].prompt")
            if len(baseline_sequence) != key[2] or len(hardened_sequence) != key[2]:
                raise RuntimeError(f"A02 {mode}/{key}: turn count does not match condition")

            warmup_equal = baseline_sequence[:-1] == hardened_sequence[:-1]
            final_equal = baseline_sequence[-1] == hardened_sequence[-1]
            full_equal = baseline_sequence == hardened_sequence
            counts["conditions"] += 1
            counts["warmup_prompt_rows"] += len(baseline_sequence) - 1
            counts["warmup_equal_conditions"] += int(warmup_equal)
            counts["final_equal_conditions"] += int(final_equal)
            counts["full_equal_conditions"] += int(full_equal)
            final_pairs[(baseline_sequence[-1], hardened_sequence[-1])] += 1
            diff = exact_diff(baseline_sequence[-1], hardened_sequence[-1])
            rows.append(
                {
                    "mode": mode,
                    "target_id": key[0],
                    "access": key[1],
                    "conversation_length": key[2],
                    "iteration": key[3],
                    "baseline_turn_count": len(baseline_sequence),
                    "hardened_turn_count": len(hardened_sequence),
                    "warmup_prompts_equal": warmup_equal,
                    "final_attack_prompt_equal": final_equal,
                    "complete_user_prompt_sequence_equal": full_equal,
                    "baseline_warmup_prompts_json": json.dumps(
                        baseline_sequence[:-1], ensure_ascii=False
                    ),
                    "hardened_warmup_prompts_json": json.dumps(
                        hardened_sequence[:-1], ensure_ascii=False
                    ),
                    "baseline_final_attack_prompt": baseline_sequence[-1],
                    "hardened_final_attack_prompt": hardened_sequence[-1],
                    "baseline_sequence_sha256": canonical_hash(baseline_sequence),
                    "hardened_sequence_sha256": canonical_hash(hardened_sequence),
                    "final_exact_textual_difference": "; ".join(
                        f"{item['operation']}: baseline={item['baseline_text']!r}; "
                        f"hardened={item['hardened_text']!r}"
                        for item in diff["operations"]
                    ),
                }
            )

    if counts["conditions"] != 450:
        raise RuntimeError(f"A02 expected 450 conditions, found {counts['conditions']}")
    if counts["warmup_equal_conditions"] != 450:
        raise RuntimeError("A02 warm-up sequences are not equal in all conditions")
    if counts["final_equal_conditions"] != 0:
        raise RuntimeError("A02 expected all final attack prompts to differ")
    if counts["full_equal_conditions"] != 0:
        raise RuntimeError("A02 expected all complete sequences to differ")

    write_csv(output_dir / "a02_prompt_sequence_comparison.csv", rows)
    final_pair_rows = [
        {
            "count": count,
            "baseline_final_attack_prompt": before,
            "hardened_final_attack_prompt": after,
            "baseline_sha256": sha256_text(before),
            "hardened_sha256": sha256_text(after),
            "difference": exact_diff(before, after)["operations"],
        }
        for (before, after), count in sorted(final_pairs.items())
    ]
    (output_dir / "a02_unique_final_prompt_pairs.json").write_text(
        json.dumps(final_pair_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "PASS",
        "interpretation": (
            "A02 complete user-prompt sequences are preserved. Warm-up prompts "
            "match in every condition, while the final attack prompt differs in "
            "all 450 conditions. The package comparison remains descriptive."
        ),
        "result_files": result_files,
        "comparison": {
            "conditions": counts["conditions"],
            "warmup_prompt_rows_compared": counts["warmup_prompt_rows"],
            "conditions_with_identical_warmups": counts["warmup_equal_conditions"],
            "conditions_with_different_warmups": (
                counts["conditions"] - counts["warmup_equal_conditions"]
            ),
            "conditions_with_identical_final_attack_prompt": counts[
                "final_equal_conditions"
            ],
            "conditions_with_different_final_attack_prompt": (
                counts["conditions"] - counts["final_equal_conditions"]
            ),
            "conditions_with_identical_complete_user_prompt_sequence": counts[
                "full_equal_conditions"
            ],
            "conditions_with_different_complete_user_prompt_sequence": (
                counts["conditions"] - counts["full_equal_conditions"]
            ),
            "unique_final_prompt_pairs": len(final_pair_rows),
            "comparison_csv": "a02_prompt_sequence_comparison.csv",
            "unique_final_pairs_json": "a02_unique_final_prompt_pairs.json",
        },
        "availability": {
            "complete_per_conversation_user_prompt_sequence": (
                "directly stored in records[].turns[].prompt"
            ),
            "warmup_prompts": "directly stored and identical across packages",
            "final_attack_prompt": (
                "directly stored and different in 450/450 conditions"
            ),
            "exact_system_prompt": "unavailable",
            "exact_api_message_payload": "unavailable",
            "complete_source_state": "unavailable",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=False)

    a01 = audit_a01(output_dir)
    a02 = audit_a02(output_dir)
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": "package-prompt-provenance-a01-a02-v1",
        "generated_at": generated_at,
        "status": "PASS" if a01["status"] == a02["status"] == "PASS" else "FAIL",
        "scope": (
            "Historical original-baseline and hardened-package user-prompt "
            "provenance for A01 and A02; no experimental results are rescored or modified."
        ),
        "a01": a01,
        "a02": a02,
        "interpretive_constraints": [
            "A01 prompts are partially preserved/reconstructable but are not package-equivalent.",
            "A02 prompt sequences are preserved and systematically differ.",
            "Both package comparisons remain descriptive.",
            "Neither finding resolves the zero-to-zero matched verifier ablations.",
        ],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "checksums.json").write_text(
        json.dumps(
            {
                "summary_sha256": sha256_file(summary_path),
                "a01_csv_sha256": sha256_file(
                    output_dir / "a01_target_prompt_comparison.csv"
                ),
                "a01_json_sha256": sha256_file(
                    output_dir / "a01_target_prompt_comparison.json"
                ),
                "a02_csv_sha256": sha256_file(
                    output_dir / "a02_prompt_sequence_comparison.csv"
                ),
                "a02_unique_pairs_sha256": sha256_file(
                    output_dir / "a02_unique_final_prompt_pairs.json"
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output_dir)


if __name__ == "__main__":
    main()
