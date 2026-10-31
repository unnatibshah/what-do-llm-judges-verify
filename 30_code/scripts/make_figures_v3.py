"""Draw the Paper A v3 ladder figure and false-alarm figure from a ``ladder.json`` (T7; prereg v3 section 9, figs 1-2).

    python 30_code/scripts/make_figures_v3.py --stage dev --ladder <scratch>/ladder.json \
        --out 60_paper_drafts/paper_v3/generated

Writes ``fig_ladder.pdf``, ``fig_false_alarms.pdf`` and, since D48, ``fig_registry_damage.pdf`` (and PNG copies). A model with no data at a rung gets no point
there. With ``--stage dev`` each figure carries a "DEV PILOT, NOT RESULTS" stamp.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from suryabench import paths  # noqa: E402

RUNGS = ["R0", "R1", "R2", "R3", "R4", "R5"]
# Fixed colour per model (validated categorical slots 1-5), plus a marker so identity never rests on colour alone.
STYLE = {"llama3.1:8b": ("#2a78d6", "o"), "qwen2.5:7b": ("#eb6834", "s"), "qwen2.5:14b": ("#1baf7a", "^"),
         "gemma-4-26b-a4b-it": ("#eda100", "D"), "gemini-3.5-flash-lite": ("#e87ba4", "v")}


def series(models: dict[str, Any], model: str, key: str) -> tuple[list[int], list[float], list[list[float]]]:
    """x positions, clause-averaged rates in percent, and asymmetric CI error bars (0 where refused)."""
    xs: list[int] = []
    ys: list[float] = []
    err: list[list[float]] = [[], []]
    for i, rung in enumerate(RUNGS):
        cell = models.get(model, {}).get(rung, {}).get(key) or {}
        if cell.get("mean") is None:  # not run: a gap, so the line does not join rungs across it
            xs.append(i)
            ys.append(float("nan"))
            err[0].append(0.0)
            err[1].append(0.0)
            continue
        y, ci = 100 * cell["mean"], cell.get("ci95")
        xs.append(i)
        ys.append(y)
        err[0].append(y - 100 * ci[0] if ci else 0.0)
        err[1].append(100 * ci[1] - y if ci else 0.0)
    return xs, ys, err


def panel(ax: Axes, models: dict[str, Any], key: str, title: str) -> None:
    for model, (color, marker) in STYLE.items():
        xs, ys, err = series(models, model, key)
        if any(y == y for y in ys):  # at least one rung run (nan != nan)
            ax.errorbar(xs, ys, yerr=err, color=color, marker=marker, markersize=5, linewidth=1.5, capsize=2,
                        label=model)
    ax.set_xticks(range(len(RUNGS)), RUNGS)
    ax.set_ylim(-3, 103)
    ax.set_title(title, fontsize=9)
    ax.grid(axis="y", color="#e5e4e0", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


STATES = ["intact", "drop25", "drop50", "spurious10"]
# D48 figure: one line per reviewer, same palette rules (colour plus marker plus line style).
REVIEWERS = {"R4": ("LLM + status line (R4)", "#1baf7a", "^", "-"), "R5": ("registry lookup (R5)", "#2a78d6", "s", "-"),
             "R2": ("LLM, no registry (R2)", "#8a8984", "o", "--")}


def damage_panel(ax: Axes, disc: dict[str, Any], model: str) -> None:
    """Discrimination (points) by registry state for R4 and R5; R2 is drawn at every state (it reads no registry)."""
    for rung, (label, color, marker, ls) in REVIEWERS.items():
        xs, ys, err = [], [], [[], []]
        for i, state in enumerate(STATES):
            c = disc.get(f"R2 @ {model}" if rung == "R2" else f"{rung} {state} @ {model}") or {}
            if c.get("mean_diff") is None:
                continue
            y, ci = 100 * c["mean_diff"], c.get("ci95")
            xs.append(i)
            ys.append(y)
            err[0].append(y - 100 * ci[0] if ci else 0.0)
            err[1].append(100 * ci[1] - y if ci else 0.0)
        if xs:
            ax.errorbar(xs, ys, yerr=err, color=color, marker=marker, linestyle=ls, markersize=5, linewidth=1.5,
                        capsize=2, label=label)
    ax.set_xticks(range(len(STATES)), ["intact", "drop 25%", "drop 50%", "spurious 10%"])
    ax.set_ylim(-103, 103)
    ax.axhline(0, color="#c9c8c3", linewidth=0.6)
    ax.set_title(model, fontsize=9)
    ax.grid(axis="y", color="#e5e4e0", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=7)


def save(fig: Any, out: Path, name: str, stage: str) -> None:
    if stage == "dev":
        fig.text(0.99, 0.01, "DEV PILOT, NOT RESULTS", ha="right", va="bottom", fontsize=7, color="#d03b3b")
    fig.tight_layout()
    for ext in ("pdf", "png"):  # no creation date in the PDF, so a rebuild is byte-identical (repro_check_v3.sh)
        fig.savefig(out / f"{name}.{ext}", dpi=200, metadata={"CreationDate": None} if ext == "pdf" else None)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ladder", required=True)
    ap.add_argument("--stage", choices=["dev", "test"], required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    lad = json.loads(paths.resolve(args.ladder).read_text(encoding="utf-8"))
    models = lad["models"]
    out = Path(paths.resolve(args.out))
    out.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(3.3, 2.6))
    panel(ax, models, "catch", "Right-reason catch by rung")
    ax.set_xlabel("rung", fontsize=8)
    ax.set_ylabel("catch (%, clause-averaged)", fontsize=8)
    ax.legend(fontsize=6, frameon=False)
    save(fig, out, "fig_ladder", args.stage)

    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.6), sharey=True)
    panel(axes[0], models, "false_alarm_matched", "Matched controls")
    panel(axes[1], models, "false_alarm_C", "Clean correct answers (C)")
    axes[0].set_ylabel("false alarms (%)", fontsize=8)
    for a in axes:
        a.set_xlabel("rung", fontsize=8)
    axes[1].legend(fontsize=6, frameon=False)
    save(fig, out, "fig_false_alarms", args.stage)

    capable = ["qwen2.5:14b", "gemma-4-26b-a4b-it"]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.8), sharey=True)
    for ax, model in zip(axes, capable, strict=True):
        damage_panel(ax, lad.get("discrimination", {}), model)
        ax.set_xlabel("registry", fontsize=8)
    axes[0].set_ylabel("discrimination (points)", fontsize=8)
    axes[0].legend(fontsize=6, frameon=False)
    save(fig, out, "fig_registry_damage", args.stage)
    print(f"figures -> {out}")


if __name__ == "__main__":
    main()
