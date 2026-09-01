#!/usr/bin/env python3
"""Build exact proposed-Git and internal-archive classification lists.

The script is read-only except for the four requested root-level list files.  It
does not alter the Git index.  Large raw roots and credential symlinks are
deliberately excluded from the proposed Git file list.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]

COMMIT_LIST = ROOT / "files_to_commit.txt"
ARCHIVE_LIST = ROOT / "files_to_internal_archive.txt"
EXCLUDE_LIST = ROOT / "files_to_exclude.txt"
DECISION_LIST = ROOT / "files_requiring_user_decision.txt"


TRACKED_EXCLUSIONS = (
    "jobs/",
    "logs/",
)
TRACKED_EXACT_EXCLUSIONS = {"rag-master-thesis.code-workspace"}

RAW_GIT_EXCLUSIONS = (
    "/arm_A_",
    "/arm_B_",
    "/raw_generation/",
    "/full/",
    "/pilot/",
)


def git_tracked() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    }


def excluded_tracked(relative: str) -> bool:
    if relative in TRACKED_EXACT_EXCLUSIONS:
        return True
    if relative.startswith(TRACKED_EXCLUSIONS):
        return True
    if relative.startswith("thesis/chapter") and relative.endswith("_revision_report.md"):
        return True
    name = Path(relative).name
    return len(Path(relative).parts) == 1 and name.startswith("slurm-") and name.endswith((".out", ".err"))


def add_tree(paths: set[str], relative_root: str) -> None:
    base = ROOT / relative_root
    if not base.exists():
        raise FileNotFoundError(relative_root)
    for path in sorted(base.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.name == ".env":
            continue
        if relative.startswith(("thesis/build", "thesis/outputs/")):
            continue
        if relative.startswith("thesis/chapter") and relative.endswith("_revision_report.md"):
            continue
        if relative.startswith("thesis/") and path.suffix in {
            ".aux",
            ".bbl",
            ".bcf",
            ".blg",
            ".fls",
            ".lof",
            ".log",
            ".lot",
            ".out",
            ".toc",
        }:
            continue
        if any(marker in f"/{relative}/" for marker in RAW_GIT_EXCLUSIONS):
            continue
        paths.add(relative)


def write_lines(path: Path, values: list[str] | set[str]) -> None:
    path.write_text("\n".join(sorted(values)) + "\n", encoding="utf-8")


def main() -> None:
    proposed = {
        relative
        for relative in git_tracked()
        if (ROOT / relative).is_file() and not excluded_tracked(relative)
    }

    for relative_root in ("data", "docs", "manifests", "thesis"):
        add_tree(proposed, relative_root)

    for relative in (
        ".env.example",
        ".gitignore",
        "README.md",
        "requirements.txt",
        "sensitivity_overrides.yaml",
        "sensitivity_policy.yaml",
        "scripts/build_figure_table_provenance.py",
        "scripts/build_internal_staging_lists.py",
        "scripts/build_release_checksums.py",
        "scripts/audit_internal_candidate_secrets.py",
        "scripts/internal_archive_tools.py",
        "files_to_commit.txt",
        "files_to_internal_archive.txt",
        "files_to_exclude.txt",
        "files_requiring_user_decision.txt",
    ):
        if relative.startswith("files_") or (ROOT / relative).is_file():
            proposed.add(relative)

    archive_manifest = json.loads(
        (ROOT / "manifests/ARCHIVED_EVIDENCE.json").read_text(encoding="utf-8")
    )
    for item in archive_manifest["archives"]:
        add_tree(proposed, item["raw_source_root"])

    # The successful development pilot is explicitly labelled as a pilot in the
    # evidence ledger. Preserve its compact metadata/source snapshot, not raw
    # generations. Its failed predecessor remains outside the proposed Git tree.
    add_tree(
        proposed,
        "outputs/experiments/verifier_challenge_pilot/VCP_A01_A02_20260803T024529Z",
    )
    pilot_prefix = (
        "outputs/experiments/verifier_challenge_pilot/"
        "VCP_A01_A02_20260803T024529Z/source_snapshot/"
    )
    proposed = {
        relative
        for relative in proposed
        if not (
            relative.startswith(pilot_prefix)
            and ("/__pycache__/" in relative or relative.endswith(".pyc"))
        )
    }

    # This compact cross-source consistency result was previously hidden by a
    # local exclude rule and is part of the final evidence map.
    proposed.add(
        "outputs/final_thesis_evidence_20260725/two_source_consistency_check.json"
    )

    # Scheduler receipts associated with the authoritative historical baseline
    # are small and claim-relevant.
    add_tree(
        proposed,
        "outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719/slurm",
    )

    # Explicitly exclude every unmanifested credential symlink even if a future
    # filesystem traversal changes its file-type treatment.
    proposed = {
        relative
        for relative in proposed
        if not (
            relative.endswith("/source_snapshot/.env")
            or relative == ".env"
            or relative
            == "outputs/verifier_validation/a01_a02_replay_v1_20260803/replay_corpus.json"
        )
    }
    write_lines(COMMIT_LIST, proposed)

    archive_patterns: list[str] = [
        "internal_archive/thesis_evidence_20260823/archives/*.tar.zst",
        "internal_archive/thesis_evidence_20260823/archives/*.verification.json",
        "internal_archive/thesis_evidence_20260823/pre_cleanup/**",
        "outputs/deliverables/**",
        "outputs/experiments/matched_single_guard_ablations/*/arm_A_*/**",
        "outputs/experiments/matched_single_guard_ablations/*/arm_B_*/**",
        "outputs/experiments/full_a02_verifier_challenge/*/raw_generation/**",
        "outputs/experiments/matched_a07s_prompt_injection_guard/*/arm_A_injection_guard_off/**",
        "outputs/experiments/matched_a07s_prompt_injection_guard/*/arm_B_injection_guard_on/**",
        "outputs/experiments/supplemental_a06_poisoned_row/*/full/**",
        "outputs/experiments/supplemental_a06_poisoned_row/*/pilot/**",
        "outputs/verifier_validation/a01_a02_replay_v1_20260803/replay_corpus.json",
        "outputs/experiments/verifier_challenge_pilot/*/raw_generation/**",
        "outputs/experiments/verifier_challenge_pilot/VCP_A01_A02_20260803T024445Z/**  # FAILED",
        "outputs/experiments/matched_single_guard_ablations/E04_A04_relation_access_guard_20260728T003704Z/**  # SUPERSEDED",
        "outputs/experiments/matched_single_guard_ablations/E06_A06_prompt_injection_guard_20260728T162318Z/**  # SUPERSEDED",
        "outputs/experiments/matched_single_guard_ablations/E06_A06_prompt_injection_guard_neutral_20260801T160000Z/**  # SUPERSEDED",
        "outputs/experiments/matched_single_guard_ablations/E08_A08_embedding_probe_guard_20260729T084534Z/**  # SUPERSEDED",
        "outputs/final_thesis_evidence_20260802_corrected_no_rerun/**  # SUPERSEDED",
        "outputs/final_thesis_evidence_20260802_no_rerun_revision*/**  # SUPERSEDED",
        "outputs/nonrun_archives/**",
        "logs/**  # DESCRIPTIVE_HISTORICAL",
    ]
    write_lines(ARCHIVE_LIST, archive_patterns)

    exclude_patterns: list[str] = [
        ".env",
        ".env.*",
        "!/.env.example",
        "**/source_snapshot/.env",
        "env/**",
        ".venv/**",
        "venv/**",
        "**/__pycache__/**  # except manifest-bound source-snapshot bytecode",
        "*.py[cod]  # except manifest-bound source-snapshot bytecode",
        ".pytest_cache/**",
        "models/**",
        "*.safetensors",
        ".vscode/**",
        ".idea/**",
        "*.code-workspace",
        "jobs/**  # unrelated Qwen development orchestration",
        "logs/**  # superseded root-level descriptive results; originals retained",
        "reports/**",
        "writing/**",
        "reference_materials/**",
        "slurm-*.out",
        "slurm-*.err",
        "thesis/build*/**",
        "thesis/outputs/**",
        "thesis/chapter*_revision_report.md",
        "outputs/audits/final_project_review_*/**",
        "outputs/audits/final_style_review_*/**",
        "outputs/audits/final_supervised_revision_*/**",
        "outputs/audits/style_revision_batch*/**",
        "outputs/deliverables/**  # authoritative copies are the two final PDFs under thesis/",
        "outputs/nonrun_archives/**",
        "outputs/experiments/matched_single_guard_ablations/*/arm_A_*/**",
        "outputs/experiments/matched_single_guard_ablations/*/arm_B_*/**",
        "outputs/experiments/full_a02_verifier_challenge/*/raw_generation/**",
        "outputs/experiments/matched_a07s_prompt_injection_guard/*/arm_A_injection_guard_off/**",
        "outputs/experiments/matched_a07s_prompt_injection_guard/*/arm_B_injection_guard_on/**",
        "outputs/experiments/supplemental_a06_poisoned_row/*/full/**",
        "outputs/experiments/supplemental_a06_poisoned_row/*/pilot/**",
        "outputs/verifier_validation/a01_a02_replay_v1_20260803/replay_corpus.json",
        "outputs/experiments/verifier_challenge_pilot/*/raw_generation/**",
        "outputs/experiments/verifier_challenge_pilot/VCP_A01_A02_20260803T024445Z/**",
        "outputs/final_thesis_evidence_20260802_corrected_no_rerun/**",
        "outputs/final_thesis_evidence_20260802_no_rerun_revision*/**",
        "internal_archive/**",
    ]
    write_lines(EXCLUDE_LIST, exclude_patterns)

    decisions: list[str] = [
        "EXTERNAL_ARCHIVE_ACCESS\tAdministratively confirm that the documented Google Drive archive remains restricted to authorized university reviewers; repository-local checks do not independently verify Drive sharing permissions.",
        "INTERNAL_LICENSE\tConfirm whether university policy requires a software or dataset license for the internal repository; none was invented.",
        "LEGACY_RETENTION\tConfirm whether the small already-tracked historical experiment/evidence bundles should remain as labelled legacy; the proposed list retains them for provenance completeness.",
        "PRIVATE_PATH_DISCLOSURE\tConfirm that authorized reviewers may receive immutable historical patches/logs/ledgers containing HPC-private absolute paths; PATH_MAPPINGS.json documents them.",
        "OLD_DELIVERABLE_RETENTION\tChoose the private retention period for old/non-authoritative thesis PDFs and prior LaTeX packages under outputs/deliverables; they are excluded from normal Git and were not deleted.",
    ]
    write_lines(DECISION_LIST, decisions)

    print(f"proposed Git files: {len(proposed)}")


if __name__ == "__main__":
    main()
