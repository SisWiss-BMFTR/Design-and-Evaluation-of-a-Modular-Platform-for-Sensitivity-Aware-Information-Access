#!/usr/bin/env python3
"""Prepare deterministic internal evidence archives without staging Git files.

The utility deliberately treats experiment trees as immutable inputs.  It creates
canonical per-member inventories, deterministic tar.zst archives, and verifies
every archived member's path, size, type, and SHA-256 against the source
inventory.  It never deletes or edits the source evidence.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "manifests"
INVENTORY_DIR = MANIFEST_DIR / "evidence_inventories"
INTERNAL_ROOT = ROOT / "internal_archive" / "thesis_evidence_20260823"
ARCHIVE_DIR = INTERNAL_ROOT / "archives"
PRE_CLEANUP_DIR = INTERNAL_ROOT / "pre_cleanup"


EVIDENCE = [
    {
        "experiment_id": "matched_A01",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E01_A01_output_leakage_verifier_20260727T143137Z",
        "claim_relationship": "Matched A01 output-leakage-verifier guard-off/guard-on evidence.",
    },
    {
        "experiment_id": "matched_A02",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E02_A02_output_leakage_verifier_20260727T185707Z",
        "claim_relationship": "Matched A02 output-leakage-verifier guard-off/guard-on evidence.",
    },
    {
        "experiment_id": "matched_A03",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E03_A03_access_change_memory_clear_20260727T231454Z",
        "claim_relationship": "Matched A03 access-change memory-clear guard-off/guard-on evidence.",
    },
    {
        "experiment_id": "matched_A04",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E04_A04_relation_access_guard_neutral_20260801T163000Z",
        "claim_relationship": "Superseding matched A04 relation-access-guard evidence used by the thesis.",
    },
    {
        "experiment_id": "matched_A05",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E05_A05_membership_guard_20260728T121108Z",
        "claim_relationship": "Matched A05 membership-guard guard-off/guard-on evidence.",
    },
    {
        "experiment_id": "matched_A06",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E06_A06_prompt_injection_guard_neutral_20260801T163000Z",
        "claim_relationship": "Superseding matched A06 prompt-injection-guard evidence used by the thesis.",
    },
    {
        "experiment_id": "matched_A07",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E07_A07_relation_access_guard_20260728T231214Z",
        "claim_relationship": "Matched natural-variant A07 relation-access-guard evidence.",
    },
    {
        "experiment_id": "matched_A08",
        "experiment_type": "AUTHORITATIVE_MATCHED_ABLATION",
        "raw_source_root": "outputs/experiments/matched_single_guard_ablations/E08_A08_embedding_probe_guard_20260729T092151Z",
        "claim_relationship": "Complete authoritative matched A08 embedding-probe-guard rerun.",
    },
    {
        "experiment_id": "supplemental_A02",
        "experiment_type": "SUPPLEMENTAL_FULL_CHALLENGE",
        "raw_source_root": "outputs/experiments/full_a02_verifier_challenge/FVC_A02_20260803T115546Z",
        "claim_relationship": "Supplemental full A02 verifier challenge evidence.",
    },
    {
        "experiment_id": "supplemental_A06",
        "experiment_type": "SUPPLEMENTAL_FROZEN_CHALLENGE",
        "raw_source_root": "outputs/experiments/supplemental_a06_poisoned_row/SA06_A06_prompt_injection_guard_20260805T220542Z",
        "claim_relationship": "Supplemental A06 pilot and confirmatory frozen poisoned-row evidence.",
    },
    {
        "experiment_id": "supplemental_A07S",
        "experiment_type": "SUPPLEMENTAL_MATCHED_CHALLENGE",
        "raw_source_root": "outputs/experiments/matched_a07s_prompt_injection_guard/E07S_A07S_prompt_injection_guard_family_label_omitted_20260803T021408Z",
        "claim_relationship": "Supplemental matched A07-S historical-prompt challenge evidence.",
    },
    {
        "experiment_id": "verifier_replay",
        "experiment_type": "DETERMINISTIC_VERIFIER_REPLAY",
        "raw_source_root": "outputs/verifier_validation/a01_a02_replay_v1_20260803",
        "claim_relationship": "Frozen A01/A02 deterministic verifier replay corpus and decisions.",
    },
]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_line(member):
    values = [
        member["type"],
        member["path"],
        member["size"],
        member["sha256"],
    ]
    return (json.dumps(values, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def inventory_for_root(root_path):
    members = []
    excluded_non_regular_entries = []
    for path in sorted(root_path.rglob("*"), key=lambda item: item.relative_to(root_path).as_posix()):
        relative = path.relative_to(root_path).as_posix()
        stat_result = path.lstat()
        if path.is_symlink():
            excluded_non_regular_entries.append(
                {
                    "path": relative,
                    "type": "symlink",
                    "reason": "Non-regular entry excluded from the evidence archive. Source-snapshot .env links are not part of the scientific source manifest and must not be distributed.",
                }
            )
        elif path.is_file():
            members.append(
                {
                    "path": relative,
                    "type": "file",
                    "size": stat_result.st_size,
                    "sha256": sha256_file(path),
                }
            )
    canonical = hashlib.sha256()
    for member in members:
        canonical.update(canonical_line(member))
    return {
        "schema_version": "canonical-evidence-inventory-v1",
        "canonicalization": "UTF-8 JSON array per line: [type,relative_path,size,sha256], sorted by relative_path, LF terminated",
        "raw_source_root": root_path.relative_to(ROOT).as_posix(),
        "member_count": len(members),
        "raw_byte_count": sum(item["size"] for item in members),
        "canonical_inventory_sha256": canonical.hexdigest(),
        "excluded_non_regular_entries": excluded_non_regular_entries,
        "members": members,
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def run_git(args):
    process = subprocess.Popen(["git"] + args, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise RuntimeError("git {} failed: {}".format(" ".join(args), stderr.decode("utf-8", errors="replace")))
    return stdout.decode("utf-8", errors="replace")


def capture_pre_cleanup_state():
    PRE_CLEANUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(str(INTERNAL_ROOT), 0o700)
    status_lines = run_git(["status", "--porcelain=v1", "-uall"]).splitlines()
    generated_prefixes = (
        "?? scripts/internal_archive_tools.py",
        "?? internal_archive/",
        "?? manifests/",
    )
    reconstructed = [line for line in status_lines if not line.startswith(generated_prefixes)]
    state = {
        "schema_version": "internal-pre-cleanup-git-state-v1",
        "capture_date": "2026-08-23",
        "note": "Preparation utility and its generated internal_archive/manifests outputs are excluded to reconstruct the state immediately before archive preparation.",
        "branch": run_git(["branch", "--show-current"]).strip(),
        "head": run_git(["rev-parse", "HEAD"]).strip(),
        "tracked_dirty_count": len(run_git(["diff", "--name-only"]).splitlines()),
        "status_porcelain": reconstructed,
        "gitignore_sha256": sha256_file(ROOT / ".gitignore"),
        "git_info_exclude_sha256": sha256_file(ROOT / ".git" / "info" / "exclude"),
    }
    write_json(PRE_CLEANUP_DIR / "GIT_STATE_BEFORE_PREPARATION.json", state)
    (PRE_CLEANUP_DIR / "git_status_porcelain.txt").write_text("\n".join(reconstructed) + "\n", encoding="utf-8")
    (PRE_CLEANUP_DIR / "gitignore.before").write_bytes((ROOT / ".gitignore").read_bytes())
    (PRE_CLEANUP_DIR / "git_info_exclude.before").write_bytes((ROOT / ".git" / "info" / "exclude").read_bytes())
    return state


def create_core_snapshot():
    selected = [
        ROOT / "README.md",
        ROOT / ".gitignore",
        ROOT / ".env.example",
        ROOT / "sensitivity_policy.yaml",
        ROOT / "sensitivity_overrides.yaml",
        ROOT / "data" / "SiSWiss_Testdaten.xlsx",
        ROOT / "code",
        ROOT / "scripts",
        ROOT / "tests",
        ROOT / "thesis",
        ROOT / "outputs" / "deliverables" / "Synchronized_Thesis_P1_Corrections.pdf",
        ROOT / "outputs" / "experiments" / "gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719",
        ROOT / "outputs" / "experiments" / "post hardened 1-8",
        ROOT / "outputs" / "rescoring" / "a02_policy_aware_20260722T155853Z",
        ROOT / "outputs" / "audits" / "package_prompt_provenance_a01_a02_20260803",
        ROOT / "outputs" / "final_thesis_evidence_20260725",
        ROOT / "outputs" / "final_thesis_evidence_20260803_prompt_provenance_v3",
        ROOT / "outputs" / "final_thesis_supplemental_evidence_20260806",
    ]
    excluded_parts = {"__pycache__", "build", "outputs"}
    members = []
    for selected_path in selected:
        candidates = [selected_path] if selected_path.is_file() else selected_path.rglob("*")
        for path in candidates:
            if not path.is_file() and not path.is_symlink():
                continue
            relative = path.relative_to(ROOT)
            if "__pycache__" in relative.parts or path.suffix == ".pyc":
                continue
            if relative.as_posix().startswith("thesis/build") or relative.as_posix().startswith("thesis/outputs/"):
                continue
            if relative.as_posix() == "thesis/chapter02_revision_report.md":
                continue
            if relative.as_posix() == "scripts/internal_archive_tools.py":
                continue
            members.append(relative.as_posix())
    members = sorted(set(members))
    archive_path = PRE_CLEANUP_DIR / "core_research_state_before_preparation.tar.zst"
    create_tar_zst(ROOT, members, archive_path)
    listing = verify_tar_zst(ROOT, members, archive_path, verify_source=True)
    result = {
        "archive_path": archive_path.relative_to(ROOT).as_posix(),
        "archive_size": archive_path.stat().st_size,
        "archive_sha256": sha256_file(archive_path),
        "member_count": len(members),
        "verification": listing,
    }
    write_json(PRE_CLEANUP_DIR / "core_research_state_before_preparation.json", result)
    return result


def create_tar_zst(base_dir, relative_members, archive_path):
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="internal-archive-members-", delete=False) as list_handle:
        list_path = Path(list_handle.name)
        for member in relative_members:
            list_handle.write(os.fsencode(member))
            list_handle.write(b"\0")
    try:
        tar_command = [
            "tar",
            "--create",
            "--file=-",
            "--format=posix",
            "--mtime=@0",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "--pax-option=delete=atime,delete=ctime",
            "--no-recursion",
            "--null",
            "--verbatim-files-from",
            "--files-from={}".format(str(list_path)),
        ]
        tar_process = subprocess.Popen(tar_command, cwd=str(base_dir), stdout=subprocess.PIPE)
        zstd_process = subprocess.Popen(
            ["zstd", "-q", "-T1", "-10", "-f", "-o", str(archive_path)],
            stdin=tar_process.stdout,
        )
        tar_process.stdout.close()
        zstd_return = zstd_process.wait()
        tar_return = tar_process.wait()
        if tar_return != 0 or zstd_return != 0:
            raise RuntimeError("archive creation failed: tar={}, zstd={}".format(tar_return, zstd_return))
    finally:
        list_path.unlink()


def verify_tar_zst(base_dir, relative_members, archive_path, verify_source):
    expected_paths = list(relative_members)
    expected = {}
    if verify_source:
        for relative in expected_paths:
            path = base_dir / relative
            stat_result = path.lstat()
            if path.is_symlink():
                target = os.readlink(str(path))
                expected[relative] = ("symlink", stat_result.st_size, hashlib.sha256(target.encode("utf-8", errors="surrogateescape")).hexdigest())
            else:
                expected[relative] = ("file", stat_result.st_size, sha256_file(path))
    zstd_process = subprocess.Popen(["zstd", "-q", "-dc", str(archive_path)], stdout=subprocess.PIPE)
    observed = {}
    with tarfile.open(fileobj=zstd_process.stdout, mode="r|") as archive:
        for member in archive:
            name = member.name
            if member.isfile():
                digest = hashlib.sha256()
                extracted = archive.extractfile(member)
                while True:
                    chunk = extracted.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                observed[name] = ("file", member.size, digest.hexdigest())
            elif member.issym():
                content = member.linkname.encode("utf-8", errors="surrogateescape")
                observed[name] = ("symlink", len(content), hashlib.sha256(content).hexdigest())
    zstd_process.stdout.close()
    return_code = zstd_process.wait()
    if return_code != 0:
        raise RuntimeError("zstd archive verification failed: {}".format(return_code))
    expected_set = set(expected_paths)
    observed_set = set(observed)
    result = {
        "status": "PASS" if expected_set == observed_set and (not verify_source or expected == observed) else "FAIL",
        "expected_member_count": len(expected_set),
        "observed_member_count": len(observed_set),
        "missing_members": sorted(expected_set - observed_set),
        "unexpected_members": sorted(observed_set - expected_set),
        "content_mismatch_count": 0,
    }
    if verify_source:
        result["content_mismatch_count"] = sum(1 for path in expected_set & observed_set if expected[path] != observed[path])
        if result["content_mismatch_count"]:
            result["status"] = "FAIL"
    return result


def create_inventories():
    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for item in EVIDENCE:
        root_path = ROOT / item["raw_source_root"]
        if not root_path.is_dir():
            raise RuntimeError("missing evidence root: {}".format(root_path))
        inventory = inventory_for_root(root_path)
        inventory.update(
            {
                "experiment_id": item["experiment_id"],
                "experiment_type": item["experiment_type"],
                "claim_relationship": item["claim_relationship"],
            }
        )
        inventory_path = INVENTORY_DIR / "{}.json".format(item["experiment_id"])
        write_json(inventory_path, inventory)
        summaries.append(
            {
                "experiment_id": item["experiment_id"],
                "inventory_path": inventory_path.relative_to(ROOT).as_posix(),
                "inventory_file_sha256": sha256_file(inventory_path),
                "member_count": inventory["member_count"],
                "raw_byte_count": inventory["raw_byte_count"],
                "canonical_inventory_sha256": inventory["canonical_inventory_sha256"],
            }
        )
    write_json(INVENTORY_DIR / "SUMMARY.json", {"schema_version": "canonical-evidence-inventory-summary-v1", "inventories": summaries})
    return summaries


def load_inventory(experiment_id):
    path = INVENTORY_DIR / "{}.json".format(experiment_id)
    return json.loads(path.read_text(encoding="utf-8"))


def create_archives(selected_ids):
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(str(INTERNAL_ROOT), 0o700)
    results = []
    for item in EVIDENCE:
        if selected_ids and item["experiment_id"] not in selected_ids:
            continue
        inventory = load_inventory(item["experiment_id"])
        root_path = ROOT / item["raw_source_root"]
        archive_path = ARCHIVE_DIR / "{}.tar.zst".format(item["experiment_id"])
        relative_members = ["{}/{}".format(root_path.name, member["path"]) for member in inventory["members"]]
        create_tar_zst(root_path.parent, relative_members, archive_path)
        verification = verify_tar_zst(root_path.parent, relative_members, archive_path, verify_source=True)
        result = {
            "experiment_id": item["experiment_id"],
            "archive_path": archive_path.relative_to(ROOT).as_posix(),
            "archive_byte_count": archive_path.stat().st_size,
            "archive_sha256": sha256_file(archive_path),
            "verification": verification,
        }
        write_json(ARCHIVE_DIR / "{}.verification.json".format(item["experiment_id"]), result)
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)
    return results


def create_archived_evidence_manifest():
    entries = []
    for item in EVIDENCE:
        inventory = load_inventory(item["experiment_id"])
        archive_path = ARCHIVE_DIR / "{}.tar.zst".format(item["experiment_id"])
        verification_path = ARCHIVE_DIR / "{}.verification.json".format(item["experiment_id"])
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        entries.append(
            {
                "experiment_id": item["experiment_id"],
                "experiment_type": item["experiment_type"],
                "raw_source_root": item["raw_source_root"],
                "inventory_path": (INVENTORY_DIR / "{}.json".format(item["experiment_id"])).relative_to(ROOT).as_posix(),
                "archive_filename": archive_path.name,
                "archive_path": archive_path.relative_to(ROOT).as_posix(),
                "archive_sha256": verification["archive_sha256"],
                "archive_byte_count": verification["archive_byte_count"],
                "raw_member_count": inventory["member_count"],
                "raw_byte_count": inventory["raw_byte_count"],
                "canonical_inventory_sha256": inventory["canonical_inventory_sha256"],
                "thesis_claim_relationship": item["claim_relationship"],
                "current_storage_path": archive_path.relative_to(ROOT).as_posix(),
                "internal_archival_destination": "USER_DECISION_REQUIRED",
                "archive_status": "pending_internal_archival",
                "copy_assessment": "Original tree and archive copy currently reside on the same HPC-backed filesystem; they are not independent durable copies.",
                "restoration_test": verification["verification"]["status"],
            }
        )
    payload = {
        "schema_version": "internal-archived-evidence-v1",
        "archive_scope": "Internal university thesis evidence; no public destination is asserted.",
        "allowed_archive_status_values": [
            "current_hpc_only",
            "second_copy_created",
            "pending_internal_archival",
            "internally_archived",
            "verified_internal_archive",
        ],
        "archives": entries,
    }
    write_json(MANIFEST_DIR / "ARCHIVED_EVIDENCE.json", payload)
    return payload


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True
    subparsers.add_parser("capture-state")
    subparsers.add_parser("core-snapshot")
    subparsers.add_parser("inventories")
    archives_parser = subparsers.add_parser("archives")
    archives_parser.add_argument("experiment_ids", nargs="*")
    subparsers.add_parser("archive-manifest")
    args = parser.parse_args()

    if args.command == "capture-state":
        print(json.dumps(capture_pre_cleanup_state(), indent=2, sort_keys=True))
    elif args.command == "core-snapshot":
        print(json.dumps(create_core_snapshot(), indent=2, sort_keys=True))
    elif args.command == "inventories":
        print(json.dumps(create_inventories(), indent=2, sort_keys=True))
    elif args.command == "archives":
        create_archives(set(args.experiment_ids))
    elif args.command == "archive-manifest":
        print(json.dumps(create_archived_evidence_manifest(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
