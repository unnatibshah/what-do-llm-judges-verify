"""Power simulation for the primary contrast (plan D15, section 4).

Paired evidence-level sensitivity, baseline p0 vs p1. Per cluster c: logit-scale random
intercept u_c ~ N(0, tau) shared by both arms plus effect heterogeneity v_c ~ N(0, tau/2) on
the treated arm; each of m cases is Bernoulli per arm (independent given the cluster).
Test: cluster sign-flip permutation (stats.signflip_signs), two-sided, at alpha/5 (Holm worst
case over 5 contrasts).

    python 30_code/scripts/power_sim.py [--nsim 1000] [--nperm 4000]
"""

import argparse
import json
from pathlib import Path

import numpy as np

from suryabench.analysis.stats import signflip_signs
from suryabench.paths import RESULTS_DIR

CLUSTERS = [5, 8, 10, 12, 15, 20, 25, 30, 40]
CASES = [6, 10, 14, 20]
SCENARIOS = {
    "0.2->0.5, tau=0.5": (0.2, 0.5, 0.5),
    "0.2->0.5, tau=1.0": (0.2, 0.5, 1.0),
    "0.2->0.4, tau=0.5": (0.2, 0.4, 0.5),
    "0.2->0.35, tau=0.5": (0.2, 0.35, 0.5),
}
ALPHA = 0.05 / 5


def _expit(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def power(
    k: int, m: int, p0: float, p1: float, tau: float, nsim: int, nperm: int,
    rng: np.random.Generator,
) -> float:
    u = rng.normal(0, tau, (nsim, k))
    v = rng.normal(0, tau / 2, (nsim, k))
    y0 = rng.binomial(m, _expit(np.log(p0 / (1 - p0)) + u))
    y1 = rng.binomial(m, _expit(np.log(p1 / (1 - p1)) + u + v))
    d = (y1 - y0) / m  # cluster mean paired difference
    signs, _ = signflip_signs(k, nperm, rng)
    null = d @ signs.T / k
    obs = np.abs(d.mean(axis=1))[:, None]
    p = (np.abs(null) >= obs - 1e-12).mean(axis=1)
    return float((p < ALPHA).mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nsim", type=int, default=1000)
    ap.add_argument("--nperm", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--out", default=str(RESULTS_DIR / "power_v2"))
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    res: dict[str, dict[str, dict[str, float]]] = {}
    minc: dict[str, dict[str, int | None]] = {}
    for name, (p0, p1, tau) in SCENARIOS.items():
        res[name] = {
            str(m): {str(k): power(k, m, p0, p1, tau, a.nsim, a.nperm, rng) for k in CLUSTERS}
            for m in CASES
        }
        minc[name] = {
            str(m): next((k for k in CLUSTERS if res[name][str(m)][str(k)] >= 0.8), None)
            for m in CASES
        }
    meta = {
        "nsim": a.nsim, "nperm": a.nperm, "seed": a.seed, "alpha_per_test": ALPHA,
        "clusters": CLUSTERS, "cases_per_cluster": CASES,
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "power.json").write_text(
        json.dumps({"meta": meta, "power": res, "min_clusters_80": minc}, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    md = [
        f"# Power simulation (alpha/5 = {ALPHA}, nsim={a.nsim}, nperm={a.nperm})", "",
        "Minimum clusters (of the grid) for >= 80% power; None = not reached by 40.", "",
        "| Scenario | " + " | ".join(f"m={m}" for m in CASES) + " |",
        "|---|" + "---|" * len(CASES),
    ]
    for n, d in minc.items():
        md.append(f"| {n} | " + " | ".join(str(d[str(m)]) for m in CASES) + " |")
    for n in res:
        md += [
            "", f"## Power: {n}", "",
            "| m \\ k | " + " | ".join(map(str, CLUSTERS)) + " |",
            "|---|" + "---|" * len(CLUSTERS),
        ]
        for m in CASES:
            row = " | ".join(f"{res[n][str(m)][str(k)]:.2f}" for k in CLUSTERS)
            md.append(f"| {m} | {row} |")
    (out / "power.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md[: 6 + len(minc)]))


if __name__ == "__main__":
    main()
