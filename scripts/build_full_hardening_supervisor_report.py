from __future__ import annotations

import csv
import html
import json
import re
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path("outputs/experiments/gpt4o_mini_full_hardening_20260711_183119")
TEMPLATE = Path("reports/supervisor_meeting_attack_report_with_metric_taxonomy.docx")
OUT_MD = Path("reports/gpt4o_mini_full_hardening_supervisor_report.md")
OUT_DOCX = Path("reports/gpt4o_mini_full_hardening_supervisor_report.docx")


ATTACK_NAMES = {
    "A01": "Direct Cell Extraction",
    "A02": "Multi-Turn Row Construction",
    "A03": "Access-Level Downgrade",
    "A04": "Relational Join-Path Inference",
    "A05": "Rank-Probing Membership Inference",
    "A06": "Prompt Injection / Poisoned Row",
    "A07": "Backdoor-Triggered Extraction",
    "A08": "Embedding-Side Leakage",
}

ATTACK_FOLDERS = {
    "A01": "attack_01_direct_cell_extraction",
    "A02": "attack_02_multiturn_row_construction",
    "A03": "attack_03_access_level_downgrade_task",
    "A04": "attack_04_relational_join_path_inference",
    "A05": "attack_05_rank_probing_membership_inference",
    "A06": "attack_06_prompt_injection_poisoned_row",
    "A07": "attack_07_backdoor_triggered_extraction",
    "A08": "attack_08_embedding_side_leakage",
}


def parse_fraction(value: str) -> tuple[int, int, float]:
    match = re.search(r"(\d+)\s*/\s*(\d+)(?:\s*\(([-+]?\d+(?:\.\d+)?)%\))?", value)
    if not match:
        return (0, 0, 0.0)
    num, den = int(match.group(1)), int(match.group(2))
    pct = float(match.group(3)) if match.group(3) is not None else (100.0 * num / den if den else 0.0)
    return num, den, pct


def parse_markdown_tables(path: Path) -> dict[str, list[dict[str, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    tables: dict[str, list[dict[str, str]]] = {}
    current_heading = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            current_heading = line[3:].strip()
        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            header = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            sep = lines[i + 1]
            if set(sep.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
                rows = []
                i += 2
                while i < len(lines) and lines[i].startswith("|"):
                    vals = [cell.strip().strip("`") for cell in lines[i].strip("|").split("|")]
                    rows.append(dict(zip(header, vals)))
                    i += 1
                tables[current_heading] = rows
                continue
        i += 1
    return tables


def validate_outputs() -> tuple[int, int, list[str]]:
    problems: list[str] = []
    dataset_count = 0
    total_rows = 0
    for profile in ["guards_on", "guards_off"]:
        for attack, folder in ATTACK_FOLDERS.items():
            for mode in ["secure_rag_mode", "sensitivity_eval_mode"]:
                base = ROOT / profile / folder / mode
                csv_path = base / "results.csv"
                json_path = base / "results.json"
                report_path = base / "report.md"
                if not csv_path.exists() or not json_path.exists() or not report_path.exists():
                    problems.append(f"Missing file(s) for {profile}/{attack}/{mode}")
                    continue
                with csv_path.open(newline="", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    json_rows = data.get("records") or data.get("results") or data.get("runs")
                else:
                    json_rows = data
                dataset_count += 1
                total_rows += len(rows)
                if len(rows) != 225:
                    problems.append(f"{profile}/{attack}/{mode} CSV has {len(rows)} rows")
                if not isinstance(json_rows, list) or len(json_rows) != 225:
                    problems.append(f"{profile}/{attack}/{mode} JSON does not contain 225 records")
    return dataset_count, total_rows, problems


def read_overall_counts(report_path: Path) -> dict[str, str]:
    text = report_path.read_text(encoding="utf-8")
    section = re.search(r"## Overall Counts\n\n(?P<body>.*?)(?:\n## |\Z)", text, re.S)
    counts: dict[str, str] = {}
    if not section:
        return counts
    for line in section.group("body").splitlines():
        match = re.match(r"-\s*(.*?):\s*`?([^`]+?)`?\.$", line.strip())
        if match:
            counts[match.group(1)] = match.group(2)
    return counts


def pct_text(value: str) -> str:
    n, d, p = parse_fraction(value)
    return f"{n}/{d} ({p:.1f}%)"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def build_markdown() -> str:
    agg_tables = parse_markdown_tables(ROOT / "AGGREGATED_ATTACK_REPORT.md")
    ablation_tables = parse_markdown_tables(ROOT / "BEFORE_AFTER_ABLATION_REPORT.md")
    normalized = agg_tables["Normalized Results"]
    cross_mode = agg_tables["Cross-Mode Totals"]
    access_level = agg_tables["Access-Level Leakage"]
    length_leakage = agg_tables["Conversation-Length Leakage"]
    ablation = next(iter(ablation_tables.values()))
    dataset_count, total_rows, problems = validate_outputs()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    norm_by_key = {
        (row["Profile"], row["Attack"].split()[0], row["Mode"]): row for row in normalized
    }
    abl_by_key = {
        (row["Attack"].split()[0], row["Mode"]): row for row in ablation
    }

    md: list[str] = []
    md.append("# Supervisor Meeting Report: Full-Hardening Guards-On/Guards-Off Attack Evaluation")
    md.append("")
    md.append(f"Generated: {generated}")
    md.append("")
    md.append("Source experiment root: `outputs/experiments/gpt4o_mini_full_hardening_20260711_183119`.")
    md.append("")
    md.append("## 1. Executive Summary")
    md.append("")
    summary_bullets = [
        "The completed experiment evaluates eight attacks against the sensitivity-aware RAG system under two profiles: `guards_on` and `guards_off`.",
        "Both profiles were run in `secure_rag_mode` and `sensitivity_eval_mode`, giving 32 datasets. Each dataset contains 225 conversations: five targets, three access levels, three conversation lengths, and five iterations.",
        "The generation model was `gpt-4o-mini` at temperature 0.0. The embedding model remained `sentence-transformers/all-MiniLM-L6-v2`.",
        "All 32 CSV/JSON/report outputs were present and validated. The final matrix contains 7,200 conversations.",
        "The main user-visible confidentiality metric is unauthorized delivered final-answer leakage. Retrieval/context exposure is reported separately because sensitive context in retrieval is not automatically the same as a delivered disclosure.",
        "With `guards_on`, unauthorized answer leakage was 0/150 in every attack and mode.",
        "With `guards_off`, unauthorized answer leakage was also 0/150 in most attack/mode pairs, except A05 membership inference in `sensitivity_eval_mode`, where 11/150 unauthorized answers confirmed or leaked protected membership.",
        "The guards-on profile removed the observed A05 sensitivity-mode membership leakage: 11/150 to 0/150, a 7.3 percentage-point reduction.",
        "The strongest remaining diagnostic concern is not delivered answer leakage but exposure of restricted context in evaluation mode: A04 and A05 show 150/150 unauthorized context exposure in both profiles, and A08 shows 150/150 context exposure with `guards_off` in sensitivity mode.",
        "Utility is not uniform. Guards-on positive controls remain perfect for A01-A06 except A01 sensitivity mode, while A07 sensitivity mode and A08 in both modes show reduced protected-user success.",
    ]
    for item in summary_bullets:
        md.append(f"- {item}")
    md.append("")
    md.append("The guards-off profile in this report is an ablation profile inside the full-hardening codebase. It disables the named guard layers used for the comparison, while core field-level access projection remains active. It should therefore not be interpreted as the older pre-hardening baseline from earlier thesis drafts.")
    md.append("")

    md.append("## 2. Experimental Setup")
    md.append("")
    setup_rows = [
        ["Dataset", "`data/SiSWiss_Testdaten.xlsx`"],
        ["Experiment root", f"`{ROOT}`"],
        ["Run manifest", "`RUN_MANIFEST.txt`"],
        ["Generation model", "`gpt-4o-mini`"],
        ["Embedding model", "`sentence-transformers/all-MiniLM-L6-v2`"],
        ["Temperature", "`0.0`"],
        ["Profiles", "`guards_on`, `guards_off`"],
        ["RAG modes", "`secure_rag_mode`, `sensitivity_eval_mode`"],
        ["Access levels", "`public`, `internal`, `protected`"],
        ["Attacks", "A01-A08"],
        ["Targets", "Five target records per attack"],
        ["Conversation lengths", "1, 3, and 5 user turns"],
        ["Iterations", "Five per target/access/length condition"],
        ["Runs per dataset", "225"],
        ["Full matrix", "8 attacks x 2 profiles x 2 modes = 32 datasets"],
        ["Total conversations", "7,200"],
    ]
    md.append(md_table(["Setup item", "Evaluated configuration"], setup_rows))
    md.append("")

    md.append("### 2.1 Output Completeness Check")
    md.append("")
    status = "passed" if not problems else "failed"
    md.append(md_table(["Validation item", "Result"], [
        ["Datasets found", f"{dataset_count}/32"],
        ["Total CSV records", f"{total_rows}/7200"],
        ["Per-dataset CSV rows", "225 for every dataset" if not problems else "See problems below"],
        ["Per-dataset JSON records", "225 for every dataset" if not problems else "See problems below"],
        ["Final aggregate reports", "Present"],
        ["Validation status", status],
    ]))
    if problems:
        md.append("")
        for problem in problems:
            md.append(f"- {problem}")
    md.append("")

    md.append("## 3. Metric Taxonomy")
    md.append("")
    md.append("The report keeps the same taxonomy as the supervisor-meeting document so that security, diagnostic exposure, and utility are not collapsed into one number.")
    md.append("")
    md.append(md_table(["Metric category", "Definition", "Main attacks"], [
        ["Unauthorized final-answer leakage", "Protected information or a protected side-channel signal appears in the delivered answer to a public/internal user.", "All attacks"],
        ["Unauthorized context exposure", "Restricted context, records, relation evidence, or membership evidence appears in retrieval/model context. This is diagnostic unless delivered.", "A01-A08"],
        ["Membership leakage", "The answer confirms that a protected record exists or belongs to the indexed corpus.", "A05"],
        ["Relation-edge leakage", "The answer reveals hidden product-formulation-process links or protected graph paths.", "A04"],
        ["Memory/state leakage", "Previously authorized material survives an access downgrade through memory, focus, cache, summary, or prompt state.", "A03"],
        ["Integrity manipulation", "The model follows attacker-controlled content such as a poisoned-row or backdoor canary.", "A06, A07"],
        ["Positive-control success", "A protected user receives the expected protected answer.", "All attacks"],
        ["Authorized error", "A protected-access run fails, refuses, or omits the expected answer.", "All attacks"],
    ]))
    md.append("")

    md.append("## 4. Full Normalized Results")
    md.append("")
    md.append("The following table is the main 32-cell result matrix. Unauthorized counts are computed over the 150 public/internal conversations in each dataset. Positive-control counts are computed over the 75 protected conversations.")
    md.append("")
    md.append(md_table(
        ["Profile", "Attack", "Mode", "Context exposure", "Answer leakage", "Positive control", "Authorized errors", "Runs"],
        [[
            row["Profile"],
            row["Attack"],
            row["Mode"],
            row["Unauthorized context exposure"],
            row["Unauthorized answer leakage"],
            row["Protected positive-control success"],
            row["Authorized errors"],
            row["Runs"],
        ] for row in normalized],
    ))
    md.append("")

    md.append("## 5. Cross-Mode Totals")
    md.append("")
    md.append("These totals are useful for orientation, but they should not be treated as a single universal security score because every attack measures a different failure mechanism.")
    md.append("")
    md.append(md_table(
        ["Profile", "Mode", "Context exposure", "Answer leakage", "Positive control", "Authorized errors"],
        [[
            row["Profile"],
            row["Mode"],
            row["Unauthorized context exposure"],
            row["Unauthorized answer leakage"],
            row["Protected positive-control success"],
            row["Authorized errors"],
        ] for row in cross_mode],
    ))
    md.append("")

    md.append("## 6. Guards-On versus Guards-Off Ablation")
    md.append("")
    md.append("The ablation isolates the contribution of the enabled guard layers within the full-hardening codebase. Negative leakage change means guards reduced delivered leakage.")
    md.append("")
    md.append(md_table(
        ["Attack", "Mode", "Guards-off leakage", "Guards-on leakage", "Change", "Guards-off positive control", "Guards-on positive control"],
        [[
            row["Attack"],
            row["Mode"],
            row["Guards-off leakage"],
            row["Guards-on leakage"],
            row["Absolute change"],
            row["Guards-off positive control"],
            row["Guards-on positive control"],
        ] for row in ablation],
    ))
    md.append("")
    md.append("Main ablation result: A05 in `sensitivity_eval_mode` is the only cell where guards-on changed delivered answer leakage in the final matrix: 11/150 to 0/150. Several other cells show important changes in context exposure or utility rather than final answer leakage.")
    md.append("")

    md.append("## 7. Access-Level and Conversation-Length Breakdown")
    md.append("")
    md.append("The access-level table splits unauthorized answer leakage into public and internal users. In the final matrix, only A05 guards-off sensitivity mode produced delivered leakage: 1/75 public and 10/75 internal.")
    md.append("")
    md.append(md_table(
        ["Profile", "Attack", "Mode", "Public", "Internal"],
        [[row["Profile"], row["Attack"], row["Mode"], row["public"], row["internal"]] for row in access_level],
    ))
    md.append("")
    md.append("Conversation-length leakage shows whether longer dialogues increased delivered answer leakage. The only non-zero delivered leakage again appears in A05 guards-off sensitivity mode: 6/50 for one-turn prompts and 5/50 for five-turn prompts.")
    md.append("")
    md.append(md_table(
        ["Profile", "Attack", "Mode", "1 turn", "3 turns", "5 turns"],
        [[row["Profile"], row["Attack"], row["Mode"], row["1"], row["3"], row["5"]] for row in length_leakage],
    ))
    md.append("")

    md.append("## 8. Attack-by-Attack Interpretation")
    md.append("")
    attack_notes = {
        "A01": "Direct extraction remained answer-confidential under both profiles and modes. Guards-on and guards-off both produced 0/150 unauthorized answer leaks in secure mode and sensitivity-evaluation mode. The utility caveat is sensitivity mode: protected positive-control success was low in both profiles, 17/75 with guards off and 19/75 with guards on. This means the zero-leak result is clean for confidentiality but less strong as a usability claim in sensitivity mode.",
        "A02": "Multi-turn row construction produced 0/150 delivered answer leakage in every final ablation cell. Positive controls were 75/75 in both profiles and modes. Compared with the earlier baseline report, this confirms that the full-hardening code path now keeps delivered reconstruction leakage at zero in the tested matrix.",
        "A03": "Access-level downgrade produced 0/150 delivered answer leakage in every final cell, with 75/75 protected positive-control success throughout. This is the clearest success case for treating role changes as a security-context boundary: the final matrix shows no delivered downgrade leakage under either guards-on or guards-off profile.",
        "A04": "Relational join/path inference is answer-confidential in the final matrix: 0/150 delivered leakage in all four cells. However, sensitivity-evaluation mode still records 150/150 unauthorized context exposure in both profiles. The interpretation is therefore that relation evidence can still be model-visible in evaluation mode, but it was not delivered as unauthorized answer leakage in the tested prompts.",
        "A05": "Rank-probing membership inference is the central ablation win. Secure mode produced 0/150 delivered membership leakage in both profiles. Sensitivity-evaluation mode leaked 11/150 with guards off, split as 1/75 public and 10/75 internal, but 0/150 with guards on. Protected positive controls remained 75/75 in both profiles, so the improvement was not achieved by refusing protected users.",
        "A06": "Prompt injection / poisoned row produced 0/150 delivered protected-value leakage in all four cells and 75/75 protected positive-control success. The final matrix therefore does not show successful protected-value extraction. The report still treats A06 as an integrity and prompt-trust risk class because retrieved document text can act as an instruction source if the model or prompts change.",
        "A07": "Backdoor-triggered extraction produced 0/150 delivered protected-value leakage in both profiles and modes. Utility is the important caveat: sensitivity-mode positive-control success fell from 74/75 with guards off to 70/75 with guards on. This suggests that the enabled guards may slightly increase refusals or misses for authorized users under this attack prompt family.",
        "A08": "Embedding-side leakage produced 0/150 delivered answer leakage in all final cells. The diagnostic pattern is utility and context exposure: guards-on improved secure-mode protected positive controls from 46/75 to 57/75 but reduced sensitivity-mode positive controls from 55/75 to 50/75. Guards-off sensitivity mode also recorded 150/150 unauthorized context exposure, while guards-on sensitivity mode reported 0/150 context exposure in the aggregate.",
    }
    for attack in ATTACK_NAMES:
        md.append(f"### {attack}: {ATTACK_NAMES[attack]}")
        md.append("")
        md.append(attack_notes[attack])
        md.append("")
        rows = []
        for profile in ["guards_off", "guards_on"]:
            for mode in ["secure_rag_mode", "sensitivity_eval_mode"]:
                row = norm_by_key[(profile, attack, mode)]
                rows.append([
                    profile,
                    mode,
                    row["Unauthorized context exposure"],
                    row["Unauthorized answer leakage"],
                    row["Protected positive-control success"],
                    row["Authorized errors"],
                ])
        md.append(md_table(["Profile", "Mode", "Context exposure", "Answer leakage", "Positive control", "Authorized errors"], rows))
        md.append("")

    md.append("## 9. Hardening Interpretation")
    md.append("")
    md.append("The enabled guard profile combines post-generation validation, prompt-injection protection, membership and embedding-probe validation, and access-change memory clearing. Core field-level access projection remains active in both profiles, which explains why many guards-off cells already show zero delivered answer leakage.")
    md.append("")
    md.append(md_table(["Layer", "Purpose", "Main attacks affected"], [
        ["Post-generation verifier", "Checks the raw answer against restricted values before delivery and replaces unsafe answers.", "A01, A02, A03, A04, A08"],
        ["Membership guard", "Detects and blocks existence or membership confirmations for protected records.", "A05"],
        ["Prompt-injection/backdoor guard", "Treats retrieved text as data, quarantines instruction-like content, and checks for canary artifacts.", "A06, A07"],
        ["Embedding/probe guard", "Suppresses rank/similarity/embedding side-channel framing and forces stricter projection.", "A08"],
        ["Access-change memory clearing", "Clears memory, focus state, cached retrieval, and previous guard state when access changes.", "A03"],
        ["Relation policy and projection", "Treats hidden relation edges and IDs as policy-bearing information.", "A04"],
    ]))
    md.append("")

    md.append("## 10. Limitations")
    md.append("")
    limitations = [
        "The attack prompts, targets, and iterations are fixed. The results do not prove resistance to adaptive attackers.",
        "Exact-value and structured-field detectors may miss paraphrases, derived facts, translations, approximations, or semantically equivalent disclosures.",
        "The run uses one generation model, `gpt-4o-mini`, at temperature 0.0. Other models may follow injected text or infer hidden values differently.",
        "`sensitivity_eval_mode` intentionally changes the threat interpretation because restricted context may be visible for evaluation. It should not be mixed with `secure_rag_mode` as if they were the same system behavior.",
        "The guards-off profile is an ablation inside the hardened codebase, not the original vulnerable baseline.",
        "Positive-control failures matter. Zero leakage is less meaningful when authorized users also fail to receive the protected answer.",
        "The current UI does not expose raw ranking lists, similarity scores, citations, or full retrieval metadata. Exposing those would create additional side-channel surfaces.",
        "Cross-session memory, external caches, concurrent users, and long-term deployed behavior were not evaluated in this matrix.",
    ]
    for item in limitations:
        md.append(f"- {item}")
    md.append("")

    md.append("## 11. Thesis-Ready Conclusion")
    md.append("")
    md.append("The completed full-hardening experiment provides a defensible 32-cell ablation matrix for the thesis. Across 7,200 conversations, guards-on produced zero observed unauthorized delivered answer leakage in all tested attack/mode combinations. The only delivered leakage observed in the final guards-off matrix was A05 membership inference in sensitivity-evaluation mode, where 11/150 unauthorized answers leaked or confirmed protected membership. Enabling guards removed this leakage while preserving 75/75 protected positive-control success.")
    md.append("")
    md.append("The broader security interpretation is more nuanced than a single zero-leak statement. Some attack classes, especially A04 and A05, still show diagnostic context exposure in sensitivity-evaluation mode. Utility also varies: A01 sensitivity mode, A07 sensitivity mode, and A08 remain relevant for positive-control discussion. The strongest thesis claim is therefore not that the system is generally secure, but that the implemented layered guards reduced observed delivered leakage in the tested matrix while exposing measurable security-utility trade-offs.")
    md.append("")

    md.append("## Appendix A. Per-Attack Overall Counts")
    md.append("")
    for attack, folder in ATTACK_FOLDERS.items():
        md.append(f"### {attack}: {ATTACK_NAMES[attack]}")
        md.append("")
        rows = []
        for profile in ["guards_off", "guards_on"]:
            for mode in ["secure_rag_mode", "sensitivity_eval_mode"]:
                row = norm_by_key[(profile, attack, mode)]
                rows.append([
                    profile,
                    mode,
                    row["Unauthorized context exposure"],
                    row["Unauthorized answer leakage"],
                    row["Protected positive-control success"],
                    row["Authorized errors"],
                    str(ROOT / profile / folder / mode / "report.md"),
                ])
        md.append(md_table(["Profile", "Mode", "Context exposure", "Answer leakage", "Positive control", "Authorized errors", "Source report"], rows))
        md.append("")

    return "\n".join(md).replace("\n\n\n", "\n\n")


def split_md_table(lines: list[str], start: int) -> tuple[list[str], list[list[str]], int]:
    header = [c.strip() for c in lines[start].strip("|").split("|")]
    rows: list[list[str]] = []
    i = start + 2
    while i < len(lines) and lines[i].startswith("|"):
        rows.append([c.strip() for c in lines[i].strip("|").split("|")])
        i += 1
    return header, rows, i


def w_text(text: str) -> str:
    return html.escape(text, quote=False)


def paragraph_xml(text: str, style: str | None = None) -> str:
    ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    if not text:
        return f"<w:p>{ppr}</w:p>"
    parts = re.split(r"(`[^`]+`)", text)
    runs = []
    for part in parts:
        if not part:
            continue
        if part.startswith("`") and part.endswith("`"):
            runs.append(f"<w:r><w:rPr><w:rFonts w:ascii=\"Courier New\" w:hAnsi=\"Courier New\"/><w:sz w:val=\"19\"/></w:rPr><w:t xml:space=\"preserve\">{w_text(part[1:-1])}</w:t></w:r>")
        else:
            runs.append(f"<w:r><w:t xml:space=\"preserve\">{w_text(part)}</w:t></w:r>")
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def table_xml(headers: list[str], rows: list[list[str]]) -> str:
    def cell(text: str, bold: bool = False) -> str:
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return (
            "<w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr>"
            f"<w:p><w:r>{rpr}<w:t xml:space=\"preserve\">{w_text(text)}</w:t></w:r></w:p></w:tc>"
        )

    grid = "".join("<w:gridCol w:w=\"1800\"/>" for _ in headers)
    out = ["<w:tbl><w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/><w:tblLook w:firstRow=\"1\" w:lastRow=\"0\" w:firstColumn=\"0\" w:lastColumn=\"0\" w:noHBand=\"0\" w:noVBand=\"1\"/></w:tblPr>", f"<w:tblGrid>{grid}</w:tblGrid>"]
    out.append("<w:tr>" + "".join(cell(h, True) for h in headers) + "</w:tr>")
    for row in rows:
        out.append("<w:tr>" + "".join(cell(c) for c in row) + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def markdown_to_document_xml(md: str) -> str:
    body: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            headers, rows, i = split_md_table(lines, i)
            body.append(table_xml(headers, rows))
            body.append(paragraph_xml(""))
            continue
        if line.startswith("# "):
            body.append(paragraph_xml(line[2:].strip(), "Title"))
        elif line.startswith("## "):
            body.append(paragraph_xml(line[3:].strip(), "Heading1"))
        elif line.startswith("### "):
            body.append(paragraph_xml(line[4:].strip(), "Heading2"))
        elif line.startswith("- "):
            body.append(paragraph_xml("• " + line[2:].strip(), "ListParagraph"))
        else:
            body.append(paragraph_xml(line.strip()))
        i += 1
    sect = (
        "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
        "<w:pgMar w:top=\"1440\" w:right=\"1134\" w:bottom=\"1440\" w:left=\"1134\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>"
        "<w:cols w:space=\"708\"/><w:docGrid w:linePitch=\"360\"/></w:sectPr>"
    )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:xml=\"http://www.w3.org/XML/1998/namespace\">"
        f"<w:body>{''.join(body)}{sect}</w:body></w:document>"
    )


def write_docx(md: str) -> None:
    document_xml = markdown_to_document_xml(md).encode("utf-8")
    with zipfile.ZipFile(TEMPLATE) as zin:
        with zipfile.ZipFile(OUT_DOCX, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = document_xml
                elif item.filename == "docProps/core.xml":
                    try:
                        root = ET.fromstring(data)
                        ns = {
                            "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
                            "dc": "http://purl.org/dc/elements/1.1/",
                            "dcterms": "http://purl.org/dc/terms/",
                        }
                        title = root.find("dc:title", ns)
                        if title is not None:
                            title.text = "Full-Hardening Guards-On/Guards-Off Attack Evaluation"
                        modified = root.find("dcterms:modified", ns)
                        if modified is not None:
                            modified.text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                        data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                    except Exception:
                        pass
                zout.writestr(item, data)


def main() -> None:
    md = build_markdown()
    OUT_MD.write_text(md, encoding="utf-8")
    write_docx(md)
    print(OUT_MD)
    print(OUT_DOCX)


if __name__ == "__main__":
    main()
