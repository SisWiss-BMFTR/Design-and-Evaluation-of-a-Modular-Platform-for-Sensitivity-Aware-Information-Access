#!/usr/bin/env python3
"""Build the internal release/archive SHA-256 checksum file.

The checksum set intentionally covers claim-critical compact evidence, source
manifests, archive inventories, and the locally available large archives. It
does not contain caches, raw duplicate trees, or credentials.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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


def main() -> None:
    paths: set[str] = set()
    for relative in (
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
        add_file(paths, item["current_storage_path"])
        verification = item["current_storage_path"].replace(
            ".tar.zst", ".verification.json"
        )
        add_file(paths, verification)

    # Source binding is stored in matched experiment manifests and in explicit
    # source manifests for later supplemental studies.
    for item in archive_manifest["archives"]:
        source_root = ROOT / item["raw_source_root"]
        for name in ("experiment_manifest.json", "source_manifest.json", "freeze_manifest.json"):
            path = source_root / name
            if path.is_file():
                paths.add(path.relative_to(ROOT).as_posix())

    lines = [f"{digest(ROOT / relative)}  {relative}" for relative in sorted(paths)]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)}: {len(lines)} entries")


if __name__ == "__main__":
    main()
