#!/usr/bin/env python3
"""Validate the two-source Chapters 5--9 thesis against package evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "outputs/final_thesis_evidence_20260725/metrics.json"
CHAPTERS = ROOT / "thesis/chapters"
FIGURES = ROOT / "thesis/figures/results"
LOG = ROOT / "thesis/build-two-source/main.log"
PDF = ROOT / "thesis/final_thesis_chapters_5_9_two_source.pdf"
REPORT = ROOT / "outputs/final_thesis_evidence_20260725/two_source_consistency_check.json"
MODES = ("secure_rag_mode", "sensitivity_eval_mode")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(text: str, token: str, reason: str, checks: list[dict[str, str]]) -> None:
    if token not in text:
        raise AssertionError(f"Missing {token!r}: {reason}")
    checks.append({"status": "pass", "check": reason, "token": token})


def reject(text: str, pattern: str, reason: str, checks: list[dict[str, str]]) -> None:
    if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
        raise AssertionError(reason)
    checks.append({"status": "pass", "check": reason, "token": pattern})


def main() -> None:
    data = json.loads(METRICS.read_text(encoding="utf-8"))
    baseline = data["descriptive_baseline"]
    hardened = data["descriptive_hardened_package"]
    chapter_text = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(CHAPTERS.glob("chapter0[5-9]_*.tex"))
    }
    text = "\n".join(chapter_text.values())
    checks: list[dict[str, str]] = []

    # Corrected A02 metrics must remain primary.
    for mode in MODES:
        require(text, f"{baseline['A02'][mode]['primary']}/150", f"A02 policy-aware baseline leakage: {mode}", checks)
        require(text, f"{hardened['A02'][mode]['primary']}/150", f"A02 policy-aware hardened leakage: {mode}", checks)
    require(text, f"{baseline['A02']['sensitivity_eval_mode']['full']}/150", "A02 policy-aware full reconstruction", checks)
    require(text, "The legacy runner flags were 60/150 and 122/150, but these are retained only as diagnostic values.", "A02 legacy flags remain diagnostic", checks)

    # Both package stages must be represented for directly comparable attack families.
    for attack in ("A01", "A02", "A03", "A04", "A05", "A06", "A08"):
        for mode in MODES:
            require(text, f"{baseline[attack][mode]['primary']}/150", f"{attack} original primary outcome: {mode}", checks)
            require(text, f"{hardened[attack][mode]['primary']}/150", f"{attack} hardened primary outcome: {mode}", checks)

    # A07 must be variant-aware, never a controlled reduction.
    require(text, "Synthetic trigger", "A07 original variant identified", checks)
    require(text, "Natural-style request", "A07 hardened variant identified", checks)
    require(text, "do not constitute a controlled before--after comparison", "A07 non-comparability stated", checks)
    reject(text, r"A07.{0,180}(?:reduced|changed|fell|dropped).{0,80}150/150.{0,80}0/150", "A07 is not presented as a controlled reduction", checks)

    # Utility aggregates are derived only from the two package matrices.
    for label, source in (("original", baseline), ("hardened", hardened)):
        for mode in MODES:
            value = sum(source[attack][mode]["positive_control"] for attack in source)
            require(text, f"{value}/600", f"{label} aggregate protected utility: {mode}", checks)
            value_without_a07 = sum(
                source[attack][mode]["positive_control"]
                for attack in source
                if attack != "A07"
            )
            require(text, f"{value_without_a07}/525", f"{label} protected utility excluding A07: {mode}", checks)

    # Correction experiments and their figures must be absent from the main text.
    forbidden = {
        r"guards[- ]off": "no guards-off evidence in Chapters 5--9",
        r"guards[- ]on": "no guards-on evidence in Chapters 5--9",
        r"A07-S|A07-N": "no correction-family identifiers in Chapters 5--9",
        r"methodology_correction|methodology correction": "no methodology-correction source in Chapters 5--9",
        r"correction telemetry|correction experiment|correction run": "no correction-run evidence in Chapters 5--9",
        r"matched prompt hash|prompt hashes matched": "no matched-prompt correction evidence in Chapters 5--9",
        r"guard_path_telemetry|a07_family_guard_ablation|a05_membership_evidence_sets": "no correction-derived figures in Chapters 5--9",
        r"over-broad membership detector handled direct extraction": "no unsupported component attribution in Chapter 8",
        r"neutral pre-hardening runner|neutral pre-hardening condition": "no residual neutral terminology in prose",
    }
    for pattern, reason in forbidden.items():
        reject(text, pattern, reason, checks)

    chapter6 = chapter_text["chapter06_results.tex"]
    reject(chapter6, r"hardened.{0,40}(?:0|[1-9][0-9]*)/(?:75|150)", "Chapter 6 contains no hardened-package values", checks)
    reject(chapter6, r"guards?[- ](?:off|on)|ablation|A07-S|A07-N", "Chapter 6 contains no component-study values", checks)

    expected_figures = {
        "a01_exposure_delivery",
        "a02_policy_aware_reconstruction",
        "a03_state_delivery",
        "a04_relation_structure",
        "a05_membership_baseline",
        "a06_integrity_confidentiality",
        "a07_baseline_integrity_confidentiality_utility",
        "a08_exposure_delivery",
        "cross_attack_descriptive_baseline",
        "cross_attack_package_comparison",
        "cross_attack_utility",
    }
    for stem in sorted(expected_figures):
        for suffix in (".pdf", ".png"):
            path = FIGURES / f"{stem}{suffix}"
            if not path.is_file() or path.stat().st_size == 0:
                raise AssertionError(f"Missing generated figure: {path}")
        checks.append({"status": "pass", "check": f"generated figure {stem}", "token": stem})

    if LOG.exists():
        log_text = LOG.read_text(encoding="utf-8", errors="replace")
        reject(log_text, r"Overfull \\\\hbox", "compiled layout has no overfull hbox", checks)
        reject(log_text, r"Undefined control sequence|LaTeX Error|Emergency stop|Fatal error", "compiled thesis has no TeX error", checks)

    artifacts = [ROOT / "thesis/main.tex", *[CHAPTERS / name for name in sorted(chapter_text)], METRICS]
    if PDF.exists():
        artifacts.append(PDF)
    REPORT.write_text(
        json.dumps(
            {
                "status": "pass",
                "checks": checks,
                "artifact_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in artifacts},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(REPORT)


if __name__ == "__main__":
    main()
