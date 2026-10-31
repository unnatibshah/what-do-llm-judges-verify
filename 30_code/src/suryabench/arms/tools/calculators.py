"""Pure calculators for the Arm 2 agent (plan D7, 2026-10-01).

They hold no regulatory value: every limit, slab or deadline is an argument the model reads from the
evidence, and every input is a value the model bound from the application. A calculator therefore
cannot decide an application, and a stale rule in the context can change the decision. (The
rule-encoding tools in this package, ``load_calc``, ``capacity_est``, ``subsidy_calc`` and
``almm_lookup``, are Arm 0's hand-coded rule system and are not given to the agent.)
"""

from typing import Any

from suryabench.arms.tools.almm_lookup import ALMM_LIST_I_MANUFACTURERS


def capacity_vs_limit(proposed_kw: float, reference_kw: float, limit_pct: float) -> dict[str, Any]:
    """Proposed capacity against limit_pct % of a reference quantity (e.g. sanctioned load)."""
    limit_kw = round(reference_kw * limit_pct / 100.0, 3)
    return {"limit_kw": limit_kw, "within_limit": proposed_kw <= limit_kw, "margin_kw": round(limit_kw - proposed_kw, 3)}


def transformer_loading(dt_capacity_kva: float, existing_solar_kw: float, proposed_kw: float,
                        limit_pct: float) -> dict[str, Any]:
    """Cumulative solar on a distribution transformer, including this application, against limit_pct %."""
    cumulative = round(existing_solar_kw + proposed_kw, 3)
    limit_kw = round(dt_capacity_kva * limit_pct / 100.0, 3)
    return {"cumulative_solar_kw": cumulative, "saturation_pct": round(100.0 * cumulative / dt_capacity_kva, 2),
            "limit_kw": limit_kw, "within_limit": cumulative <= limit_kw}


def slab_amount(capacity_kw: float, slabs: list[dict[str, float]], cap_inr: float | None = None,
                units: int = 1) -> dict[str, Any]:
    """Tiered amount: slabs = [{"up_to_kw": x, "rate_inr_per_kw": r}, ...] in ascending order; the last
    slab may omit up_to_kw (no upper bound). Multiplied by ``units`` (e.g. households); capped at cap_inr."""
    total, lower = 0.0, 0.0
    for slab in slabs:
        upper = float(slab.get("up_to_kw", capacity_kw))
        if capacity_kw > lower:
            total += (min(capacity_kw, upper) - lower) * float(slab["rate_inr_per_kw"])
        lower = upper
    total *= units
    if cap_inr is not None:
        total = min(total, float(cap_inr))
    return {"amount_inr": round(total, 2)}


def deadline_check(days_elapsed: float, limit_days: float) -> dict[str, Any]:
    """Elapsed days against a deadline."""
    return {"days_elapsed": days_elapsed, "limit_days": limit_days, "deadline_passed": days_elapsed > limit_days}


def almm_listed(module_make: str) -> dict[str, Any]:
    """Whether the module make appears on the ALMM List-I manufacturer list (a lookup, not a rule)."""
    make = module_make.lower()
    listed = any(m in make for m in ALMM_LIST_I_MANUFACTURERS) and not any(
        w in make for w in ("unlisted", "not_listed", "non-almm"))
    return {"almm_list_i": listed}


CALCULATORS: dict[str, Any] = {
    "capacity_vs_limit": capacity_vs_limit,
    "transformer_loading": transformer_loading,
    "slab_amount": slab_amount,
    "deadline_check": deadline_check,
    "almm_listed": almm_listed,
}

CALCULATOR_DOC = """- capacity_vs_limit(proposed_kw, reference_kw, limit_pct)
- transformer_loading(dt_capacity_kva, existing_solar_kw, proposed_kw, limit_pct)
- slab_amount(capacity_kw, slabs=[{"up_to_kw": x, "rate_inr_per_kw": r}, ...], cap_inr=null, units=1)
- deadline_check(days_elapsed, limit_days)
- almm_listed(module_make)"""


def run_calculator(tool: str, args: Any) -> dict[str, Any]:
    """Run one calculator; a bad call returns an error observation for the model, never raises."""
    fn = CALCULATORS.get(str(tool))
    if fn is None:
        return {"error": f"unknown tool '{tool}'; available: {', '.join(CALCULATORS)}"}
    if not isinstance(args, dict):
        return {"error": "args must be a JSON object"}
    try:
        result: dict[str, Any] = fn(**args)
        return result
    except (TypeError, ValueError, KeyError, ZeroDivisionError) as e:
        return {"error": f"{tool} failed: {e}"}
