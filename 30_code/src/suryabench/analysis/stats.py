"""Statistical inference pipeline for SuryaBench (protocol §1.4.6, §4.2).

Implements:
1. McNemar paired comparison test with exact binomial and continuity correction; Holm's step-down
   correction over a family of preregistered contrasts.
2. Rule-node clustered bootstrap for hierarchical 95% confidence intervals.
3. Sensitivity and specificity computation over fault-events and non-fault opportunities.
"""

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class McNemarResult:
    """Result of McNemar's paired test."""

    n_discordant_a: int  # b: A correct, B incorrect
    n_discordant_b: int  # c: A incorrect, B correct
    chi2_stat: float
    p_value: float
    odds_ratio: float
    is_significant: bool  # at alpha = 0.05


@dataclass(frozen=True)
class BootstrapCI:
    """Clustered bootstrap confidence interval."""

    point_estimate: float
    ci_lower: float
    ci_upper: float
    std_err: float
    n_clusters: int
    n_replicates: int


def mcnemar_test(
    outcomes_a: list[bool],
    outcomes_b: list[bool],
    alpha: float = 0.05,
    continuity_correction: bool = True,
    exact: bool = False,
) -> McNemarResult:
    """Compute McNemar's paired test for correlated binary classification outcomes.

    Args:
        outcomes_a: Boolean correctness for system A across matched cases.
        outcomes_b: Boolean correctness for system B across matched cases.
        alpha: Significance threshold (default: 0.05).
        continuity_correction: Whether to apply Edwards continuity correction.
        exact: Always use the exact binomial p-value (the preregistered contrasts); otherwise it is
            used only below 25 discordant pairs.

    Returns:
        McNemarResult with discordant pair counts, test statistic, and p-value.
    """
    if len(outcomes_a) != len(outcomes_b):
        raise ValueError(f"Mismatched sample lengths: {len(outcomes_a)} vs {len(outcomes_b)}")

    b = sum(1 for a, b_val in zip(outcomes_a, outcomes_b, strict=True) if a and not b_val)
    c = sum(1 for a, b_val in zip(outcomes_a, outcomes_b, strict=True) if not a and b_val)

    total_discordant = b + c
    if total_discordant == 0:
        return McNemarResult(
            n_discordant_a=0,
            n_discordant_b=0,
            chi2_stat=0.0,
            p_value=1.0,
            odds_ratio=1.0,
            is_significant=False,
        )

    odds_ratio = (b / c) if c > 0 else float("inf")

    # If small discordant count, compute exact two-tailed binomial p-value
    if exact or total_discordant < 25:
        # Two-tailed binomial with p=0.5
        min_bc = min(b, c)
        p_val = 2.0 * sum(
            math.comb(total_discordant, k) * (0.5**total_discordant) for k in range(min_bc + 1)
        )
        p_val = min(1.0, p_val)
        chi2 = ((abs(b - c) - (1 if continuity_correction else 0)) ** 2) / total_discordant
        return McNemarResult(
            n_discordant_a=b,
            n_discordant_b=c,
            chi2_stat=round(chi2, 4),
            p_value=round(p_val, 5),
            odds_ratio=round(odds_ratio, 4),
            is_significant=p_val < alpha,
        )

    # Asymptotic chi-square test with 1 degree of freedom
    diff: float = float(abs(b - c))
    if continuity_correction:
        diff = max(0.0, diff - 1.0)

    chi2 = (diff**2) / total_discordant
    # Survival function for chi2 with df=1 is 2 * (1 - Phi(sqrt(chi2))) = erfc(sqrt(chi2/2))
    p_val = math.erfc(math.sqrt(chi2 / 2.0))

    return McNemarResult(
        n_discordant_a=b,
        n_discordant_b=c,
        chi2_stat=round(chi2, 4),
        p_value=round(p_val, 5),
        odds_ratio=round(odds_ratio, 4),
        is_significant=p_val < alpha,
    )


def cluster_bootstrap_ci(
    records: list[dict[str, Any]],
    cluster_key: str,
    metric_fn: Callable[[list[dict[str, Any]]], float],
    n_replicates: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> BootstrapCI:
    """Compute 95% confidence intervals via rule-node cluster resampling.

    Per protocol §4.2.2, individual benchmark cases share rule nodes and cannot
    be treated as independent i.i.d. observations. Resampling is performed by
    clustering over the governing rule node with replacement.

    Args:
        records: List of case result records containing cluster_key.
        cluster_key: Dict key identifying the rule node cluster.
        metric_fn: Function mapping resampled records to a float metric.
        n_replicates: Number of bootstrap resamples (default: 1000).
        ci: Desired confidence level (default: 0.95).
        seed: Random seed for deterministic reproducibility.

    Returns:
        BootstrapCI with point estimate, lower bound, upper bound, and SE.
    """
    import random

    if not records:
        raise ValueError("Cannot bootstrap empty records")

    # Group records by cluster
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        key = str(r.get(cluster_key, "default_cluster"))
        clusters[key].append(r)

    cluster_ids = list(clusters.keys())
    n_clusters = len(cluster_ids)

    # Point estimate on full sample
    point_estimate = metric_fn(records)

    if n_clusters < 2:
        # Cannot meaningfully cluster-resample fewer than 2 clusters
        return BootstrapCI(
            point_estimate=round(point_estimate, 4),
            ci_lower=round(point_estimate, 4),
            ci_upper=round(point_estimate, 4),
            std_err=0.0,
            n_clusters=n_clusters,
            n_replicates=0,
        )

    rng = random.Random(seed)
    boot_estimates: list[float] = []

    for _ in range(n_replicates):
        resampled_clusters = rng.choices(cluster_ids, k=n_clusters)
        resampled_records: list[dict[str, Any]] = []
        for cid in resampled_clusters:
            resampled_records.extend(clusters[cid])

        boot_estimates.append(metric_fn(resampled_records))

    boot_estimates.sort()

    alpha = 1.0 - ci
    lower_idx = int(math.floor(alpha / 2.0 * n_replicates))
    upper_idx = int(math.ceil((1.0 - alpha / 2.0) * n_replicates)) - 1

    ci_lower = boot_estimates[max(0, lower_idx)]
    ci_upper = boot_estimates[min(n_replicates - 1, upper_idx)]

    # Standard error
    mean_boot = sum(boot_estimates) / n_replicates
    variance = sum((x - mean_boot) ** 2 for x in boot_estimates) / (n_replicates - 1)
    std_err = math.sqrt(variance)

    return BootstrapCI(
        point_estimate=round(point_estimate, 4),
        ci_lower=round(ci_lower, 4),
        ci_upper=round(ci_upper, 4),
        std_err=round(std_err, 4),
        n_clusters=n_clusters,
        n_replicates=n_replicates,
    )


def holm(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, dict[str, float | bool]]:
    """Holm step-down correction: adjusted p-value and rejection for each named contrast."""
    order = sorted(p_values, key=lambda k: p_values[k])
    m = len(order)
    out: dict[str, dict[str, float | bool]] = {}
    running = 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (m - i) * p_values[k]))  # monotone adjusted p
        out[k] = {"p": p_values[k], "p_holm": round(running, 5), "reject": running < alpha}
    return out


# --- Paper A v2 statistics (decision D15): the unit of analysis is the cluster. ---------------

MAX_FAMILY = 10  # preregistered family size: 5 (plan section 4), 8 (D48 amendment 1), 10 (D49 amendment 2)
MIN_BOOT_CLUSTERS = 10


@dataclass(frozen=True)
class PermResult:
    """Sign-flip permutation result on cluster-level mean paired differences."""

    p: float
    observed: float  # mean of cluster-level mean differences
    n_clusters: int
    exact: bool


def cluster_means(diffs_by_cluster: dict[str, list[float]] | list[list[float]]) -> np.ndarray:
    """Mean paired difference per cluster (clusters with no cases are rejected)."""
    groups = (
        list(diffs_by_cluster.values())
        if isinstance(diffs_by_cluster, dict)
        else diffs_by_cluster
    )
    if not groups or any(len(g) == 0 for g in groups):
        raise ValueError("every cluster needs at least one paired difference")
    return np.array([float(np.mean(g)) for g in groups])


def signflip_signs(k: int, n_perm: int, rng: np.random.Generator) -> tuple[np.ndarray, bool]:
    """Sign matrix (rows = permutations, +-1). Exact full enumeration if 2^k <= n_perm.

    The Monte Carlo matrix always includes the identity row, so p is never 0.
    """
    if 2**k <= n_perm:
        bits = (np.arange(2**k)[:, None] >> np.arange(k)) & 1
        return 1.0 - 2.0 * bits, True
    signs = rng.choice((-1.0, 1.0), size=(n_perm, k))
    signs[0] = 1.0
    return signs, False


def _perm_p(means: np.ndarray, alternative: str, n_perm: int, seed: int) -> tuple[float, bool]:
    """alternative: 'two-sided' | 'greater' | 'less' on the mean of `means`."""
    signs, exact = signflip_signs(len(means), n_perm, np.random.default_rng(seed))
    null = signs @ means / len(means)
    obs = float(np.mean(means))
    tol = 1e-12
    if alternative == "two-sided":
        hits = np.abs(null) >= abs(obs) - tol
    elif alternative == "greater":
        hits = null >= obs - tol
    else:
        hits = null <= obs + tol
    return float(np.mean(hits)), exact


def cluster_permutation_test(
    paired_diffs_by_cluster: dict[str, list[float]] | list[list[float]],
    n_perm: int = 10000,
    seed: int = 42,
) -> PermResult:
    """Two-sided sign-flip permutation test on cluster-level mean paired differences.

    Exact enumeration when 2^k <= n_perm, otherwise n_perm random sign vectors (identity
    included). The statistic is the mean of the cluster means.
    """
    means = cluster_means(paired_diffs_by_cluster)
    p, exact = _perm_p(means, "two-sided", n_perm, seed)
    return PermResult(p=p, observed=float(np.mean(means)), n_clusters=len(means), exact=exact)


def cluster_one_sample_test(
    values_by_cluster: dict[str, list[float]] | list[list[float]],
    mu0: float,
    alternative: str = "less",
    n_perm: int = 10000,
    seed: int = 42,
) -> PermResult:
    """One-sample sign-flip permutation test of the mean of cluster means against ``mu0``.

    ``alternative``: "less" (H1: mean < mu0), "greater" or "two-sided". Cluster means are centred
    at ``mu0`` and signs flipped; exact when 2^k <= n_perm, so the smallest attainable p is 2^-k.
    ``observed`` is the uncentred mean of cluster means.
    """
    means = cluster_means(values_by_cluster)
    p, exact = _perm_p(means - mu0, alternative, n_perm, seed)
    return PermResult(p=p, observed=float(np.mean(means)), n_clusters=len(means), exact=exact)


def cluster_bootstrap_ci_checked(
    records: list[dict[str, Any]],
    cluster_key: str,
    metric_fn: Callable[[list[dict[str, Any]]], float],
    n_replicates: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[BootstrapCI | None, str | None]:
    """Like :func:`cluster_bootstrap_ci` but refuses: (None, reason) if < 10 clusters or the
    interval is degenerate (zero width / zero SE). Otherwise (result, None)."""
    n = len({str(r.get(cluster_key, "default_cluster")) for r in records})
    if n < MIN_BOOT_CLUSTERS:
        return None, f"only {n} clusters (< {MIN_BOOT_CLUSTERS})"
    res = cluster_bootstrap_ci(records, cluster_key, metric_fn, n_replicates, ci, seed)
    if res.ci_upper <= res.ci_lower or res.std_err == 0.0:
        return None, "degenerate interval (zero width)"
    return res, None


@dataclass(frozen=True)
class TostResult:
    p: float  # max of the two one-sided p-values
    observed: float
    margin: float
    n_clusters: int
    equivalent: bool
    conclusion: str


def tost_equivalence(
    paired_diffs_by_cluster: dict[str, list[float]] | list[list[float]],
    margin: float,
    alpha: float = 0.05,
    n_perm: int = 10000,
    seed: int = 42,
) -> TostResult:
    """Permutation TOST on cluster-level mean differences against equivalence bounds +-margin.

    H0a: mean <= -margin; H0b: mean >= +margin (each by sign-flip on the shifted means).
    Equivalence is concluded only if both are rejected at alpha.
    """
    if margin <= 0:
        raise ValueError("margin must be positive and preregistered")
    means = cluster_means(paired_diffs_by_cluster)
    p_lo, _ = _perm_p(means + margin, "greater", n_perm, seed)
    p_hi, _ = _perm_p(means - margin, "less", n_perm, seed)
    p = max(p_lo, p_hi)
    eq = p < alpha
    return TostResult(
        p=p,
        observed=float(np.mean(means)),
        margin=margin,
        n_clusters=len(means),
        equivalent=eq,
        conclusion=(
            f"equivalent within +-{margin}" if eq else f"equivalence not shown within +-{margin}"
        ),
    )


def holm_family(named_p: dict[str, float], alpha: float = 0.05) -> dict[str, dict[str, float | bool]]:
    """Holm over a named preregistered family (at most 5 contrasts).

    Returns {name: {p, p_holm, reject}}; `reject` is the decision at `alpha`.
    """
    if not named_p or len(named_p) > MAX_FAMILY:
        raise ValueError(f"family must hold 1..{MAX_FAMILY} preregistered contrasts")
    if any(not 0.0 <= v <= 1.0 for v in named_p.values()):
        raise ValueError("p-values must lie in [0, 1]")
    return holm(named_p, alpha)


@dataclass(frozen=True)
class CoPrimaryResult:
    improves: bool
    sens_diff: float
    sens_p: float
    sens_significant: bool
    fpr_diff: float
    fpr_noninferior_p: float
    fpr_noninferior: bool


def coprimary_improvement(
    sens_diffs_by_cluster: dict[str, list[float]] | list[list[float]],
    fpr_diffs_by_cluster: dict[str, list[float]] | list[list[float]],
    sens_alpha: float = 0.05,
    fpr_margin: float = 0.10,
    alpha: float = 0.05,
    n_perm: int = 10000,
    seed: int = 42,
) -> CoPrimaryResult:
    """Co-primary rule: improves only if sensitivity rises AND FPR rises by <= fpr_margin.

    Sensitivity: permutation p (two-sided) with observed difference > 0, judged at `sens_alpha`
    (set it to the Holm threshold for the contrast's rank, or compute p_holm with `holm_family`
    and pass sens_alpha=1.0 after checking it yourself). FPR: one-sided non-inferiority,
    H0: mean FPR increase >= margin, sign-flip on (diff - margin), rejected at `alpha`.
    Diffs are (configuration - baseline).
    """
    sens = cluster_permutation_test(sens_diffs_by_cluster, n_perm, seed)
    sens_ok = sens.observed > 0 and sens.p < sens_alpha
    fm = cluster_means(fpr_diffs_by_cluster)
    p_ni, _ = _perm_p(fm - fpr_margin, "less", n_perm, seed)
    ni = p_ni < alpha
    return CoPrimaryResult(
        improves=sens_ok and ni,
        sens_diff=sens.observed,
        sens_p=sens.p,
        sens_significant=sens_ok,
        fpr_diff=float(np.mean(fm)),
        fpr_noninferior_p=p_ni,
        fpr_noninferior=ni,
    )
