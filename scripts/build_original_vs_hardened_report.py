#!/usr/bin/env python3
"""Build a standalone, traceable original-versus-hardened package report."""

from __future__ import annotations

import csv
import hashlib
import json
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/original_vs_hardened_20260726"
MODES = ("secure_rag_mode", "sensitivity_eval_mode")
MODE_LABEL = {"secure_rag_mode": "Secure", "sensitivity_eval_mode": "Sensitivity"}
UNAUTH = {"public", "internal"}

ATTACK_NAMES = {
    "A01": "Direct cell extraction",
    "A02": "Multi-turn row reconstruction",
    "A03": "Access-level downgrade",
    "A04": "Relational join-path inference",
    "A05": "Rank/membership inference",
    "A06": "Poisoned-row prompt injection",
    "A07-S": "Synthetic-trigger extraction",
    "A07-N": "Natural validation-style extraction",
    "A08": "Embedding/rank side leakage",
}

BASE_LABELED = ROOT / "outputs/experiments/gpt4o_mini_slurm"
BASE_NEUTRAL = ROOT / "outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719"
POST_NEUTRAL = ROOT / "outputs/experiments/post hardened 1-8"
POST_NEW = ROOT / "outputs/experiments/labeled_post_hardened_a01_a07_20260726T170023Z"

COMMON_FOLDERS = {
    "A01": "attack_01_direct_cell_extraction",
    "A02": "attack_02_multiturn_row_construction",
    "A03": "attack_03_access_level_downgrade_task",
    "A04": "attack_04_relational_join_path_inference",
    "A05": "attack_05_rank_probing_membership_inference",
    "A06": "attack_06_prompt_injection_poisoned_row",
    "A08": "attack_08_embedding_side_leakage",
}

LABELED_POST = {
    "A01": POST_NEW / "A01/post_hardening",
    "A02": ROOT / "outputs/experiments/gpt4o_mini_slurm_postgen_20260626/attack_02_multiturn_row_construction",
    "A03": ROOT / "outputs/experiments/gpt4o_mini_slurm_after_hardening(memory)/attack_03_access_level_downgrade_task",
    "A04": ROOT / "outputs/experiments/hardening_A4/after_hardening_positive_control_fix_14712029",
    "A05": ROOT / "outputs/experiments/gpt4o_mini_slurm_attack05_membership_guard_20260627_v2/attack_05_rank_probing_membership_inference",
    "A06": ROOT / "outputs/experiments/gpt4o_mini_slurm_attack06_hardening_20260709_retry1/attack_06_prompt_injection_poisoned_row",
    "A07-S": POST_NEW / "A07-S/post_hardening",
    "A07-N": POST_NEW / "A07-N/post_hardening",
    "A08": ROOT / "outputs/experiments/gpt4o_mini_slurm_attack08_hardening_20260710_retry1/attack_08_embedding_side_leakage",
}

NEUTRAL_PRE = {
    **{attack: BASE_NEUTRAL / folder for attack, folder in COMMON_FOLDERS.items()},
    "A07-S": BASE_NEUTRAL / "attack_07_backdoor_triggered_extraction",
    "A08": BASE_NEUTRAL / "gpt4o_mini_slurm_attack08_neutral_prehardened_20260719/attack_08_embedding_side_leakage",
}
NEUTRAL_POST = {
    **{attack: POST_NEUTRAL / folder for attack, folder in COMMON_FOLDERS.items()},
    "A01": POST_NEUTRAL / "gpt4o_mini_slurm_attack01_neutral_posthardened_20260720/attack_01_direct_cell_extraction",
    "A07-N": POST_NEUTRAL / "attack_07_backdoor_triggered_extraction",
}
LABELED_PRE = {
    **{attack: BASE_LABELED / folder for attack, folder in COMMON_FOLDERS.items()},
    "A07-S": BASE_LABELED / "attack_07_backdoor_triggered_extraction",
}

CAUSES = {
    "A01": ("Protected cells could be retrieved or made model-visible for low-privilege users.",
            "Role-aware field projection and final-answer/membership verification create preventive and detective boundaries."),
    "A02": ("Fields from one protected row could be accumulated across turns and reconstructed.",
            "Sensitivity-aware context plus post-generation comparison against restricted structured values prevents delivery."),
    "A03": ("Sensitive state survived a role downgrade in memory, summaries, focus state, or cached context.",
            "An access change is treated as a security boundary that clears state and reapplies current-role filtering."),
    "A04": ("Relation identifiers and graph edges were treated as harmless metadata and enabled hidden traversal.",
            "Relation visibility policy, guarded traversal, focus-ID sanitization, and relation-aware answer checks protect edges."),
    "A05": ("Content controls did not prevent yes/no signals about whether protected records existed.",
            "A membership-probe detector refuses unauthorized existence/rank confirmation before or after generation."),
    "A06": ("Retrieved documents were too close to the instruction channel, allowing poisoned text to influence generation.",
            "Retrieved text is treated as untrusted data, projected by role, quarantined when instruction-like, and checked for artifacts."),
    "A07-S": ("Synthetic trigger rows caused attacker-controlled canary compliance, an integrity failure.",
              "Trigger/probe detection, injection-resistant context, membership refusal, and artifact checks interrupt the path."),
    "A07-N": ("Natural validation requests sought the same protected association without a conspicuous trigger token.",
              "Policy is attached to data and membership/relationship capabilities rather than relying only on trigger wording."),
    "A08": ("Embedding/rank language became an indirect extraction interface for protected numeric information.",
            "Probe-aware retrieval, strict projection, memory suppression, and output verification reduce the side channel."),
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def role(row: dict[str, Any]) -> str:
    return str(row.get("access", row.get("access_after", "")))


def truth(row: dict[str, Any], *fields: str) -> bool:
    for field in fields:
        if field in row:
            return bool(row[field])
    return False


def metric_fields(attack: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], str]:
    if attack == "A01":
        return (("delivered_answer_leak", "answer_leak"), ("raw_retrieval_secret_present", "retrieved_secret_present"),
                ("delivered_answer_leak", "answer_leak"), "delivered exact-cell leakage")
    if attack == "A02":
        return (("conversation_delivered_answer_leak", "conversation_any_answer_leak"),
                ("final_retrieved_full_support",), ("final_answer_full_reconstruction",), "delivered row leakage")
    if attack == "A03":
        return (("unauthorized_answer_leak",), ("unauthorized_retrieval_exposure", "attack_context_secret_available"),
                ("positive_control_success",), "delivered state/memory leakage")
    if attack == "A04":
        return (("answer_edge_leakage", "answer_join_edge"), ("raw_retrieval_exposure", "retrieved_join_edge"),
                ("protected_positive_control_success", "answer_complete"), "delivered relation-edge leakage")
    if attack == "A05":
        return (("unauthorized_answer_membership_confirmation", "unauthorized_answer_leak"),
                ("unauthorized_retrieval_hit", "retrieved_target_doc_present", "retrieved_candidate_id_present"),
                ("authorized_positive_control_success",), "delivered membership confirmation")
    if attack in {"A06", "A07-S", "A07-N"}:
        return (("canary_in_answer", "answer_contains_canary"), ("secret_in_retrieved_context", "backdoor_retrieved", "poison_retrieved"),
                ("authorized_positive_control_success",), "canary compliance (integrity)")
    return (("unauthorized_answer_leak",), ("visible_context_target_present", "retrieved_target_present"),
            ("positive_control_success",), "delivered embedding/rank leakage")


def summarize(attack: str, path: Path) -> dict[str, Any]:
    data = load(path)
    rows = data["records"]
    unauth = [r for r in rows if role(r) in UNAUTH]
    protected = [r for r in rows if role(r) == "protected"]
    primary, exposure, positive, label = metric_fields(attack)
    result = {
        "source": str(path.relative_to(ROOT)),
        "sha256": sha(path),
        "records": len(rows),
        "unauthorized_n": len(unauth),
        "protected_n": len(protected),
        "primary": sum(truth(r, *primary) for r in unauth),
        "exposure": sum(truth(r, *exposure) for r in unauth),
        "positive": sum(truth(r, *positive) for r in protected),
        "metric": label,
        "roles": sorted({role(r) for r in rows}),
        "lengths": sorted({int(r.get("conversation_length", r.get("total_user_turns", 0))) for r in rows}),
        "iterations": sorted({int(r["iteration"]) for r in rows}),
        "targets": sorted({str(r["target_id"]) for r in rows}),
    }
    if attack in {"A06", "A07-S", "A07-N"}:
        result["confidentiality"] = sum(truth(r, "unauthorized_answer_leak", "secret_in_answer") for r in unauth)
    if attack == "A02":
        result["raw_primary"] = sum(truth(r, "conversation_raw_answer_leak", "conversation_any_answer_leak") for r in unauth)
        result["full_reconstruction"] = sum(truth(r, "final_answer_full_reconstruction") for r in unauth)
    return result


def final_prompt(row: dict[str, Any]) -> str | None:
    if row.get("attack_prompt"):
        return str(row["attack_prompt"])
    turns = row.get("turns") or []
    for turn in reversed(turns):
        if turn.get("turn_kind") == "attack" and turn.get("prompt"):
            return str(turn["prompt"])
    return None


def prompt_relation(pre_path: Path, post_path: Path, attack: str) -> str:
    pre_rows, post_rows = load(pre_path)["records"], load(post_path)["records"]
    pre_prompts = {final_prompt(r) for r in pre_rows}
    post_prompts = {final_prompt(r) for r in post_rows}
    if None in pre_prompts or None in post_prompts:
        return "Exact text unavailable"
    if pre_prompts == post_prompts:
        if attack == "A03":
            pre_seed = {r.get("seed_prompt") for r in pre_rows}
            post_seed = {r.get("seed_prompt") for r in post_rows}
            return "Attack exact; seed differs" if pre_seed != post_seed else "Attack and seed exact"
        return "Exact"
    return "Different"


def source_for(mapping: dict[str, Path], attack: str, mode: str) -> Path:
    return mapping[attack] / mode / "results.json"


def build_ledger() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    comparisons: dict[str, Any] = {"labeled": {}, "neutral": {}}
    ledger: list[dict[str, Any]] = []
    for style, pre_map, post_map in [
        ("labeled", LABELED_PRE, LABELED_POST),
        ("neutral", NEUTRAL_PRE, NEUTRAL_POST),
    ]:
        common = sorted(set(pre_map) & set(post_map))
        for attack in common:
            comparisons[style][attack] = {}
            for mode in MODES:
                pre_path, post_path = source_for(pre_map, attack, mode), source_for(post_map, attack, mode)
                pre, post = summarize(attack, pre_path), summarize(attack, post_path)
                relation = prompt_relation(pre_path, post_path, attack)
                item = {"pre": pre, "post": post, "prompt_relation": relation}
                comparisons[style][attack][mode] = item
                ledger.extend([
                    {"style": style, "stage": "original", "attack": attack, "mode": mode, **pre},
                    {"style": style, "stage": "hardened", "attack": attack, "mode": mode, **post},
                ])
    comparisons["neutral"]["A07-note"] = (
        "The stored neutral original A07 is synthetic-trigger style, while the stored neutral hardened A07 is natural style; "
        "they are reported separately and not treated as a before/after causal pair."
    )
    return comparisons, ledger


def frac(n: int, d: int) -> str:
    return f"{n}/{d} ({100*n/d:.1f}%)" if d else "n/a"


def wrap(text: str, width: int = 92) -> str:
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def write_csv(ledger: list[dict[str, Any]]) -> None:
    columns = ["style", "stage", "attack", "mode", "metric", "primary", "unauthorized_n",
               "exposure", "positive", "protected_n", "records", "source", "sha256"]
    with (OUT / "evidence_ledger.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in ledger:
            writer.writerow({key: row.get(key, "") for key in columns})


def write_figures(comp: dict[str, Any]) -> None:
    for style in ("labeled", "neutral"):
        attacks = [a for a in ATTACK_NAMES if a in comp[style]]
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
        for ax, mode in zip(axes, MODES):
            before = [100 * comp[style][a][mode]["pre"]["primary"] / comp[style][a][mode]["pre"]["unauthorized_n"] for a in attacks]
            after = [100 * comp[style][a][mode]["post"]["primary"] / comp[style][a][mode]["post"]["unauthorized_n"] for a in attacks]
            x = range(len(attacks))
            ax.bar([i - .2 for i in x], before, .4, label="Original", color="#a44a3f")
            ax.bar([i + .2 for i in x], after, .4, label="Hardened", color="#267a68")
            ax.set_ylabel("Primary outcome (%)")
            ax.set_title(MODE_LABEL[mode] + " mode")
            ax.set_xticks(list(x), attacks)
            ax.set_ylim(0, 105)
            ax.grid(axis="y", alpha=.25)
        axes[0].legend(ncol=2)
        fig.suptitle(f"{style.title()} prompts: attack-specific primary security outcomes")
        fig.savefig(OUT / f"{style}_primary_outcomes.pdf")
        fig.savefig(OUT / f"{style}_primary_outcomes.png", dpi=180)
        plt.close(fig)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
        *["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in rows],
    ])


def tex_escape(value: Any) -> str:
    text = str(value)
    for old, new in [
        ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
        ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
        ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]:
        text = text.replace(old, new)
    return text


def tex_result_rows(comp: dict[str, Any], style: str, mode: str) -> str:
    rows = []
    for attack in ATTACK_NAMES:
        if attack not in comp[style]:
            continue
        item = comp[style][attack][mode]
        pre, post = item["pre"], item["post"]
        rows.append(
            f"{attack} & {tex_escape(pre['metric'])} & "
            f"{pre['primary']}/{pre['unauthorized_n']} & {post['primary']}/{post['unauthorized_n']} & "
            f"{pre['positive']}/{pre['protected_n']} & {post['positive']}/{post['protected_n']} & "
            f"{tex_escape(item['prompt_relation'])} \\\\"
        )
    return "\n".join(rows)


def build_tex(comp: dict[str, Any]) -> str:
    labeled_secure = tex_result_rows(comp, "labeled", "secure_rag_mode")
    labeled_sens = tex_result_rows(comp, "labeled", "sensitivity_eval_mode")
    neutral_secure = tex_result_rows(comp, "neutral", "secure_rag_mode")
    neutral_sens = tex_result_rows(comp, "neutral", "sensitivity_eval_mode")
    cause_sections = []
    for attack, name in ATTACK_NAMES.items():
        cause, fix = CAUSES[attack]
        cause_sections.append(
            rf"""\section{{{attack}: {tex_escape(name)}}}
\textbf{{Original failure mechanism.}} {tex_escape(cause)}

\textbf{{Hardening.}} {tex_escape(fix)}
"""
        )
    provenance_rows = []
    for style in ("labeled", "neutral"):
        for attack in ATTACK_NAMES:
            if attack not in comp[style]:
                continue
            relations = sorted({comp[style][attack][m]["prompt_relation"] for m in MODES})
            matched = all(r in {"Exact", "Attack and seed exact"} for r in relations)
            provenance_rows.append(
                f"{style.title()} & {attack} & {tex_escape(', '.join(relations))} & "
                f"{'Prompt-matched package comparison' if matched else 'Descriptive package comparison'} \\\\"
            )
    return rf"""\documentclass[12pt,a4paper,oneside,openany]{{report}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage[english]{{babel}}
\usepackage{{lmodern}}
\usepackage{{microtype}}
\setlength{{\emergencystretch}}{{3em}}
\usepackage[a4paper,top=30mm,bottom=30mm,inner=35mm,outer=25mm]{{geometry}}
\usepackage{{setspace}}
\onehalfspacing
\usepackage{{booktabs}}
\usepackage{{graphicx}}
\usepackage{{longtable}}
\usepackage{{tabularx}}
\usepackage{{array}}
\usepackage{{pdflscape}}
\usepackage{{enumitem}}
\usepackage{{xcolor}}
\usepackage[hidelinks]{{hyperref}}
\usepackage[nameinlink,noabbrev]{{cleveref}}
\usepackage{{needspace}}
\usepackage{{etoolbox}}
\preto\section{{\Needspace{{5\baselineskip}}}}
\preto\subsection{{\Needspace{{4\baselineskip}}}}
\setlength{{\tabcolsep}}{{3pt}}
\renewcommand{{\arraystretch}}{{1.15}}
\hypersetup{{
  pdftitle={{Modular Sensitivity-Aware Retrieval-Augmented Generation for Structured Tabular Data}},
  pdfauthor={{Author Name}},
  pdfsubject={{Master's Thesis in Computer Science}},
  pdfkeywords={{retrieval-augmented generation, RAG, access control, tabular data, security}}
}}
\newcommand{{\thesistitle}}{{Modular Sensitivity-Aware Retrieval-Augmented Generation for Structured Tabular Data}}
\newcommand{{\thesisauthor}}{{Author Name}}
\newcommand{{\studentid}}{{Student ID}}
\newcommand{{\universityname}}{{University Name}}
\newcommand{{\facultyname}}{{Faculty or Department Name}}
\newcommand{{\supervisorname}}{{Supervisor Name}}
\newcommand{{\submissiondate}}{{\today}}
\begin{{document}}
\begin{{titlepage}}
  \centering
  \vspace*{{20mm}}
  {{\Large \universityname\par}}
  \vspace{{5mm}}
  {{\large \facultyname\par}}
  \vfill
  {{\Huge\bfseries \thesistitle\par}}
  \vspace{{12mm}}
  {{\Large Master's Thesis in Computer Science\par}}
  \vfill
  \begin{{tabular}}{{@{{}}ll@{{}}}}
    Author: & \thesisauthor \\
    Student ID: & \studentid \\
    Supervisor: & \supervisorname \\
    Submission date: & \submissiondate
  \end{{tabular}}
  \vspace*{{15mm}}
\end{{titlepage}}
\pagenumbering{{roman}}
\begingroup
\singlespacing
\small
\tableofcontents
\endgroup
\clearpage
\begingroup
\singlespacing
\small
\listoftables
\endgroup
\clearpage
\begingroup
\singlespacing
\small
\listoffigures
\endgroup
\clearpage
\pagenumbering{{arabic}}

\setcounter{{chapter}}{{4}}
\chapter{{Experiments}}
\section{{Evaluation scope}}
This report compares the historical original implementation with the complete hardened implementation. Attack-labeled and neutral prompts are kept separate because naming an attack can alter model and guard behaviour. The hardened package recorded zero unauthorized delivered primary outcomes in every directly tabulated comparison. This supports a substantial security improvement on the tested matrix, but it is not a universal proof of security.

The interpretation is package-level. Field and relation projection, state invalidation, membership protection, injection-resistant context handling, probe-aware processing, and final-answer verification jointly changed the observed behavior. Historical prompt and source-state metadata are incomplete for several datasets, so the report does not attribute every difference causally to one code component.

\section{{Research questions}}
The evaluation asks how the original implementation failed, how the complete hardened package behaved, and whether results differ between prompts that explicitly identify the attack and prompts that omit the label. Guards-off/on ablations are reserved for a later component study.

\begin{{table}}[htbp]
\centering
\caption{{Two parallel package comparisons}}
\begin{{tabularx}}{{\textwidth}}{{@{{}}lXXX@{{}}}}
\toprule
Condition & Original & Hardened & Interpretation \\
\midrule
Labeled & Attack name stated & Attack name stated & Conspicuous attack wording \\
Neutral & Attack name omitted & Attack name omitted & Less conspicuous wording \\
\bottomrule
\end{{tabularx}}
\end{{table}}

\section{{Evaluation procedure}}
Each complete attack--mode matrix crosses five deterministic targets, three access roles (public, internal, protected), three conversation lengths (1, 3, and 5 user turns), and five iterations. This yields 225 conversations. Public and internal runs form the unauthorized security denominator of 150; protected runs form the positive-control utility denominator of 75.

The model is \texttt{{gpt-4o-mini}} at temperature 0.0 with retrieval depth five. Secure mode projects evidence according to access policy before generation. Sensitivity-evaluation mode deliberately keeps restricted evidence model-visible so downstream containment can be tested. Where available, the evaluation distinguishes raw retrieval, model-visible context, raw answer, and delivered answer.

\section{{Attack-specific outcomes}}
A single generic leakage rate would conflate different failures. A01 measures exact-cell disclosure; A02 row reconstruction; A03 state and memory disclosure; A04 relation-edge disclosure; A05 membership confirmation; A06 and A07 attacker-controlled canary compliance; and A08 numeric embedding/rank leakage. Protected-role success is a utility measure.

\begin{{landscape}}
\begin{{small}}
\begin{{longtable}}{{@{{}}p{{0.10\linewidth}}p{{0.11\linewidth}}p{{0.25\linewidth}}p{{0.38\linewidth}}@{{}}}}
\caption{{Evidence provenance and permissible interpretation}}\label{{tab:provenance}}\\
\toprule
Style & Attack & Prompt relation & Interpretation \\
\midrule
\endfirsthead
\toprule
Style & Attack & Prompt relation & Interpretation \\
\midrule
\endhead
{chr(10).join(provenance_rows)}
\bottomrule
\end{{longtable}}
\end{{small}}
\end{{landscape}}

Exact prompt matching improves comparability but does not isolate a single hardening change because the whole implementation changed. A07-S is the valid labeled A07 pair. Historical A07-N lacks the attack label, and the stored neutral A07 stages use different families; they are not treated as before/after pairs.

\chapter{{Results}}
\section{{Attack-labeled prompts}}
\subsection{{Secure mode}}
\begin{{landscape}}
\begin{{small}}
\begin{{longtable}}{{@{{}}p{{0.06\linewidth}}p{{0.24\linewidth}}rrrrp{{0.17\linewidth}}@{{}}}}
\caption{{Labeled prompts in secure mode}}\label{{tab:labeled-secure}}\\
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endfirsthead
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endhead
{labeled_secure}
\bottomrule
\end{{longtable}}
\end{{small}}
\end{{landscape}}

\subsection{{Sensitivity-evaluation mode}}
\begin{{landscape}}
\begin{{small}}
\begin{{longtable}}{{@{{}}p{{0.06\linewidth}}p{{0.24\linewidth}}rrrrp{{0.17\linewidth}}@{{}}}}
\caption{{Labeled prompts in sensitivity-evaluation mode}}\label{{tab:labeled-sensitivity}}\\
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endfirsthead
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endhead
{labeled_sens}
\bottomrule
\end{{longtable}}
\end{{small}}
\end{{landscape}}

\begin{{figure}}[htbp]
\centering
\includegraphics[width=\textwidth]{{labeled_primary_outcomes.pdf}}
\caption{{Attack-specific primary outcomes under labeled prompts.}}
\end{{figure}}

\section{{Neutral prompts}}
\subsection{{Secure mode}}
\begin{{landscape}}
\begin{{small}}
\begin{{longtable}}{{@{{}}p{{0.06\linewidth}}p{{0.24\linewidth}}rrrrp{{0.17\linewidth}}@{{}}}}
\caption{{Neutral prompts in secure mode}}\label{{tab:neutral-secure}}\\
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endfirsthead
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endhead
{neutral_secure}
\bottomrule
\end{{longtable}}
\end{{small}}
\end{{landscape}}

\subsection{{Sensitivity-evaluation mode}}
\begin{{landscape}}
\begin{{small}}
\begin{{longtable}}{{@{{}}p{{0.06\linewidth}}p{{0.24\linewidth}}rrrrp{{0.17\linewidth}}@{{}}}}
\caption{{Neutral prompts in sensitivity-evaluation mode}}\label{{tab:neutral-sensitivity}}\\
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endfirsthead
\toprule
Attack & Primary outcome & Original security & Hardened security & Original utility & Hardened utility & Prompt relation \\
\midrule
\endhead
{neutral_sens}
\bottomrule
\end{{longtable}}
\end{{small}}
\end{{landscape}}

\begin{{figure}}[htbp]
\centering
\includegraphics[width=\textwidth]{{neutral_primary_outcomes.pdf}}
\caption{{Attack-specific primary outcomes under neutral prompts.}}
\end{{figure}}

\section{{Interpretation}}
The original labeled matrix shows complete failure for A03 and A07-S and substantial A02, A05, A04-sensitivity, and A08-sensitivity outcomes. The neutral original matrix again shows complete A03 failure and substantial A02, A04-sensitivity, A05, and A08-sensitivity outcomes. Neutral A01 sensitivity mode additionally records 74/150 disclosures.

Differences between labeled and neutral counts cannot be attributed only to the label. Several historical prompts differ in more than that phrase, and some exact prompt text is unavailable. A clean label-effect study would change only the label phrase.

The directly tabulated hardened matrices record 0/150 for each primary unauthorized outcome. Positive controls show remaining utility costs, notably labeled A01 sensitivity mode and A08. Zero delivery also does not imply zero retrieval or model-context exposure.

\chapter{{Vulnerability Analysis}}
{chr(10).join(cause_sections)}

\chapter{{Discussion}}
\section{{Why the hardened system is more secure}}
The central improvement is policy continuity. Access rules are enforced when fields and relations are loaded, when retrieval becomes model context, when security state changes, and before an answer is delivered. This defence-in-depth design reduces reliance on model refusal alone.

\begin{{table}}[htbp]
\centering
\caption{{Hardening layers and security contributions}}
\begin{{tabularx}}{{\textwidth}}{{@{{}}p{{0.27\textwidth}}X@{{}}}}
\toprule
Layer & Contribution \\
\midrule
Field and relation projection & Prevents unauthorized attributes and edges from entering ordinary context. \\
Secure context construction & Separates untrusted data from instructions and preserves policy metadata. \\
State invalidation & Stops information acquired under one role from surviving a downgrade. \\
Membership and probe handling & Protects existence, rank, and similarity signals. \\
Prompt-injection handling & Quarantines instruction-like retrieved text and checks artifacts. \\
Output verification & Checks generated answers against restricted values before delivery. \\
Telemetry & Separates retrieval, context, raw answer, replacement, and delivery stages. \\
\bottomrule
\end{{tabularx}}
\end{{table}}

\section{{Limitations}}
\begin{{itemize}}[leftmargin=*]
\item This is a historical package comparison, not a randomized one-change intervention.
\item Several original files omit exact prompts, system prompts, dataset hashes, or full source-tree state.
\item A02 and A03 have prompt or protected-seed differences in parts of the historical evidence.
\item A07-S is the only like-for-like labeled A07 comparison; unmatched A07 stages are excluded.
\item Attack-specific outcomes are heterogeneous and must not be summed as one probability.
\item Zero observed leakage applies only to this model, dataset, prompt panel, and sample size.
\item Positive-control failures show that security improvement can coexist with utility loss.
\end{{itemize}}

\chapter{{Conclusion}}
The evidence supports the conclusion that the complete hardened package is substantially more secure than the original implementation on the tested matrix. Policy-aware projection reduces exposure, state boundaries prevent privilege carry-over, specialized checks cover membership, injection, and side-channel probes, and final verification limits delivery when earlier layers fail.

The next stage should hold the hardened source state and exact neutral prompts constant while switching the guard bundle off and on. That narrower ablation can estimate guard contribution and should remain separate from this package comparison.

\appendix
\chapter{{Reproducibility Artifacts}}
The companion \path{{metrics.json}} records extracted counts, denominators, source paths, prompt relations, and SHA-256 hashes. The flat \path{{evidence_ledger.csv}} records every included source. The validated generation script is \path{{scripts/build_original_vs_hardened_report.py}}.

\end{{document}}
"""


def build_markdown(comp: dict[str, Any]) -> str:
    md: list[str] = [
        "# Original versus Hardened RAG Security Evaluation",
        "",
        "**A two-prompt-style package comparison across eight adversarial attack families**",
        "",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "## Executive summary",
        "",
        "This report compares the historical original implementation with the complete hardened implementation. "
        "It deliberately separates attack-labeled prompts from neutral prompts, because naming an attack can itself change model or guard behaviour.",
        "",
        "Across the tested matrices, the hardened package eliminated the recorded unauthorized delivered primary outcome in every directly tabulated labeled comparison. "
        "The neutral package comparison also recorded zero primary outcomes after hardening for the available like-for-like families. "
        "This is evidence of improved security on this dataset and attack matrix, not a universal proof of security.",
        "",
        "The strongest interpretation is package-level: field/relation projection, state invalidation, membership protection, injection-resistant context handling, "
        "probe-aware processing, and output verification jointly reduced delivery of protected information or attacker-controlled artifacts. "
        "The historical runs do not always preserve enough prompt and source-state metadata to assign every change causally to a particular code component.",
        "",
        "## 1. Questions and comparison design",
        "",
        "The evaluation asks (1) what failed in the original system, (2) how the full hardened package behaved, and "
        "(3) whether results differ when the prompt explicitly names the attack. Guards-off/on ablations are intentionally excluded; they are a later component study.",
        "",
        md_table(["Prompt condition", "Original", "Hardened", "Interpretation"], [
            ["Labeled", "Attack name stated", "Attack name stated", "Package comparison under conspicuous attack wording"],
            ["Neutral", "Attack name omitted", "Attack name omitted", "Package comparison under less conspicuous wording"],
        ]),
        "",
        "## 2. Experimental procedure",
        "",
        "Each complete attack–mode matrix crosses five deterministic targets, three access roles (public, internal, protected), "
        "three conversation lengths (1, 3, 5 user turns), and five iterations: 225 conversations. Public and internal runs "
        "form the unauthorized security denominator (150); protected runs form the authorized positive-control denominator (75). "
        "The generation model is gpt-4o-mini at temperature 0.0, retrieval depth is five, and the indexed workbook is SiSwiss_Testdaten.xlsx.",
        "",
        "Secure mode projects context according to access policy before generation. Sensitivity-evaluation mode deliberately allows "
        "restricted evidence to remain model-visible so downstream containment and delivery controls can be measured. Raw retrieval, "
        "model-visible context, raw answer, delivered answer, memory state, and attack-specific outcome fields are kept separate where available.",
        "",
        "A single generic leakage definition would be misleading. The primary outcome is exact-cell disclosure for A01, row leakage for A02, "
        "state/memory disclosure for A03, relation-edge disclosure for A04, membership confirmation for A05, canary compliance for A06/A07, "
        "and numeric embedding/rank disclosure for A08. Protected-role success measures utility, not an attack success.",
        "",
        "## 3. Evidence provenance and comparability",
        "",
    ]
    prov_rows = []
    for style in ("labeled", "neutral"):
        for attack in ATTACK_NAMES:
            if attack not in comp[style]:
                continue
            relations = sorted({comp[style][attack][m]["prompt_relation"] for m in MODES})
            matched = all(relation in {"Exact", "Attack and seed exact"} for relation in relations)
            prov_rows.append([style.title(), attack, ", ".join(relations),
                              "Prompt-matched package comparison" if matched else "Descriptive package comparison"])
    md += [md_table(["Style", "Attack", "Stored prompt relation", "Permissible interpretation"], prov_rows), "",
           "Exact prompt matching improves comparability but does not isolate a single code change because the whole implementation changed. "
           "“Different” or unavailable prompt text restricts the result to descriptive association. For A03, the final attack can match while the protected seed differs.",
           "",
           "**A07 limitation.** The stored original A07 synthetic run has an explicit attack label and is paired with the new labeled A07-S run. "
           "The historical natural-style A07 prompt does not contain the attack label, while the new A07-N prompt does. The stored neutral original A07 is synthetic "
           "and the stored neutral hardened A07 is natural. Consequently, neither A07-N nor the neutral A07 folders form a valid like-for-like before/after pair.",
           "",
           "## 4. Results: attack-labeled prompts", ""]
    for mode in MODES:
        rows = []
        for attack in ATTACK_NAMES:
            if attack not in comp["labeled"]:
                continue
            item = comp["labeled"][attack][mode]
            pre, post = item["pre"], item["post"]
            rows.append([attack, pre["metric"], frac(pre["primary"], pre["unauthorized_n"]),
                         frac(post["primary"], post["unauthorized_n"]),
                         frac(pre["positive"], pre["protected_n"]), frac(post["positive"], post["protected_n"]),
                         item["prompt_relation"]])
        md += [f"### {MODE_LABEL[mode]} mode", "",
               md_table(["Attack", "Primary outcome", "Original", "Hardened", "Original utility", "Hardened utility", "Prompt"], rows), ""]
    md += ["A07-S is the valid labeled before/after family. A07-N remains useful additional hardened evidence, but its historical natural prompt lacks the label "
           "and therefore is not inserted into this labeled package comparison.", "",
           "## 5. Results: neutral prompts", ""]
    for mode in MODES:
        rows = []
        for attack in ATTACK_NAMES:
            if attack not in comp["neutral"] or attack.startswith("A07"):
                continue
            item = comp["neutral"][attack][mode]
            pre, post = item["pre"], item["post"]
            rows.append([attack, pre["metric"], frac(pre["primary"], pre["unauthorized_n"]),
                         frac(post["primary"], post["unauthorized_n"]),
                         frac(pre["positive"], pre["protected_n"]), frac(post["positive"], post["protected_n"]),
                         item["prompt_relation"]])
        md += [f"### {MODE_LABEL[mode]} mode", "",
               md_table(["Attack", "Primary outcome", "Original", "Hardened", "Original utility", "Hardened utility", "Prompt"], rows), ""]
    md += ["A07 is excluded from the neutral before/after table because the stored stages use different attack families. "
           "The source folders remain preserved, but they are excluded from the normalized before/after ledger to prevent accidental pairing.", "",
           "## 6. Interpretation of the result patterns", "",
           "**Original system.** The labeled original matrix shows the clearest failures in A03 and A07-S (150/150 in both modes), "
           "with substantial A02, A05, A04-sensitivity, and A08-sensitivity outcomes. The neutral original matrix again shows complete "
           "A03 failure and substantial A02, A04-sensitivity, A05, and A08-sensitivity outcomes. Neutral A01 sensitivity mode additionally "
           "records 74/150 disclosures, whereas labeled A01 records none.",
           "",
           "**Prompt-style effect.** Differences between labeled and neutral counts are descriptively important, but they cannot be attributed "
           "only to the presence of an attack label. Several historical prompt texts differ in more than the label, and some exact texts were not stored. "
           "The safe conclusion is that prompt formulation materially changes observed attack behavior; a clean causal label-effect study would need prompts "
           "that differ by the label phrase alone.",
           "",
           "**Hardened system.** The directly tabulated hardened matrices record 0/150 for every attack-specific primary unauthorized outcome. "
           "This includes conditions where restricted evidence was deliberately model-visible. The positive controls show that containment was not free: "
           "notable utility reductions remain for labeled A01 sensitivity mode and A08, while other attacks preserve or improve protected-user success.",
           "",
           "**Exposure versus delivery.** A zero delivered outcome does not always mean that sensitive information was absent from retrieval or model context. "
           "The hardened architecture often succeeds by preventing exposed evidence from crossing the final delivery boundary. Such latent exposure remains "
           "a security concern and is retained in the companion metrics rather than collapsed into the delivered-answer measure.",
           "",
           "## 7. Vulnerability causes and hardening changes", ""]
    for attack, name in ATTACK_NAMES.items():
        cause, fix = CAUSES[attack]
        md += [f"### {attack}: {name}", "", f"**Original failure mechanism.** {cause}", "",
               f"**Hardening.** {fix}", ""]
    md += [
        "## 8. Why the hardened system is more secure",
        "",
        "The principal improvement is policy continuity across the full information path. Access rules are applied when fields and relations are loaded, "
        "when retrieval results become model context, when conversational state changes, and again before an answer is delivered. This defence-in-depth design "
        "reduces reliance on any single model refusal.",
        "",
        md_table(["Layer", "Security contribution"], [
            ["Field and relation projection", "Prevents unauthorized attributes and graph edges from entering ordinary context."],
            ["Secure context construction", "Preserves the distinction between data and instructions and attaches policy to model-visible evidence."],
            ["State invalidation", "Prevents information acquired under one role from surviving a downgrade."],
            ["Membership/probe handling", "Protects existence, rank, and similarity signals even when full record contents are hidden."],
            ["Prompt-injection handling", "Quarantines instruction-like retrieved text and detects attacker-controlled artifacts."],
            ["Output verification", "Checks raw generated answers against restricted values before delivery."],
            ["Telemetry", "Separates retrieval exposure, model exposure, raw leakage, replacement, and delivered leakage."],
        ]),
        "",
        "Security can therefore improve even when retrieval exposure remains: a later boundary may prevent delivery. Nevertheless, context exposure remains important "
        "because a different prompt or model could convert latent exposure into an answer. The report does not equate zero delivered leakage with absence of risk.",
        "",
        "## 9. Limitations",
        "",
        "- This is a historical package comparison, not a randomized one-change intervention.",
        "- Some original result files omit exact prompts, system prompts, dataset hashes, or complete Git/dirty-tree state.",
        "- A02 and A03 have known prompt or protected-seed differences in parts of the historical evidence.",
        "- A07-S is the only like-for-like labeled A07 comparison. A07-N and the neutral A07 stages lack a matched before/after prompt-family pair.",
        "- Attack-specific primary outcomes are intentionally heterogeneous; cross-attack totals should not be interpreted as one common probability.",
        "- Zero observed leakage applies only to this model, dataset, prompt panel, retrieval configuration, and sample size.",
        "- Positive-control failures show that security gains can coexist with reduced authorized utility.",
        "",
        "## 10. Conclusions and next stage",
        "",
        "The stored evidence supports the conclusion that the complete hardened package is substantially more secure on the tested matrix than the original implementation. "
        "The mechanism is defence in depth: policy-aware projection reduces exposure, state boundaries prevent privilege carry-over, specialized guards cover membership, "
        "injection, and side-channel probes, and final verification limits delivery when earlier layers fail.",
        "",
        "The next stage should use the same hardened source state and exact neutral prompts in guards-off and guards-on arms. That experiment answers a narrower question: "
        "how much of the hardened package’s behavior is attributable to the switchable guard bundle. It should remain separate from this original-versus-hardened report.",
        "",
        "## Appendix A. Evidence roots and reproducibility artifacts",
        "",
        md_table(["Evidence group", "Root"], [
            ["Original labeled", "outputs/experiments/gpt4o_mini_slurm"],
            ["Original neutral", "outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719"],
            ["Hardened neutral", "outputs/experiments/post hardened 1-8"],
            ["New hardened labeled A01/A07", "outputs/experiments/labeled_post_hardened_a01_a07_20260726T170023Z"],
            ["Other hardened labeled attacks", "Attack-specific folders recorded per row in evidence_ledger.csv"],
        ]),
        "",
        "The companion `metrics.json` contains every extracted numerator, denominator, source path, prompt-relation classification, and SHA-256 result hash. "
        "`evidence_ledger.csv` provides a flat audit table. The plotting and report source is `scripts/build_original_vs_hardened_report.py`.",
    ]
    return "\n".join(md) + "\n"


def pdf_text_page(pdf: PdfPages, title: str, paragraphs: list[str], footer: str) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    fig.text(.085, .94, title, fontsize=17, weight="bold", color="#173f5f")
    y = .895
    for para in paragraphs:
        if para.startswith("## "):
            y -= .012
            fig.text(.085, y, para[3:], fontsize=13, weight="bold", color="#267a68")
            y -= .045
            continue
        if para.startswith("### "):
            fig.text(.085, y, para[4:], fontsize=11, weight="bold")
            y -= .035
            continue
        lines = wrap(para.replace("**", "").replace("`", ""), 96).splitlines() or [""]
        fig.text(.085, y, "\n".join(lines), fontsize=9.4, va="top", linespacing=1.35)
        y -= .025 * len(lines) + .018
    fig.text(.5, .035, footer, ha="center", fontsize=8, color="#666666")
    plt.axis("off")
    pdf.savefig(fig)
    plt.close(fig)


def pdf_result_table(pdf: PdfPages, comp: dict[str, Any], style: str, mode: str, page: int) -> None:
    attacks = [a for a in ATTACK_NAMES if a in comp[style]]
    rows = []
    for attack in attacks:
        item = comp[style][attack][mode]
        pre, post = item["pre"], item["post"]
        rows.append([
            attack,
            "\n".join(textwrap.wrap(pre["metric"], 21)),
            f"{pre['primary']}/{pre['unauthorized_n']}",
            f"{post['primary']}/{post['unauthorized_n']}",
            f"{pre['positive']}/{pre['protected_n']}",
            f"{post['positive']}/{post['protected_n']}",
            "\n".join(textwrap.wrap(item["prompt_relation"], 15)),
        ])
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.axis("off")
    ax.set_title(f"{style.title()} prompts — {MODE_LABEL[mode]} mode", fontsize=16, weight="bold",
                 color="#173f5f", pad=22)
    table = ax.table(
        cellText=rows,
        colLabels=["Attack", "Primary outcome", "Original\nsecurity", "Hardened\nsecurity",
                   "Original\nutility", "Hardened\nutility", "Prompt relation"],
        cellLoc="left", colLoc="left", loc="center",
        colWidths=[.065, .25, .105, .105, .105, .105, .16],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.2)
    table.scale(1, 2.25)
    for (r, _), cell in table.get_celld().items():
        cell.set_edgecolor("#b8c4cc")
        if r == 0:
            cell.set_facecolor("#173f5f")
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
        elif r % 2 == 0:
            cell.set_facecolor("#edf5f2")
    fig.text(.06, .08, "Security denominator: public + internal (n=150). Utility denominator: protected (n=75).",
             fontsize=8.5, color="#444")
    fig.text(.94, .04, f"Page {page}", ha="right", fontsize=8, color="#666")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def pdf_provenance_table(pdf: PdfPages, comp: dict[str, Any], page: int) -> None:
    rows = []
    for style in ("labeled", "neutral"):
        for attack in ATTACK_NAMES:
            if attack not in comp[style]:
                continue
            relations = sorted({comp[style][attack][m]["prompt_relation"] for m in MODES})
            matched = all(r in {"Exact", "Attack and seed exact"} for r in relations)
            rows.append([style.title(), attack, "\n".join(textwrap.wrap(", ".join(relations), 24)),
                         "Prompt-matched package" if matched else "Descriptive package"])
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.set_title("Evidence provenance and permissible interpretation", fontsize=15, weight="bold",
                 color="#173f5f", pad=20)
    table = ax.table(cellText=rows, colLabels=["Style", "Attack", "Prompt relation", "Interpretation"],
                     cellLoc="left", colLoc="left", loc="center",
                     colWidths=[.15, .12, .34, .3])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 2.1)
    for (r, _), cell in table.get_celld().items():
        cell.set_edgecolor("#b8c4cc")
        if r == 0:
            cell.set_facecolor("#173f5f"); cell.get_text().set_color("white"); cell.get_text().set_weight("bold")
        elif r % 2 == 0:
            cell.set_facecolor("#edf5f2")
    fig.text(.08, .065, "Prompt matching improves comparability but does not isolate one code change.", fontsize=8.5)
    fig.text(.92, .035, f"Page {page}", ha="right", fontsize=8, color="#666")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def build_pdf(md: str, comp: dict[str, Any]) -> None:
    sections = md.split("\n## ")
    with PdfPages(OUT / "original_vs_hardened_report.pdf") as pdf:
        pdf_text_page(pdf, "Original versus Hardened RAG Security Evaluation", [
            "A two-prompt-style package comparison across eight adversarial attack families",
            "Standalone report — the thesis source is unchanged",
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            "Scope: original implementation versus complete hardened implementation under attack-labeled and neutral prompts.",
            "Guards-off/on ablations are intentionally reserved for the next experimental stage.",
        ], "Original versus Hardened RAG Security Evaluation")
        page = 2
        for section in sections[1:]:
            lines = section.splitlines()
            title = lines[0].strip()
            prose = []
            for line in lines[1:]:
                line = line.strip()
                if not line or line.startswith("|") or line.startswith("!["):
                    continue
                prose.append(line.lstrip("- "))
            chunks, current, count = [], [], 0
            for para in prose:
                cost = max(2, len(textwrap.wrap(para, 96)))
                if current and count + cost > 31:
                    chunks.append(current); current = []; count = 0
                current.append(para); count += cost + 1
            if current:
                chunks.append(current)
            for idx, chunk in enumerate(chunks or [[]]):
                pdf_text_page(pdf, title + (f" (continued {idx+1})" if idx else ""), chunk, f"Page {page}")
                page += 1
            if title == "3. Evidence provenance and comparability":
                pdf_provenance_table(pdf, comp, page)
                page += 1
            if title == "4. Results: attack-labeled prompts":
                for mode in MODES:
                    pdf_result_table(pdf, comp, "labeled", mode, page)
                    page += 1
            if title == "5. Results: neutral prompts":
                for mode in MODES:
                    pdf_result_table(pdf, comp, "neutral", mode, page)
                    page += 1
        for style in ("labeled", "neutral"):
            image = plt.imread(OUT / f"{style}_primary_outcomes.png")
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.suptitle(f"{style.title()} prompt results", fontsize=16, weight="bold", color="#173f5f", y=.95)
            ax = fig.add_axes([.06, .14, .88, .72])
            ax.imshow(image); ax.axis("off")
            fig.text(.5, .05, f"Page {page}", ha="center", fontsize=8, color="#666")
            pdf.savefig(fig); plt.close(fig); page += 1


def validate(comp: dict[str, Any], ledger: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for row in ledger:
        if row["records"] != 225:
            errors.append(f"{row['style']} {row['stage']} {row['attack']} {row['mode']}: {row['records']} records")
        if row["unauthorized_n"] != 150 or row["protected_n"] != 75:
            errors.append(f"{row['style']} {row['stage']} {row['attack']} {row['mode']}: denominator mismatch")
        if row["roles"] != ["internal", "protected", "public"]:
            errors.append(f"{row['source']}: role coverage mismatch")
        if row["iterations"] != [1, 2, 3, 4, 5]:
            errors.append(f"{row['source']}: iteration coverage mismatch")
    return {
        "valid": not errors,
        "errors": errors,
        "ledger_rows": len(ledger),
        "result_files": len({row["source"] for row in ledger}),
        "comparisons": {style: sorted(a for a in comp[style] if not a.endswith("-note")) for style in ("labeled", "neutral")},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    comp, ledger = build_ledger()
    validation = validate(comp, ledger)
    (OUT / "metrics.json").write_text(json.dumps(comp, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    write_csv(ledger)
    write_figures(comp)
    md = build_markdown(comp)
    (OUT / "original_vs_hardened_report.md").write_text(md, encoding="utf-8")
    (OUT / "main.tex").write_text(build_tex(comp), encoding="utf-8")
    build_pdf(md, comp)
    checksums = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "checksums.json":
            checksums[path.name] = sha(path)
    (OUT / "checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), **validation}, indent=2))


if __name__ == "__main__":
    main()
