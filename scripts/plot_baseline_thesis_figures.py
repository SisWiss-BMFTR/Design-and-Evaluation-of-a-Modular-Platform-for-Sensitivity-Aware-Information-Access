#!/usr/bin/env python3
"""Generate Chapter 6 figures from the neutral-prompt pre-hardening outputs.

The script intentionally reads only the completed July 2026 neutral-prompt
baseline.  The earlier attack-labelled baseline and the full-hardening
guards-on/guards-off ablation are not baseline data sources.
No third-party plotting package is required: compact vector PDF and SVG files
are written directly so the figures can be regenerated in the thesis environment.
"""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE_ROOT = (
    ROOT
    / "outputs"
    / "experiments"
    / "gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719"
)
FIGURE_DIR = ROOT / "thesis" / "figures"
MODES = ("secure_rag_mode", "sensitivity_eval_mode")

ATTACKS = (
    ("A01", "attack_01_direct_cell_extraction", None),
    ("A02", "attack_02_multiturn_row_construction", None),
    ("A03", "attack_03_access_level_downgrade_task", None),
    ("A04", "attack_04_relational_join_path_inference", None),
    ("A05", "attack_05_rank_probing_membership_inference", None),
    ("A06", "attack_06_prompt_injection_poisoned_row", None),
    ("A07", "attack_07_backdoor_triggered_extraction", None),
    (
        "A08",
        "gpt4o_mini_slurm_attack08_neutral_prehardened_20260719/attack_08_embedding_side_leakage",
        None,
    ),
)


def load_records(directory, mode, variant):
    path = BASELINE_ROOT / directory
    if variant:
        path /= variant
    path = path / mode / "results.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    records = payload["records"]
    if len(records) != 225:
        raise ValueError("Expected 225 records in {}, found {}".format(path, len(records)))
    return records, path


def access(record, attack):
    if attack == "A03":
        return record["access_after"]
    return record["access"]


def primary_success(record, attack):
    if attack == "A01":
        return bool(record["answer_leak"])
    if attack == "A02":
        return bool(record["conversation_any_answer_leak"])
    if attack == "A03":
        return bool(record["unauthorized_answer_leak"])
    if attack == "A04":
        return bool(record["answer_join_edge"])
    if attack == "A05":
        return bool(record["unauthorized_answer_leak"])
    if attack == "A06":
        return bool(record["unauthorized_answer_leak"])
    if attack == "A07":
        return bool(record["canary_in_answer"])
    if attack == "A08":
        return bool(record["unauthorized_answer_leak"])
    raise KeyError(attack)


def positive_success(record, attack):
    if attack == "A01":
        return bool(record["answer_leak"])
    if attack == "A02":
        return bool(record["final_answer_full_reconstruction"])
    if attack == "A03":
        return bool(record["positive_control_success"])
    if attack == "A04":
        return bool(record["answer_complete"])
    if attack in ("A05", "A06", "A07"):
        return bool(record["authorized_positive_control_success"])
    if attack == "A08":
        return bool(record["positive_control_success"])
    raise KeyError(attack)


def aggregate():
    rows = []
    for attack, directory, variant in ATTACKS:
        for mode in MODES:
            records, source = load_records(directory, mode, variant)
            unauthorized = [row for row in records if access(row, attack) in ("public", "internal")]
            protected = [row for row in records if access(row, attack) == "protected"]
            if len(unauthorized) != 150 or len(protected) != 75:
                raise ValueError("Unexpected access split in {}".format(source))
            primary_count = sum(primary_success(row, attack) for row in unauthorized)
            positive_count = sum(positive_success(row, attack) for row in protected)
            rows.append({
                "attack": attack,
                "mode": mode,
                "primary_count": primary_count,
                "primary_total": len(unauthorized),
                "primary_rate": 100.0 * primary_count / len(unauthorized),
                "positive_count": positive_count,
                "positive_total": len(protected),
                "positive_rate": 100.0 * positive_count / len(protected),
                "source": str(source.relative_to(ROOT)),
            })
    return rows


def escape_pdf(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_text(x, y, size, value, color=(0.12, 0.16, 0.22)):
    return "BT /F1 {} Tf {} {} {} rg {} {} Td ({}) Tj ET".format(
        size, color[0], color[1], color[2], x, y, escape_pdf(value)
    )


def write_pdf(path, title, ylabel, rows, metric_key):
    width, height = 720, 430
    left, right, bottom, top = 72, 24, 68, 54
    plot_w, plot_h = width - left - right, height - bottom - top
    commands = ["1 1 1 rg 0 0 {} {} re f".format(width, height)]
    commands.append(pdf_text(72, 402, 15, title))
    for tick in range(0, 101, 20):
        y = bottom + plot_h * tick / 100.0
        commands.append("0.86 0.88 0.91 RG 0.5 w {} {} m {} {} l S".format(left, y, width - right, y))
        commands.append(pdf_text(40, y - 3, 8, str(tick)))
    commands.append("0.2 0.24 0.3 RG 0.8 w {} {} m {} {} l {} {} l S".format(
        left, height - top, left, bottom, width - right, bottom
    ))
    group_w = plot_w / 8.0
    bar_w = group_w * 0.29
    colors = ((0.18, 0.45, 0.72), (0.90, 0.45, 0.15))
    for index, attack in enumerate([item[0] for item in ATTACKS]):
        matching = [row for row in rows if row["attack"] == attack]
        matching.sort(key=lambda row: MODES.index(row["mode"]))
        center = left + group_w * (index + 0.5)
        for mode_index, row in enumerate(matching):
            value = row[metric_key]
            x = center + (mode_index - 1) * bar_w + 2
            h = plot_h * value / 100.0
            color = colors[mode_index]
            commands.append("{} {} {} rg {} {} {} {} re f".format(
                color[0], color[1], color[2], x, bottom, bar_w - 3, h
            ))
            label = "{:.1f}".format(value)
            commands.append(pdf_text(x - 1, bottom + h + 5, 7, label))
        commands.append(pdf_text(center - 11, 46, 9, attack))
    commands.append("{} {} {} rg 486 404 12 8 re f".format(*colors[0]))
    commands.append(pdf_text(502, 404, 8, "secure_rag_mode"))
    commands.append("{} {} {} rg 594 404 12 8 re f".format(*colors[1]))
    commands.append(pdf_text(610, 404, 8, "sensitivity_eval_mode"))
    content = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {} {}] ".format(width, height)
         + "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>").encode("ascii"),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend("{} 0 obj\n".format(number).encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend("xref\n0 {}\n".format(len(objects) + 1).encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend("{:010d} 00000 n \n".format(offset).encode("ascii"))
    output.extend(("trailer << /Size {} /Root 1 0 R >>\nstartxref\n{}\n%%EOF\n".format(
        len(objects) + 1, xref
    )).encode("ascii"))
    path.write_bytes(output)


def write_svg(path, title, ylabel, rows, metric_key):
    width, height = 960, 560
    left, right, bottom, top = 85, 30, 90, 75
    plot_w, plot_h = width - left - right, height - bottom - top
    colors = ("#2e73b8", "#e67326")
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}">'.format(width, height, width, height),
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#202936}.title{font-size:20px;font-weight:bold}.axis{font-size:12px}.value{font-size:10px}</style>',
        '<text class="title" x="{}" y="30">{}</text>'.format(left, title),
    ]
    for tick in range(0, 101, 20):
        y = top + plot_h * (1 - tick / 100.0)
        parts.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#d9dee6"/>'.format(left, y, width - right, y))
        parts.append('<text class="axis" x="{}" y="{}" text-anchor="end">{}</text>'.format(left - 10, y + 4, tick))
    parts.append('<text class="axis" transform="translate(18,{}) rotate(-90)" text-anchor="middle">{}</text>'.format(top + plot_h / 2, ylabel))
    group_w = plot_w / 8.0
    bar_w = group_w * 0.30
    for index, attack in enumerate([item[0] for item in ATTACKS]):
        matching = [row for row in rows if row["attack"] == attack]
        matching.sort(key=lambda row: MODES.index(row["mode"]))
        center = left + group_w * (index + 0.5)
        for mode_index, row in enumerate(matching):
            value = row[metric_key]
            x = center + (mode_index - 1) * bar_w + 2
            h = plot_h * value / 100.0
            y = top + plot_h - h
            parts.append('<rect x="{}" y="{}" width="{}" height="{}" fill="{}"/>'.format(x, y, bar_w - 3, h, colors[mode_index]))
            parts.append('<text class="value" x="{}" y="{}" text-anchor="middle">{:.1f}</text>'.format(x + (bar_w - 3) / 2, y - 5, value))
        parts.append('<text class="axis" x="{}" y="{}" text-anchor="middle">{}</text>'.format(center, height - 55, attack))
    parts.append('<rect x="650" y="18" width="14" height="10" fill="{}"/><text class="axis" x="670" y="28">secure_rag_mode</text>'.format(colors[0]))
    parts.append('<rect x="790" y="18" width="14" height="10" fill="{}"/><text class="axis" x="810" y="28">sensitivity_eval_mode</text>'.format(colors[1]))
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    rows = aggregate()
    with (FIGURE_DIR / "baseline_figure_data.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    figures = (
        ("baseline_primary_outcomes", "Primary unauthorised baseline outcome by attack and mode", "Attack-specific outcome rate (%)", "primary_rate"),
        ("baseline_positive_controls", "Protected positive-control success by attack and mode", "Positive-control success rate (%)", "positive_rate"),
    )
    for stem, title, ylabel, metric in figures:
        write_pdf(FIGURE_DIR / (stem + ".pdf"), title, ylabel, rows, metric)
        write_svg(FIGURE_DIR / (stem + ".svg"), title, ylabel, rows, metric)
    print("Generated {} from 16 neutral pre-hardening result bundles.".format(FIGURE_DIR))


if __name__ == "__main__":
    main()
