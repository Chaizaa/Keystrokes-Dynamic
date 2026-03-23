"""Generate Figure 8 (ROC overlay for 20 users) from exported ROC points.

Input JSON schema:
{
  "s003": {
    "fpr": [0.0, 0.01, ...],
    "tpr": [0.0, 0.20, ...],
    "auc": 0.973,
    "eer_point": [0.065, 0.934]
  },
  "s004": { ... }
}
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


INPUT_PATH = Path("docs/diagrams/roc_data_20_users.json")
OUTPUT_PATH = Path("docs/diagrams/Gambar_8_ROC_Overlay_20_Pengguna.png")


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"ROC data file not found: {INPUT_PATH}. "
            "Export per-user ROC points first."
        )

    with INPUT_PATH.open("r", encoding="utf-8") as f:
        roc_data = json.load(f)

    fig, ax = plt.subplots(figsize=(10, 8))

    for user_id, d in roc_data.items():
        fpr = d["fpr"]
        tpr = d["tpr"]
        auc = float(d["auc"])
        eer_x, eer_y = d["eer_point"]

        ax.plot(fpr, tpr, linewidth=1.2, alpha=0.85, label=f"{user_id} (AUC={auc:.3f})")
        ax.scatter([eer_x], [eer_y], marker="x", s=36, alpha=0.9)

    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1.0, color="gray", label="Random baseline")

    ax.set_title("ROC Overlay of 20 User")
    ax.set_xlabel("False Positive Rate (FPR)")
    ax.set_ylabel("True Positive Rate (TPR)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.25)
    ax.legend(ncol=2, fontsize=8, frameon=False)

    fig.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=300)
    plt.close(fig)

    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
