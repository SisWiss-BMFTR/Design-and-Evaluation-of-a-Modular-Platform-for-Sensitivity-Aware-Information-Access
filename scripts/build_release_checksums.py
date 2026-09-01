#!/usr/bin/env python3
"""Build the internal release/archive SHA-256 checksum file.

The checksum set intentionally covers claim-critical compact evidence, source
manifests, archive inventories, and the externally archived large evidence
packages. Missing external packages retain their already-recorded checksum
bindings; Git-resident files are always hashed from the current tree. It does
not contain caches, raw duplicate trees, or credentials.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "manifests/RELEASE_SHA256SUMS"


def add_file(paths: set[str], relative: str) -> None:
    path = ROOT / relative
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(relative)
    paths.add(relative)


def add_tree(paths: set[str], relative_root: str) -> None:
    base = ROOT / relative_root
    if not base.is_dir():
        raise FileNotFoundError(relative_root)
    for path in base.rglob("*"):
        if path.is_file() and not path.is_symlink():
            paths.add(path.relative_to(ROOT).as_posix())


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def existing_checksums() -> dict[str, str]:
    if not OUTPUT.is_file():
        return {}
    values: dict[str, str] = {}
    for number, line in enumerate(OUTPUT.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError(f"invalid checksum line {number}")
        checksum, relative = match.groups()
        if relative in values:
            raise ValueError(f"duplicate checksum path: {relative}")
        values[relative] = checksum
    return values


def main() -> None:
    previous = existing_checksums()
    paths: set[str] = set()
    external: dict[str, str] = {}
    for relative in (
        "thesis/Design and Evaluation of a Modular Platform for Sensitivity-Aware Information Access.pdf",
        "thesis/final_thesis.pdf",
        "thesis/main.tex",
        "thesis/references.bib",
        "data/SiSWiss_Testdaten.xlsx",
        "sensitivity_policy.yaml",
        "sensitivity_overrides.yaml",
    ):
        add_file(paths, relative)

    for relative_root in (
        "manifests/evidence_inventories",
        "outputs/final_thesis_evidence_20260725",
        "outputs/final_thesis_evidence_20260803_prompt_provenance_v3",
        "outputs/final_thesis_supplemental_evidence_20260803",
        "outputs/final_thesis_supplemental_evidence_20260806",
        "outputs/audits/package_prompt_provenance_a01_a02_20260803",
    ):
        add_tree(paths, relative_root)

    for path in (ROOT / "manifests").glob("*.json"):
        if path.is_file() and not path.is_symlink():
            paths.add(path.relative_to(ROOT).as_posix())

    archive_manifest = json.loads(
        (ROOT / "manifests/ARCHIVED_EVIDENCE.json").read_text(encoding="utf-8")
    )
    for item in archive_manifest["archives"]:
        source_root = ROOT / item["raw_source_root"]
        for path in source_root.iterdir():
            if path.is_file() and not path.is_symlink() and path.name != "replay_corpus.json":
                paths.add(path.relative_to(ROOT).as_posix())
        archive_relative = item["current_storage_path"]
        archive_path = ROOT / archive_relative
        if archive_path.is_file() and not archive_path.is_symlink():
            if digest(archive_path) != item["archive_sha256"]:
                raise ValueError(f"archive checksum mismatch: {archive_relative}")
            paths.add(archive_relative)
        else:
            if previous.get(archive_relative) not in (None, item["archive_sha256"]):
                raise ValueError(f"stale external archive binding: {archive_relative}")
            external[archive_relative] = item["archive_sha256"]

        verification = archive_relative.replace(
            ".tar.zst", ".verification.json"
        )
        verification_path = ROOT / verification
        if verification_path.is_file() and not verification_path.is_symlink():
            paths.add(verification)
        elif verification in previous:
            external[verification] = previous[verification]
        else:
            raise FileNotFoundError(verification)

    # Source binding is stored in matched experiment manifests and in explicit
    # source manifests for later supplemental studies.
    for item in archive_manifest["archives"]:
        source_root = ROOT / item["raw_source_root"]
        for name in ("experiment_manifest.json", "source_manifest.json", "freeze_manifest.json"):
            path = source_root / name
            if path.is_file():
                paths.add(path.relative_to(ROOT).as_posix())

    if paths & external.keys():
        raise ValueError("local and external checksum paths overlap")
    checksums = {relative: digest(ROOT / relative) for relative in paths}
    checksums.update(external)
    lines = [f"{checksums[relative]}  {relative}" for relative in sorted(checksums)]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"{OUTPUT.relative_to(ROOT)}: {len(lines)} entries "
        f"({len(paths)} local, {len(external)} external)"
    )


if __name__ == "__main__":
    main()
