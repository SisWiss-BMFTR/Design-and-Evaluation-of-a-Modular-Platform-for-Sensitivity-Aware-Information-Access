#!/usr/bin/env python3
"""Merge five A03 recovery shards into the canonical 225-record outputs."""

from __future__ import annotations

import argparse
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from run_access_level_downgrade_task import (
    RunRecord,
    aggregate_by_access_and_history,
    aggregate_by_target_condition,
    compute_overall_counts,
    write_csv_output,
    write_json_output,
    write_markdown_output,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("recovery_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    shard_paths = sorted(args.recovery_root.glob("*/results.json"))
    if len(shard_paths) != 5:
        raise SystemExit(f"Expected 5 completed shard JSON files, found {len(shard_paths)}")

    records = []
    target_ids = []
    indexed_chunks = None
    for path in shard_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        shard_records = [RunRecord(**item) for item in payload["records"]]
        if len(shard_records) != 45:
            raise SystemExit(f"Expected 45 records in {path}, found {len(shard_records)}")
        records.extend(shard_records)
        target_ids.extend(target["target_id"] for target in payload["targets"])
        indexed_chunks = indexed_chunks or payload["design"]["indexed_chunks"]

    keys = {
        (record.target_id, record.access_after, record.pre_attack_history_length, record.iteration)
        for record in records
    }
    if len(records) != 225 or len(keys) != 225 or len(set(target_ids)) != 5:
        raise SystemExit(
            f"Invalid merged matrix: records={len(records)}, unique_keys={len(keys)}, "
            f"targets={len(set(target_ids))}"
        )

    records.sort(
        key=lambda r: (r.target_id, r.access_after, r.pre_attack_history_length, r.iteration)
    )
    target_rows = aggregate_by_target_condition(records)
    condition_rows = aggregate_by_access_and_history(records)
    overall = compute_overall_counts(records)
    report_args = Namespace(
        rag_mode="sensitivity_eval_mode",
        access="all",
        target_ids=sorted(set(target_ids)),
        conversation_lengths=[1, 3, 5],
        iterations=5,
        retrieval_only=False,
    )
    shared = SimpleNamespace(chunk_count=indexed_chunks)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_output(args.output_dir / "results.json", report_args, shared, records, target_rows, condition_rows, overall)
    write_csv_output(args.output_dir / "results.csv", records)
    write_markdown_output(args.output_dir / "report.md", report_args, shared, records, target_rows, condition_rows, overall)
    print(f"Merged {len(records)} records into {args.output_dir}")


if __name__ == "__main__":
    main()
