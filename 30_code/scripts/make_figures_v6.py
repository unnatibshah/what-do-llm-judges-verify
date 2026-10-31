"""Figures 2 and 3 of paper_v6, drawn from the paper's own number macros (generated/numbers_e123.tex), so every
plotted value is a value the text already reports. No model call and no new analysis.

    .venv/bin/python 30_code/scripts/make_figures_v6.py

Writes generated/fig_gap.pdf (gap faults by presentation) and generated/fig_decoy.pdf (faults vs decoys by title).
Colours: the dataviz reference palette's first two categorical slots, validated (CVD and normal-vision separation
pass on white); identity is never colour alone (legend plus direct value labels).
"""

import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from suryabench.paths import ROOT  # noqa: E402

GEN = ROOT / "60_paper_drafts" / "paper_v7" / "generated"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#8c8b87"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
JUDGES = [("Gemma", "Gemma 4 26B"), ("GPT", "GPT-5.5"), ("Gemini", "Gemini 3.1 Pro"), ("Opus", "Claude Opus 4.5")]  # table order

plt.rcParams.update({"font.size": 8, "pdf.fonttype": 42, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})


def macros() -> dict[str, str]:
    text = (GEN / "numbers_e123.tex").read_text(encoding="utf-8")
    return dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", text))


def frac(v: str) -> tuple[int, int]:
    k, n = v.split("/")
    return int(k), int(n)


def gap_figure(m: dict[str, str]) -> None:
    conds = [("Texts", "texts alone"), ("Damaged", "\u201cin force\u201d"), ("Norecord", "\u201cno repl. recorded\u201d"),
             ("Lowauth", "unverified note"), ("Caveat", "with warning")]
    fig, axes = plt.subplots(1, 4, figsize=(6.3, 2.2), sharey=True)
    for ax, (key, name) in zip(axes, JUDGES, strict=True):
        vals = [frac(m[f"E{key}Gap{c}"]) for c, _ in conds]
        assert all(n == 24 for _, n in vals)
        ks = [k for k, _ in vals]
        colors = [GRAY] + [BLUE] * 4
        ax.bar(range(5), ks, color=colors, width=0.62, edgecolor="white", linewidth=1)
        for i, k in enumerate(ks):
            ax.text(i, k + 0.5, str(k), ha="center", va="bottom", color=INK, fontsize=7)
        ax.set_title(name, fontsize=8, color=INK)
        ax.set_xticks(range(5), [label for _, label in conds], rotation=50, ha="right", rotation_mode="anchor",
                      fontsize=6.5)
        ax.set_ylim(0, 27)
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("gap faults caught (of 24)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=GRAY), plt.Rectangle((0, 0), 1, 1, color=BLUE)]
    fig.legend(handles, ["no record (both texts)", "damaged record, as presented"], loc="upper center", ncol=2,
               frameon=False, bbox_to_anchor=(0.5, 1.08), fontsize=7)
    fig.tight_layout()
    fig.savefig(GEN / "fig_gap.pdf", bbox_inches="tight")
    plt.close(fig)


def decoy_figure(m: dict[str, str]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.0), sharey=True)
    for ax, (split, title) in zip(axes, [("Same", "near-identical titles"), ("Different", "different titles")], strict=True):
        x = range(len(JUDGES))
        for off, (kind, color, label) in zip([-0.19, 0.19], [("Catch", BLUE, "fault caught"),
                                                            ("Decoy", ORANGE, "decoy flagged as replaced")], strict=True):
            vals = [frac(m[f"E{key}{split}{kind}"]) for key, _ in JUDGES]
            pct = [100 * k / n for k, n in vals]
            ax.bar([i + off for i in x], pct, width=0.36, color=color, edgecolor="white", linewidth=1, label=label)
            for i, (k, n) in enumerate(vals):
                ax.text(i + off, 100 * k / n + 2, f"{k}/{n}", ha="center", va="bottom", fontsize=5.8, color=INK)
        ax.set_title(f"Pairs with {title}", fontsize=8, color=INK)
        ax.set_xticks(list(x), [name.replace(" ", "\n", 1) for _, name in JUDGES], fontsize=6.5)
        ax.set_ylim(0, 112)
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("% of items (both texts, no record)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.08), fontsize=7)
    fig.tight_layout()
    fig.savefig(GEN / "fig_decoy.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    m = macros()
    # The decoy split covers all 48 pairs; the gap figure's first bar is the H2a baseline.
    for key, _ in JUDGES:
        assert frac(m[f"E{key}SameCatch"])[1] + frac(m[f"E{key}DifferentCatch"])[1] == int(m["ENLinks"])
    gap_figure(m)
    decoy_figure(m)
    print("wrote", GEN / "fig_gap.pdf", GEN / "fig_decoy.pdf")


if __name__ == "__main__":
    main()
