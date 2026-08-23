#!/usr/bin/env python3
"""Audit the exact proposed internal Git tree without disclosing secret values."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "files_to_commit.txt"
HISTORY_PATHS = (
    ROOT
    / "internal_archive/thesis_evidence_20260823/"
    "git_history_high_confidence_secret_paths.txt"
)
OUTPUT = ROOT / "manifests/SECRET_PRIVACY_SCAN.json"

HIGH_PATTERNS = {
    "openai_key": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "private_key_header": re.compile(
        rb"BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY"
    ),
}
REFERENCE_PATTERNS = {
    "credential_variable_name": re.compile(
        rb"\b(?:OPENAI_API_KEY|API_KEY|ACCESS_TOKEN|PASSWORD|SECRET|PRIVATE_KEY)\b",
        re.IGNORECASE,
    ),
    "env_filename_reference": re.compile(rb"(?:^|[/\\])\.env(?:\b|$)"),
    "authentication_artifact_reference": re.compile(
        rb"\b(?:credentials?|cookies?|shell history|ssh data)\b", re.IGNORECASE
    ),
}
PRIVATE_PATH_PATTERNS = {
    "hpc_mnt_vast_path": re.compile(rb"/mnt/vast/"),
    "private_user_path": re.compile(rb"/(?:user|home)/[A-Za-z0-9._-]+/"),
    "hpc_file_uri": re.compile(rb"file:///+(?:mnt/vast|user|home)/"),
    "vscode_remote_state": re.compile(rb"(?:vscode-remote|\.vscode-server)"),
}
SIGNED_URL = re.compile(
    rb"https?://[^\s\"'<>]+[?&](?:X-Amz-Signature|Signature|sig|token|access_token)=",
    re.IGNORECASE,
)

ALLOWED_BINARY_SUFFIXES = {".pdf", ".png", ".xlsx", ".pyc"}
PLACEHOLDER_MARKERS = (
    b"placeholder",
    b"your",
    b"example",
    b"dummy",
    b"test",
    b"xxxx",
    b"abcdef",
    b"openai-key",
    b"openai_key",
)


def live_key() -> bytes | None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_bytes().splitlines():
        if line.startswith(b"OPENAI_API_KEY="):
            return line.split(b"=", 1)[1].strip().strip(b"\"'")
    return None


def placeholder(token: bytes) -> bool:
    lowered = token.lower()
    body = token[3:].replace(b"-", b"").replace(b"_", b"")
    return any(item in lowered for item in PLACEHOLDER_MARKERS) or len(set(body)) <= 4


def read_candidate() -> list[str]:
    values = [line for line in CANDIDATE.read_text(encoding="utf-8").splitlines() if line]
    if len(values) != len(set(values)):
        raise RuntimeError("candidate file list contains duplicates")
    for relative in values:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"invalid candidate file: {relative}")
    return values


def scan_candidate(values: list[str], current_live_key: bytes | None) -> dict[str, object]:
    high: list[dict[str, object]] = []
    references: dict[str, Counter[str]] = {
        category: Counter() for category in REFERENCE_PATTERNS
    }
    private_paths: dict[str, Counter[str]] = {
        category: Counter() for category in PRIVATE_PATH_PATTERNS
    }
    signed_urls: Counter[str] = Counter()
    binary_files: list[dict[str, object]] = []

    for relative in values:
        path = ROOT / relative
        data = path.read_bytes()
        for category, pattern in HIGH_PATTERNS.items():
            matches = pattern.findall(data)
            if not matches:
                continue
            actual = 0
            placeholder_count = 0
            live_matches = 0
            for match in matches:
                token = match if isinstance(match, bytes) else match[0]
                if category == "openai_key" and placeholder(token):
                    placeholder_count += 1
                else:
                    actual += 1
                if current_live_key and token == current_live_key:
                    live_matches += 1
            if actual:
                high.append(
                    {
                        "path": relative,
                        "category": category,
                        "severity": "CRITICAL",
                        "actual_looking_match_count": actual,
                        "matches_current_live_key": bool(live_matches),
                    }
                )
            if placeholder_count:
                references.setdefault("placeholder_key", Counter())[relative] += placeholder_count

        for category, pattern in REFERENCE_PATTERNS.items():
            count = len(pattern.findall(data))
            if count:
                references[category][relative] += count
        for category, pattern in PRIVATE_PATH_PATTERNS.items():
            count = len(pattern.findall(data))
            if count:
                private_paths[category][relative] += count
        signed_count = len(SIGNED_URL.findall(data))
        if signed_count:
            signed_urls[relative] += signed_count

        is_binary = b"\0" in data[:8192]
        if is_binary:
            binary_files.append(
                {
                    "path": relative,
                    "size": len(data),
                    "suffix": path.suffix.lower(),
                    "expected_scientific_binary": path.suffix.lower()
                    in ALLOWED_BINARY_SUFFIXES,
                }
            )

    def counters(document: dict[str, Counter[str]]) -> list[dict[str, object]]:
        rows = []
        for category, counts in sorted(document.items()):
            for path, count in sorted(counts.items()):
                rows.append({"path": path, "category": category, "match_count": count})
        return rows

    return {
        "status": "PASS" if not high and not signed_urls else "FAIL",
        "high_confidence_secret_findings": high,
        "credential_and_authentication_references": counters(references),
        "private_path_references": counters(private_paths),
        "signed_url_candidates": [
            {"path": path, "category": "signed_url", "match_count": count}
            for path, count in sorted(signed_urls.items())
        ],
        "binary_files": binary_files,
        "unexpected_binary_files": [
            item for item in binary_files if not item["expected_scientific_binary"]
        ],
    }


def scan_recorded_history(current_live_key: bytes | None) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    placeholders: list[dict[str, object]] = []
    unique_actual: set[bytes] = set()
    unique_placeholder: set[bytes] = set()
    for line in HISTORY_PATHS.read_text(encoding="utf-8").splitlines():
        commit, path = line.split("\t", 1)
        data = subprocess.check_output(
            ["git", "show", f"{commit}:{path}"], cwd=ROOT, stderr=subprocess.DEVNULL
        )
        for token in HIGH_PATTERNS["openai_key"].findall(data):
            if placeholder(token):
                unique_placeholder.add(token)
                placeholders.append(
                    {
                        "commit": commit,
                        "path": path,
                        "category": "placeholder_openai_key",
                        "severity": "INFORMATIONAL",
                    }
                )
            else:
                unique_actual.add(token)
                findings.append(
                    {
                        "commit": commit,
                        "path": path,
                        "category": "openai_key",
                        "severity": "CRITICAL",
                        "matches_current_live_key": bool(
                            current_live_key and token == current_live_key
                        ),
                    }
                )
    return {
        "status": "FAIL_CREDENTIALS_PRESENT_IN_HISTORY" if findings else "PASS",
        "commit_count_scanned": int(
            subprocess.check_output(["git", "rev-list", "--all", "--count"], cwd=ROOT)
        ),
        "high_confidence_findings": findings,
        "high_confidence_occurrence_count": len(findings),
        "distinct_actual_looking_key_count": len(unique_actual),
        "placeholder_occurrence_count": len(placeholders),
        "distinct_placeholder_count": len(unique_placeholder),
        "env_history": {
            "dot_env_ever_tracked": bool(
                subprocess.check_output(
                    ["git", "log", "--all", "--format=%H", "--", ".env"], cwd=ROOT
                ).strip()
            ),
            "dot_env_example_history_contains_live_key": any(
                item["path"] == ".env.example" and item["matches_current_live_key"]
                for item in findings
            ),
        },
        "history_rewrite_recommendation": (
            "RECOMMENDED_AFTER_ROTATION_AND_COORDINATION; not performed by this task. "
            "If the remote is shared, coordinate invalidation/re-cloning before rewriting."
            if findings
            else "NOT_RECOMMENDED"
        ),
    }


def main() -> None:
    values = read_candidate()
    key = live_key()
    env_path = ROOT / ".env"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".env"], cwd=ROOT, check=False
    ).returncode == 0
    remote = subprocess.check_output(
        ["git", "config", "--get", "remote.origin.url"], cwd=ROOT, text=True
    ).strip()
    parsed_remote = urlsplit(remote)
    candidate_result = scan_candidate(values, key)
    history_result = scan_recorded_history(key)
    mode = stat.S_IMODE(os.stat(env_path).st_mode) if env_path.exists() else None
    document = {
        "schema_version": "internal-thesis-secret-privacy-scan-v1",
        "overall_status": (
            "ACTION_REQUIRED_GIT_HISTORY"
            if history_result["status"] != "PASS"
            else candidate_result["status"]
        ),
        "disclosure_rule": "No secret values, matching lines, or secret digests are recorded.",
        "candidate_tree": {
            "file_list": "files_to_commit.txt",
            "file_count": len(values),
            **candidate_result,
        },
        "env": {
            "path": ".env",
            "exists": env_path.is_file(),
            "live_openai_credential_present": bool(key),
            "permissions_octal": f"{mode:03o}" if mode is not None else None,
            "owner_only": mode == 0o600,
            "ignored_by_git": ignored,
            "included_in_candidate_tree": ".env" in values,
        },
        "git_history": history_result,
        "remote": {
            "scheme": parsed_remote.scheme,
            "host": parsed_remote.hostname,
            "embedded_userinfo": bool(parsed_remote.username or parsed_remote.password),
        },
        "rotation_recommendation": (
            "YES. Revoke/rotate both actual-looking keys found in history, including "
            "the current .env key. Rotation was not performed."
        ),
    }
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))
    print("candidate_status=" + str(candidate_result["status"]))
    print("history_status=" + str(history_result["status"]))


if __name__ == "__main__":
    main()
