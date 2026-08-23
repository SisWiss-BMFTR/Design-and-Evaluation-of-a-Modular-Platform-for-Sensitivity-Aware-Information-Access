#!/usr/bin/env python3
"""Generate corrected prompt-matched before/after thesis figures."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


OUT = Path("thesis/figures")
OUT.mkdir(parents=True, exist_ok=True)

attacks = ["A01", "A02", "A03", "A04", "A05", "A06", "A07-S", "A08"]

# Attack-specific primary outcomes, each with N=150 unauthorised conversations.
pre_secure = np.array([0, 8, 150, 0, 0, 0, 150, 0]) / 150 * 100
post_secure = np.array([0, 0, 0, 0, 0, 0, 0, 0]) / 150 * 100
pre_sensitivity = np.array([0, 123, 150, 75, 10, 0, 150, 82]) / 150 * 100
post_sensitivity = np.array([0, 0, 0, 0, 0, 0, 0, 0]) / 150 * 100

x = np.arange(len(attacks))
width = 0.19
fig, ax = plt.subplots(figsize=(12.5, 5.8))
ax.bar(x - 1.5 * width, pre_secure, width, label="Pre: Secure mode", color="#4472C4")
ax.bar(x - 0.5 * width, post_secure, width, label="Post: Secure mode", color="#9DC3E6")
ax.bar(x + 0.5 * width, pre_sensitivity, width, label="Pre: Sensitivity-evaluation mode", color="#C55A11")
ax.bar(x + 1.5 * width, post_sensitivity, width, label="Post: Sensitivity-evaluation mode", color="#F4B183")
ax.scatter([5], [2 / 150 * 100], marker="D", s=55, color="#A61C00", zorder=5,
           label="A06 pre-sensitivity confidentiality leakage")
ax.annotate("2/150 confidentiality disclosures\n(canary compliance remained 0/150)",
            xy=(5, 2 / 150 * 100), xytext=(4.15, 17), fontsize=8,
            arrowprops={"arrowstyle": "->", "color": "#A61C00"})
ax.set_xticks(x)
ax.set_xticklabels(attacks)
ax.set_ylabel("Outcome rate (%)")
ax.set_ylim(0, 108)
ax.grid(axis="y", alpha=0.25)
ax.legend(ncol=2, fontsize=8, loc="upper right")
fig.tight_layout()
fig.savefig(OUT / "corrected_before_after_outcomes.pdf", bbox_inches="tight")
fig.savefig(OUT / "corrected_before_after_outcomes.png", dpi=220, bbox_inches="tight")
plt.close(fig)

# Attack-specific protected positive controls, each with N=75.
pre_secure_u = np.array([75, 68, 75, 75, 75, 75, 75, 75]) / 75 * 100
post_secure_u = np.array([75, 75, 75, 75, 75, 75, 75, 75]) / 75 * 100
pre_sensitivity_u = np.array([60, 74, 75, 25, 75, 25, 75, 75]) / 75 * 100
post_sensitivity_u = np.array([64, 54, 75, 75, 75, 75, 75, 75]) / 75 * 100

fig, ax = plt.subplots(figsize=(12.5, 5.8))
ax.bar(x - 1.5 * width, pre_secure_u, width, label="Pre: Secure mode", color="#4472C4")
ax.bar(x - 0.5 * width, post_secure_u, width, label="Post: Secure mode", color="#9DC3E6")
ax.bar(x + 0.5 * width, pre_sensitivity_u, width, label="Pre: Sensitivity-evaluation mode", color="#C55A11")
ax.bar(x + 1.5 * width, post_sensitivity_u, width, label="Post: Sensitivity-evaluation mode", color="#F4B183")
ax.set_xticks(x)
ax.set_xticklabels(attacks)
ax.set_ylabel("Positive-control success (%)")
ax.set_ylim(0, 108)
ax.grid(axis="y", alpha=0.25)
ax.legend(ncol=2, fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(OUT / "corrected_before_after_utility.pdf", bbox_inches="tight")
fig.savefig(OUT / "corrected_before_after_utility.png", dpi=220, bbox_inches="tight")
plt.close(fig)

print(OUT / "corrected_before_after_outcomes.pdf")
print(OUT / "corrected_before_after_utility.pdf")
