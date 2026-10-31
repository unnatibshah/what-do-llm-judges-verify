"""T10: apply PREREGISTRATION_v3 section 6 (reading the primary result, Holm) and section 7 (stop rules), and since D48
amendment 1 section 4 (readings A4.1 to A4.5 on the new primary family; v3's ladder readings become secondary and
uncorrected), mechanically
to a ``ladder.json``, and write ``CLAIMS-APPROVED.md``: each claim, its wording, whether it was preregistered and the
rule applied. The pre-written sentences are read from the prereg itself, so they cannot drift from what was signed.
The authors confirm the file (USER-TASKS U5); this script decides nothing they have not already registered.

    python 30_code/scripts/make_claims_v3.py --ladder <dir>/ladder.json --out 80_review/CLAIMS-APPROVED.md
    python 30_code/scripts/make_claims_v3.py --ladder <scratch>/ladder.json --out <scratch>/CLAIMS.md --label DEV
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from suryabench import paths
from suryabench.analysis.ladder import CAPABLE, NET_PRIMARY, WEAK

PREREG = paths.METHOD_DIR / "PREREGISTRATION_v3.md"
AMENDMENT = paths.METHOD_DIR / "PREREGISTRATION_v3_AMENDMENT_1_DRAFT.md"  # D48; rename here when it is signed
SECONDARY = "gemini-3.5-flash-lite"
MIN_CLAUSES, WITHIN, SCORER_MIN = 10, 0.10, 0.95  # prereg sections 7.1, 7.4/7.5, 7.7


def sentences(prereg: Path = PREREG) -> dict[int, str]:
    """Stop rule number -> its pre-written sentence (the last double-quoted text of the rule in section 7; rule 6's
    title is quoted too)."""
    text = prereg.read_text(encoding="utf-8")
    sec = text[text.index("## 7. Stop rules"):text.index("## 8.")]
    out = {}
    for m in re.finditer(r"^(\d+)\. \*\*(.+?)(?=^\d+\. \*\*|^Every outcome|\Z)", sec, re.M | re.S):
        quotes = re.findall(r'"([^"]+)"', " ".join(m.group(2).split()))
        if quotes:
            out[int(m.group(1))] = quotes[-1]
    return out


def amendment_sentences(amendment: Path = AMENDMENT) -> dict[int, list[str]]:
    """D48 reading number -> its quoted sentences, in order (amendment section 4)."""
    text = amendment.read_text(encoding="utf-8")
    sec = text[text.index("## 4. Pre-written readings"):text.index("## 5.")]
    out = {}
    for m in re.finditer(r"^(\d+)\. (.+?)(?=^\d+\. |^v3 rule|\Z)", sec, re.M | re.S):
        out[int(m.group(1))] = re.findall(r'"([^"]+)"', " ".join(m.group(2).split()))
    return out


def d47_rules(lad: dict[str, Any], capable: list[str]) -> list[dict[str, str]]:
    """Amendment 1 section 4, readings 1 to 5, per capable model run."""
    said = amendment_sentences()
    con, models = lad.get("contrasts", {}), lad.get("models", {})
    rows: list[dict[str, str]] = []

    def sig(c: dict[str, Any], sign: int) -> bool:
        return bool(c.get("holm_reject")) and sign * (c.get("mean_diff") or 0) > 0

    for m in capable:
        net = {s: con.get(f"Net-{s} @ {m}", {}) for s in NET_PRIMARY}
        shown = ", ".join(f"{s} {c.get('mean_diff', 'not run')} (Holm p {c.get('p_holm', '-')})" for s, c in net.items())
        damaged_up = [s for s in NET_PRIMARY if s != "intact" and sig(net[s], +1)]
        if not any(sig(c, +1) for c in net.values()):
            rows.append({"claim": f"Reviewer adds nothing over the registry ({m})", "wording": said[1][0],
                         "prereg": "Y", "rule": f"A4.1: R4 - R5 not positive after Holm at any state; {shown}"})
        elif damaged_up and not sig(net["intact"], +1):
            rows.append({"claim": f"Value only under damage ({m})",
                         "wording": said[2][0].replace("[the first such state]", damaged_up[0]), "prereg": "Y",
                         "rule": f"A4.2: {shown}"})
        if sig(net["intact"], -1):
            rows.append({"claim": f"Reviewer worse than the registry ({m})", "wording": said[3][0], "prereg": "Y",
                         "rule": f"A4.3: R4 - R5 intact {net['intact'].get('mean_diff')}, Holm p {net['intact'].get('p_holm')}"})
        defer = con.get(f"Defer @ {m}")
        if defer:
            rows.append({"claim": f"Deference ({m})", "wording": said[4][0] if sig(defer, +1) else said[4][1],
                         "prereg": "Y", "rule": f"A4.4: deference {defer.get('mean_diff')}, Holm p {defer.get('p_holm', '-')}"})
        for rung in ("R0", "R1", "R2"):
            cell = models.get(m, {}).get(rung, {})
            loose, strict = (cell.get("catch_any") or {}).get("mean"), (cell.get("catch") or {}).get("mean")
            if loose is not None and strict is not None and loose - strict > WITHIN:
                rows.append({"claim": f"Flag scoring inflates catches ({m}, {rung})",
                             "wording": said[5][0].replace("[the gap]", f"{100 * (loose - strict):.0f}"), "prereg": "Y",
                             "rule": f"A4.5: any-finding {loose} vs right-reason {strict} at {rung}"})
    return rows


def catch(lad: dict[str, Any], model: str, rung: str) -> float | None:
    return ((lad.get("models", {}).get(model, {}).get(rung) or {}).get("catch") or {}).get("mean")


def apply_rules(lad: dict[str, Any], scorer_agreement: float | None = None) -> list[dict[str, str]]:
    said = sentences()
    models, con = lad.get("models", {}), lad.get("contrasts", {})
    capable = [m for m in CAPABLE if m in models]
    fallback = "gemma-4-26b-a4b-it" not in models
    required = ["qwen2.5:14b"] if fallback else list(CAPABLE)
    n_clauses = max([c.get("clauses", 0) for c in con.values()] +
                    [(r.get("catch") or {}).get("units", 0) for m in models.values() for r in m.values()] or [0])
    rows: list[dict[str, str]] = []

    def add(claim: str, wording: str, prereg: bool, rule: str) -> None:
        rows.append({"claim": claim, "wording": wording, "prereg": "Y" if prereg else "N", "rule": rule})

    if fallback:
        add("API fallback", "The primary analysis uses the local models; qwen2.5:14b is the only capable model and the "
            "primary family has four tests.", True, "7.8 / section 4 API fallback (gemma-4-26b-a4b-it not in ladder)")
    if n_clauses < MIN_CLAUSES:
        add("No primary claim", said[1].replace("k distinct", f"{n_clauses} distinct"), True,
            f"7.1: {n_clauses} distinct clauses < {MIN_CLAUSES}")

    if n_clauses >= MIN_CLAUSES:
        rows += d47_rules(lad, capable)

    # v3 section 6, secondary since D48: the same readings on uncorrected sign-flip p
    def significant(c: dict[str, Any]) -> bool:
        return c.get("signflip_p") is not None and c["signflip_p"] < 0.05

    lifted, not_enough = {}, {}
    for m in capable:
        lift = con.get(f"R4-R2 @ {m}", {})
        lifted[m] = significant(lift) and (lift.get("mean_diff") or 0) > 0
        add(f"R4 lifts {m}", f"R4 - R2 = {lift.get('mean_diff', 'not run')}, p = {lift.get('signflip_p', 'not run')}: "
            + ("R4 lifts this capable model." if lifted[m] else "not shown."), True,
            "6: R4 - R2 > 0 with uncorrected p < 0.05 (secondary, D48)")
        base, r2, r4 = con.get(f"R2-R0 @ {m}", {}), catch(lad, m, "R2"), catch(lad, m, "R4")
        not_enough[m] = (bool(base) and not significant(base) and r2 is not None and r4 is not None and r2 < r4 / 2)
        add(f"Both versions not enough ({m})", f"R2 - R0 p = {base.get('signflip_p', 'not run')}, R2 catch {r2}, R4 catch "
            f"{r4}: " + ("seeing both versions is not enough." if not_enough[m] else "not shown."), True,
            "6: R2 - R0 not significant and R2 < R4 / 2 (secondary, D48)")
    ladder_ok = (n_clauses >= MIN_CLAUSES and all(m in capable for m in required)
                 and all(lifted[m] and not_enough[m] for m in required))
    add("Ladder claim (secondary, D48)", "Supported for " + ", ".join(required) + "." if ladder_ok else
        "Not supported: no ladder claim is made.", True, "6: needs both readings for "
        + ("qwen2.5:14b alone (API fallback)" if fallback else "both capable models"))

    if capable and all((catch(lad, m, "R2") or 0) >= (catch(lad, m, "R4") or 0) for m in capable):
        add("Retrieval is the bottleneck", said[2], True, "7.2: R2 >= R4 for every capable model")
    if capable and not all(lifted[m] for m in capable):
        add("R4 does not lift", said[3], True, "7.3: R4 - R2 not significant (uncorrected, D48) for "
            + ", ".join(m for m in capable if not lifted[m]))
    for w in (m for m in WEAK if m in models):
        r2, r4 = catch(lad, w, "R2"), catch(lad, w, "R4")
        if r2 is not None and r4 is not None and abs(r4 - r2) <= WITHIN:
            add(f"Weak model ignores the status ({w})", said[4] + " (reported as a limit of the claim)", True,
                f"7.4: R4 {r4} within 10 points of R2 {r2}")
    r2, r4 = catch(lad, SECONDARY, "R2"), catch(lad, SECONDARY, "R4")
    if r2 is not None and r4 is not None and abs(r4 - r2) <= WITHIN:
        add("Stronger model closes the gap", said[5] + " (goes in the abstract)", True,
            f"7.5: {SECONDARY} R2 {r2} within 10 points of R4 {r4}")
    for m, rungs in models.items():
        cc = [rungs[r] for r in ("R0-cc", "R1-cc", "R2-cc") if r in rungs]
        uses = sum((c.get("cant_confirm_fault") or {}).get("k", 0) + (c.get("cant_confirm_correct") or {}).get("k", 0)
                   for c in cc)
        if cc and uses == 0:
            add(f"Can't confirm unused ({m})", said[6] + " E2 is reported as a null result.", True,
                "7.6: 0 uses at R0-cc to R2-cc")
    if scorer_agreement is not None and scorer_agreement < SCORER_MIN:
        add("Scorer check failed", "Gate: the scorer must be fixed before sealing; no claim until it is.", True,
            f"7.7: agreement {scorer_agreement:.0%} < 95%")
    return rows


def render(rows: list[dict[str, str]], source: str, label: str | None) -> str:
    head = ["# CLAIMS-APPROVED (T10)", ""]
    if label:
        head += [f"**{label}: NOT RESULTS.** Generated from `{source}` to test the machinery; no claim here may be "
                 "used in the paper.", ""]
    head += [f"Generated by `30_code/scripts/make_claims_v3.py` from `{source}`, applying PREREGISTRATION_v3 "
             "sections 6 and 7 mechanically. Quoted wording is the prereg's own. The authors confirm this file (U5); "
             "stop rule 9 (dates) is checked by hand.", "",
             "| Claim | Wording | Preregistered | Rule applied |", "|---|---|---|---|"]
    body = [f"| {r['claim']} | {r['wording'].replace('|', '/')} | {r['prereg']} | {r['rule']} |" for r in rows]
    return "\n".join(head + body) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ladder", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", help="e.g. DEV: stamps the file as not results")
    ap.add_argument("--scorer-agreement", type=float, help="human scorer check agreement, 0-1 (stop rule 7)")
    args = ap.parse_args()
    lad = json.loads(paths.resolve(args.ladder).read_text(encoding="utf-8"))
    rows = apply_rules(lad, args.scorer_agreement)
    out = Path(args.out)
    out.write_text(render(rows, args.ladder, args.label), encoding="utf-8", newline="\n")
    print(f"{len(rows)} claims -> {out}")


if __name__ == "__main__":
    main()
