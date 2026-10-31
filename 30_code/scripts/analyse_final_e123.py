"""D52: analysis of E1-E3 (decoys, framing arms, 48 links) over the blocks in ``evalkit_rfc_v2``.

    PYTHONPATH=30_code/src python 30_code/scripts/analyse_final_e123.py [--out 50_analysis/results/evalkit_rfc_v2]

Rescores every reply from its raw text (``evalkit.score``) and stops if a stored score differs. Writes
``analysis/e123.json``, ``analysis/e123.md`` and ``analysis/items.csv`` (one row per model x context x item).
Tests (lock v2): H1 fault catch vs matched-decoy validity FA with both texts (paired by link index, bootstrap over
pairs); H2a dropped-link catch, ``status-damaged`` vs ``both-texts``; H2b each framing arm vs ``status-damaged``;
exact McNemar, Holm within each family.
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from suryabench import evalkit as ek
from suryabench.paths import RESULTS_DIR, resolve

ARMS = ("norecord-damaged", "lowauth-damaged", "caveat-damaged")


def cp(k: int, n: int) -> list[float]:
    """Wilson 95% interval."""
    z, ph = 1.96, k / n
    c = (ph + z * z / (2 * n)) / (1 + z * z / n)
    h = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def kn(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    k, n = sum(bool(r[key]) for r in rows), len(rows)
    return {"k": k, "n": n, "ci": cp(k, n) if n else None}


def holm(ps: dict[str, float]) -> dict[str, float]:
    out, m, run = {}, len(ps), 0.0
    for i, (name, p) in enumerate(sorted(ps.items(), key=lambda x: x[1])):
        run = max(run, min(1.0, (m - i) * p))
        out[name] = round(run, 6)
    return out


def paired(a: dict[str, bool], b: dict[str, bool]) -> dict[str, Any]:
    ids = sorted(a.keys() & b.keys())
    lost = sum(a[i] and not b[i] for i in ids)
    gained = sum(b[i] and not a[i] for i in ids)
    return {"items": len(ids), "first": sum(a[i] for i in ids), "second": sum(b[i] for i in ids),
            "lost": lost, "gained": gained, "p": round(ek.mcnemar(lost, gained), 6)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(RESULTS_DIR / "evalkit_rfc_v2"))
    ap.add_argument("--tex", help="folder for numbers_e123.tex and tab_e123_*.tex (paper_v5/generated)")
    a = ap.parse_args()
    out = Path(resolve(a.out))
    docs, links, _ = ek.rfc_links()
    dec = ek.rfc_decoys(links, docs)
    by_id = {it.item_id: it for it in ek.items(links, docs) + ek.decoy_items(dec, docs)}
    res: dict[str, Any] = {"decoy_balance": ek.decoy_balance(links, dec, docs), "models": {}}
    from difflib import SequenceMatcher
    from statistics import median
    res["abstract_overlap_median"] = {
        f"{name}_{'same' if st else 'different'}": round(median(
            SequenceMatcher(None, ek.scrub(docs[x.old].text, x.new), ek.scrub(docs[x.new].text, x.old)).ratio() for x in pairs
            if ek.same_title(docs[x.old].title, docs[x.new].title) == st), 2)
        for name, pairs in (("links", links), ("decoys", dec)) for st in (True, False)}
    items_csv: list[dict[str, Any]] = []
    h2a, h2b = {}, {}
    for mdir in sorted(p for p in out.iterdir() if p.is_dir() and (p / "both-texts.json").exists()):
        blocks = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in mdir.glob("*.json")}
        model = blocks["both-texts"]["model"]
        m: dict[str, Any] = {"contexts": {}, "code_hash": sorted({b["code_hash"] for b in blocks.values()})}
        rows_by: dict[str, dict[str, dict[str, Any]]] = {}
        for ctx, b in blocks.items():
            for r in b["rows"]:  # independent rescoring from the raw reply
                it = by_id[r["item_id"]]
                s = ek.score(it, r["reply"], ek.masked_ids(it) if ctx == "both-masked" else None)
                if any(s[k] != r[k] for k in ("right", "any", "validity", "invalid")):
                    raise SystemExit(f"rescore mismatch {model} {ctx} {r['item_id']}")
                items_csv.append({"model": model, "context": ctx, "item_id": r["item_id"], "role": r["role"],
                                  "dropped": r.get("dropped", False), "right": r["right"], "any": r["any"],
                                  "validity": r["validity"], "invalid": r["invalid"],
                                  "kind": ek.rationale_kind(r["reply"]) if r["role"] == "fault" else ""})
            rows_by[ctx] = {r["item_id"]: r for r in b["rows"]}
            role = lambda x, rs=b["rows"]: [r for r in rs if r["role"] == x]  # noqa: E731
            m["contexts"][ctx] = {"fault_right": kn(role("fault"), "right"), "fault_any": kn(role("fault"), "any"),
                                  "control_validity": kn(role("control"), "validity"),
                                  "control_any": kn(role("control"), "any"),
                                  "date_validity": kn(role("date-control"), "validity"),
                                  "decoy_validity": kn(role("decoy"), "validity"), "decoy_any": kn(role("decoy"), "any"),
                                  "invalid": sum(r["invalid"] for r in b["rows"])}
        # H1: paired by link index (decoy i is matched to link i)
        bt = rows_by["both-texts"]
        d = [float(bt[f"{lk.old}>{lk.new}#fault"]["right"]) - float(bt[f"{x.old}>{x.new}#decoy"]["validity"])
             for lk, x in zip(links, dec, strict=True)]
        rng = np.random.default_rng(0)
        bs = [float(np.mean(rng.choice(d, len(d)))) for _ in range(2000)]
        split = {}
        for kind in ("same", "different"):
            idx = [i for i, lk in enumerate(links) if ek.same_title(docs[lk.old].title, docs[lk.new].title) == (kind == "same")]
            split[kind] = {"fault_right": sum(bt[f"{links[i].old}>{links[i].new}#fault"]["right"] for i in idx),
                           "decoy_validity": sum(bt[f"{dec[i].old}>{dec[i].new}#decoy"]["validity"] for i in idx),
                           "n": len(idx)}
        def asim(lk: ek.Link) -> float:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, ek.scrub(docs[lk.old].text, lk.new), ek.scrub(docs[lk.new].text, lk.old)).ratio()
        st_dec = [(asim(x), bool(bt[f"{x.old}>{x.new}#decoy"]["validity"])) for x in dec
                  if ek.same_title(docs[x.old].title, docs[x.new].title)]
        df_lk = [(asim(lk), bool(bt[f"{lk.old}>{lk.new}#fault"]["right"])) for lk in links
                 if not ek.same_title(docs[lk.old].title, docs[lk.new].title)]
        m["abstract_overlap"] = {  # exploratory, threshold 0.3 on difflib ratio of the two abstracts as the judge saw them (scrubbed)
            "same_title_decoy_fa": {k: f"{sum(f for s, f in st_dec if (s >= 0.3) == hi)}/{sum((s >= 0.3) == hi for s, _ in st_dec)}"
                                    for k, hi in (("high", True), ("low", False))},
            "diff_title_fault_catch": {k: f"{sum(f for s, f in df_lk if (s >= 0.3) == hi)}/{sum((s >= 0.3) == hi for s, _ in df_lk)}"
                                       for k, hi in (("high", True), ("low", False))}}
        m["H1"] = {"disc_mean": round(float(np.mean(d)), 4), "ci95": [round(float(np.percentile(bs, q)), 4)
                                                                      for q in (2.5, 97.5)], "by_title": split}
        res["models"][model] = m
        if "status-damaged" not in rows_by:  # a partial run: H1 only
            continue
        # H2a / H2b on the dropped-link faults
        dropped = [i for i, r in rows_by["status-damaged"].items() if r["role"] == "fault" and r["dropped"]]
        catch = {ctx: {i: bool(rows_by[ctx][i]["right"]) for i in dropped} for ctx in rows_by if ctx != "status"}
        m["H2a"] = paired(catch["both-texts"], catch["status-damaged"])
        h2a[model] = m["H2a"]["p"]
        m["H2b"] = {}
        for arm in ARMS:
            if arm in catch:
                m["H2b"][arm] = paired(catch["status-damaged"], catch[arm])
                m["H2b"][arm]["vs_own"] = paired(catch["both-texts"], catch[arm])
                h2b[f"{model}|{arm}"] = m["H2b"][arm]["p"]
        m["bare_pass"] = {ctx: sum(ek.rationale_kind(rows_by[ctx][i]["reply"]) == "pass, no finding" for i in dropped)
                          for ctx in catch}
        m["dropped_catch"] = {ctx: kn([rows_by[ctx][i] for i in dropped], "right") for ctx in catch}
        if "conflict-damaged" in rows_by:  # exploratory arm (2026-10-31): the record_conflict code, no test
            cr = rows_by["conflict-damaged"]
            m["conflict_code"] = {"gap": sum(bool(cr[i].get("conflict")) for i in dropped), **{
                role: sum(bool(r.get("conflict")) for r in cr.values() if r["role"] == role)
                for role in ("fault", "control", "date-control", "decoy")}}
        first24 = {f"{lk.old}>{lk.new}#fault" for lk in links[:24]}  # v2 reused pilot text-only replies there (v3 re-asked them)
        fresh = [i for i in dropped if i not in first24]
        m["fresh_gap"] = {"n": len(fresh), "own": sum(catch["both-texts"][i] for i in fresh),
                          "with_record": sum(catch["status-damaged"][i] for i in fresh)}
        pilot = RESULTS_DIR / "evalkit_rfc" / mdir.name / "status-damaged.json"
        if pilot.exists():  # exploratory: the pilot's gap items (damaged record over 24 links) against these
            prow = {r["item_id"]: r for r in json.loads(pilot.read_text(encoding="utf-8"))["rows"]
                    if r["role"] == "fault" and r["dropped"]}
            both = sorted(prow.keys() & set(dropped))
            only = sorted(prow.keys() - set(dropped))
            m["pilot_overlap"] = {"pilot_items": len(prow), "shared": len(both),
                                  "shared_same_reply": sum(prow[i]["reply"] == rows_by["status-damaged"][i]["reply"] for i in both),
                                  "shared_caught": sum(bool(rows_by["status-damaged"][i]["right"]) for i in both),
                                  "pilot_only": len(only), "pilot_only_caught": sum(bool(prow[i]["right"]) for i in only)}
    for name, ps in (("H2a", h2a), ("H2b", h2b)):
        res[f"holm_{name}"] = holm(ps)
    res["seed1"] = seed_one(out.parent / (out.name + "_seed1"), out, links)
    prev = out.parent / "evalkit_rfc_v2"
    if out.name == "evalkit_rfc_v3" and prev.exists():  # v3 re-asked the pilot's prompts: scores that changed vs v2
        res["reask"] = {}
        for mdir in sorted(p for p in out.iterdir() if (prev / p.name / "both-texts.json").exists()):
            n = changed = 0
            for f in (prev / mdir.name).glob("*.json"):
                old = {r["item_id"]: r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}
                for r in json.loads((mdir / f.name).read_text(encoding="utf-8"))["rows"]:
                    n += 1
                    changed += any(r[k] != old[r["item_id"]][k] for k in ("right", "any", "validity"))
            res["reask"][mdir.name] = {"items": n, "changed": changed}
    adir = out / "analysis"
    adir.mkdir(exist_ok=True)
    (adir / "e123.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    with (adir / "items.csv").open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=list(items_csv[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(items_csv)
    if res["seed1"].get("link_rows"):
        with (adir / "seed1_links.csv").open("w", encoding="utf-8", newline="\n") as fh:
            w = csv.DictWriter(fh, fieldnames=list(res["seed1"]["link_rows"][0]), lineterminator="\n")
            w.writeheader()
            w.writerows(res["seed1"]["link_rows"])
    (adir / "e123.md").write_text("\n".join(report(res)) + "\n", encoding="utf-8", newline="\n")
    if a.tex:
        tex(res, items_csv, links, docs, Path(resolve(a.tex)))
    print("\n".join(report(res)))


def seed_one(d1: Path, d0: Path, links: list[ek.Link]) -> dict[str, Any]:
    """Plan amendment v3: H2a on damage seed 1 per judge (exact McNemar, Holm across seed-1 judges); overlap with seed
    0; pooled over unique links (a link dropped by both seeds has one, identical, reply and counts once)."""
    if not d1.is_dir():
        return {}
    out: dict[str, Any] = {"models": {}}
    link_rows: list[dict[str, Any]] = []
    for mdir in sorted(p for p in d1.iterdir() if (p / "status-damaged.json").exists()):
        def load(d: Path, ctx: str, name: str = mdir.name) -> dict[str, dict[str, Any]]:
            f = d / name / f"{ctx}.json"
            return {r["item_id"]: r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]} if f.exists() else {}
        own = {i: bool(r["right"]) for i, r in load(d0, "both-texts").items() if r["role"] == "fault"}
        s0 = {i: bool(r["right"]) for i, r in load(d0, "status-damaged").items() if r["role"] == "fault" and r["dropped"]}
        r1 = load(d1, "status-damaged")
        s1 = {i: bool(r["right"]) for i, r in r1.items() if r["role"] == "fault" and r["dropped"]}
        if not s0 or not own:
            continue
        model = json.loads((mdir / "status-damaged.json").read_text(encoding="utf-8"))["model"]
        same_reply = sum(load(d0, "status-damaged")[i]["reply"] == r1[i]["reply"] for i in s0.keys() & s1.keys())
        m = {"seed1": paired(own, s1), "seed0": paired(own, s0),
             "shared": len(s0.keys() & s1.keys()), "shared_same_reply": same_reply,
             "only0": len(s0.keys() - s1.keys()), "only1": len(s1.keys() - s0.keys())}
        union = sorted(s0.keys() | s1.keys())
        dd = []
        for i in union:
            w = s1[i] if i in s1 else s0[i]  # shared links: identical reply under both seeds
            dd.append(float(own[i]) - float(w))
            link_rows.append({"model": model, "item_id": i, "seeds": "+".join(k for k, g in (("0", s0), ("1", s1)) if i in g),
                              "own": int(own[i]), "with_record": int(w)})
        rng = np.random.default_rng(0)
        bs = [float(np.mean(rng.choice(dd, len(dd)))) for _ in range(2000)]
        pos, neg = sum(x > 0 for x in dd), sum(x < 0 for x in dd)
        m["pooled"] = {"links": len(dd), "mean": round(float(np.mean(dd)), 4),
                       "ci95": [round(float(np.percentile(bs, q)), 4) for q in (2.5, 97.5)],
                       "lost": pos, "gained": neg, "sign_p": round(ek.mcnemar(pos, neg), 6)}
        out["models"][model] = m
    out["holm_seed1"] = holm({k: v["seed1"]["p"] for k, v in out["models"].items()})
    out["link_rows"] = link_rows
    return out


def report(res: dict[str, Any]) -> list[str]:
    def f(c: dict[str, Any]) -> str:
        return f"{c['k']}/{c['n']}"
    lines = ["# E1-E3 results (generated by analyse_final_e123.py)", "",
             "## Per context: fault right-reason catch | validity FA on controls, date controls, decoys | any-finding FA on decoys", ""]
    for model, m in res["models"].items():
        lines += [f"### {model}", "", "| Context | Catch | Ctrl FA | Date FA | Decoy FA | Decoy any | Invalid |", "|---|---|---|---|---|---|---|"]
        for ctx in ek.CONTEXTS:
            if ctx in m["contexts"]:
                c = m["contexts"][ctx]
                lines.append(f"| {ctx} | {f(c['fault_right'])} | {f(c['control_validity'])} | {f(c['date_validity'])} | "
                             f"{f(c['decoy_validity'])} | {f(c['decoy_any'])} | {c['invalid']} |")
        h1 = m["H1"]
        lines += ["", f"H1 (both texts): fault catch − matched decoy FA = {h1['disc_mean']:+.3f}, 95% CI {h1['ci95']}; "
                  f"by title: {h1['by_title']}", ""]
        if "H2a" not in m:
            lines += ["(partial run: gap contexts not yet run)", ""]
            continue
        lines += [
                  "Dropped-link faults (catch, bare passes): " + "; ".join(
                      f"{ctx} {f(c)} (bare {m['bare_pass'][ctx]})" for ctx, c in m["dropped_catch"].items()),
                  f"H2a both-texts → status-damaged: {m['H2a']}"]
        for arm, v in m["H2b"].items():
            lines.append(f"H2b status-damaged → {arm}: {v}")
        lines.append("")
    lines += [f"Holm H2a: {res['holm_H2a']}", f"Holm H2b: {res['holm_H2b']}", "", f"Decoy balance: {res['decoy_balance']}"]
    if res["seed1"].get("models"):
        lines += ["", "## Damage seed 1 (plan amendment v3)", ""]
        for model, m in res["seed1"]["models"].items():
            lines.append(f"{model}: seed0 {m['seed0']} | seed1 {m['seed1']} | shared {m['shared']} (same reply "
                         f"{m['shared_same_reply']}), only0 {m['only0']}, only1 {m['only1']} | pooled {m['pooled']}")
        lines.append(f"Holm seed 1: {res['seed1']['holm_seed1']}")
    return lines


MODELS = {"gemma-4-26b-a4b-it": ("Gemma", "Gemma 4 26B"), "kbench-gpt-5-5": ("GPT", "GPT-5.5"),
          "kbench-gemini-3-1-pro": ("Gemini", "Gemini 3.1 Pro"), "kbench-claude-opus-4-5": ("Opus", "Claude Opus 4.5")}
CTX = {"both-texts": "Texts", "status": "Record", "status-damaged": "Damaged", "norecord-damaged": "Norecord",
       "lowauth-damaged": "Lowauth", "caveat-damaged": "Caveat", "conflict-damaged": "Conflict"}
PEND = r"\pend{}"


def tex(res: dict[str, Any], items_csv: list[dict[str, Any]], links: list[ek.Link], docs: dict[str, ek.Doc],
        t: Path) -> None:
    """\\E<Model><Key> macros (k/n, points, p) for paper_v5; a value not yet run prints \\pend."""
    t.mkdir(parents=True, exist_ok=True)
    mods = res["models"]
    L = ["% Generated by 30_code/scripts/analyse_final_e123.py --tex; do not edit by hand.",
         f"\\newcommand{{\\EComplete}}{{{int(all(m in mods and len(mods[m]['contexts']) >= 6 for m in MODELS))}}}",
         f"\\newcommand{{\\ENLinks}}{{{len(links)}}}"]
    def mac(name: str, val: Any) -> None:
        L.append(f"\\newcommand{{\\{name}}}{{{val}}}")
    def f(c: dict[str, Any] | None) -> str:
        return f"{c['k']}/{c['n']}" if c else PEND
    def pts(x: float) -> str:
        return f"{100 * x:+.0f}".replace("-", "$-$")
    def pv(p: float | None) -> str:
        return PEND if p is None else ("<.001" if p < 0.001 else f"{p:.3f}".lstrip("0"))
    b = res["decoy_balance"]
    mac("EBalArea", b["same_area"])
    for k in ("title_ratio", "old_year", "new_year", "gap_years", "old_words", "new_words"):
        st = "".join(w.capitalize() for w in k.split("_"))
        mac(f"EBal{st}SMD", f"{b[k]['smd']:.2f}".replace("-", "$-$"))
    for m, (st, _) in MODELS.items():
        mm = mods.get(m, {})
        for ctx, cs in CTX.items():
            c = mm.get("contexts", {}).get(ctx)
            for key, name in (("fault_right", "Catch"), ("fault_any", "CatchAny"), ("control_validity", "CtrlFA"),
                              ("control_any", "CtrlAny"), ("date_validity", "DateFA"), ("decoy_validity", "DecoyFA"),
                              ("decoy_any", "DecoyAny")):
                mac(f"E{st}{name}{cs}", f(c[key]) if c else PEND)
            mac(f"E{st}Gap{cs}", f(mm.get("dropped_catch", {}).get(ctx)) if ctx != "status" else "--")
            mac(f"E{st}Bare{cs}", mm.get("bare_pass", {}).get(ctx, PEND) if ctx != "status" else "--")
        h1 = mm.get("H1")
        mac(f"E{st}HOne", pts(h1["disc_mean"]) if h1 else PEND)
        mac(f"E{st}HOneCI", f"[{pts(h1['ci95'][0])}, {pts(h1['ci95'][1])}]" if h1 else PEND)
        for kind in ("same", "different"):
            bt = h1["by_title"][kind] if h1 else None
            mac(f"E{st}{kind.capitalize()}Catch", f"{bt['fault_right']}/{bt['n']}" if bt else PEND)
            mac(f"E{st}{kind.capitalize()}Decoy", f"{bt['decoy_validity']}/{bt['n']}" if bt else PEND)
        h2a = mm.get("H2a")
        mac(f"E{st}HTwoaLost", h2a["lost"] if h2a else PEND)
        mac(f"E{st}HTwoaGained", h2a["gained"] if h2a else PEND)
        mac(f"E{st}HTwoaP", pv(h2a["p"]) if h2a else PEND)
        mac(f"E{st}HTwoaHolm", pv(res["holm_H2a"].get(m)))
        ra = res.get("reask", {}).get(m)
        mac(f"E{st}ReaskChanged", ra["changed"] if ra else PEND)
        mac(f"E{st}ReaskItems", f"{ra['items']:,}" if ra else PEND)
        cc = mm.get("conflict_code")
        for key, name in (("gap", "Gap"), ("decoy", "Decoy"), ("control", "Ctrl"), ("date-control", "Date")):
            mac(f"E{st}ConflictCode{name}", cc[key] if cc else PEND)
        for arm, cs in (("norecord-damaged", "Norecord"), ("lowauth-damaged", "Lowauth"), ("caveat-damaged", "Caveat")):
            v = mm.get("H2b", {}).get(arm)
            mac(f"E{st}Arm{cs}Gained", v["gained"] if v else PEND)
            mac(f"E{st}Arm{cs}Lost", v["lost"] if v else PEND)
            mac(f"E{st}Arm{cs}P", pv(v["p"]) if v else PEND)
            mac(f"E{st}Arm{cs}Holm", pv(res["holm_H2b"].get(f"{m}|{arm}")))
    for k, v in res["abstract_overlap_median"].items():
        mac("EAbsSim" + "".join(w.capitalize() for w in k.split("_")), f"{v:.2f}")
    for m, (st, _) in MODELS.items():
        mm = mods.get(m, {})
        ao = mm.get("abstract_overlap")
        for grp, name in (("same_title_decoy_fa", "DecoyFASim"), ("diff_title_fault_catch", "DiffCatchSim")):
            for lvl in ("high", "low"):
                mac(f"E{st}{name}{lvl.capitalize()}", ao[grp][lvl] if ao else PEND)
        po = mm.get("pilot_overlap")
        for k in ("pilot_items", "shared", "shared_same_reply", "shared_caught", "pilot_only", "pilot_only_caught"):
            mac(f"E{st}Pilot" + "".join(w.capitalize() for w in k.split("_")), po[k] if po else PEND)
        fg = mm.get("fresh_gap")
        for k in ("n", "own", "with_record"):
            mac(f"E{st}Fresh" + "".join(w.capitalize() for w in k.split("_")), fg[k] if fg else PEND)
        dc = mm.get("dropped_catch", {}).get("status-damaged")
        mac(f"E{st}MissDamaged", dc["n"] - dc["k"] if dc else PEND)
        for arm, cs in (("lowauth-damaged", "Lowauth"), ("caveat-damaged", "Caveat"), ("norecord-damaged", "Norecord")):
            v = mm.get("H2b", {}).get(arm)
            mac(f"E{st}Arm{cs}Raw", pv(v["p"]) if v else PEND)
    mac("EHTwobTests", len(res["holm_H2b"]))
    so = res.get("seed1", {}).get("models", {})
    for m, (st, _) in MODELS.items():
        v = so.get(m)
        mac(f"E{st}SOneOwn", f"{v['seed1']['first']}/{v['seed1']['items']}" if v else PEND)
        mac(f"E{st}SOneWith", f"{v['seed1']['second']}/{v['seed1']['items']}" if v else PEND)
        mac(f"E{st}SOneLost", v["seed1"]["lost"] if v else PEND)
        mac(f"E{st}SOneGained", v["seed1"]["gained"] if v else PEND)
        mac(f"E{st}SOneHolm", pv(res["seed1"]["holm_seed1"].get(m)) if v else PEND)
        mac(f"E{st}SOneShared", v["shared"] if v else PEND)
        mac(f"E{st}PoolLinks", v["pooled"]["links"] if v else PEND)
        mac(f"E{st}PoolMean", pts(v["pooled"]["mean"]) if v else PEND)
        mac(f"E{st}PoolCI", f"[{pts(v['pooled']['ci95'][0])}, {pts(v['pooled']['ci95'][1])}]" if v else PEND)
        mac(f"E{st}PoolLost", v["pooled"]["lost"] if v else PEND)
        mac(f"E{st}PoolGained", v["pooled"]["gained"] if v else PEND)
        mac(f"E{st}PoolP", pv(v["pooled"]["sign_p"]) if v else PEND)
    (t / "numbers_e123.tex").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")

    def wrap(cap: str, lab: str, spec: str, head: list[str], rows: list[str]) -> str:
        return "\n".join([r"\begin{table*}[t]\centering\footnotesize", f"\\caption{{{cap}}}", f"\\label{{{lab}}}",
                          r"\resizebox{\textwidth}{!}{%", f"\\begin{{tabular}}{{{spec}}}", r"\toprule", *head,
                          r"\midrule", *rows, r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]) + "\n"
    rows = []
    for st, name in MODELS.values():
        for i, (ctx, cs) in enumerate(CTX.items()):
            rows.append(f"{name if i == 0 else ''} & \\texttt{{{ctx}}} & \\E{st}Catch{cs} & \\E{st}CatchAny{cs} & "
                        f"\\E{st}CtrlFA{cs} & \\E{st}CtrlAny{cs} & \\E{st}DateFA{cs} & \\E{st}DecoyFA{cs} & \\E{st}DecoyAny{cs} \\\\")
        rows.append(r"\addlinespace")
    (t / "tab_e123_main.tex").write_text(wrap(
        "All 48 links, per judge and context. Catch: right-reason catches of faults (any: any finding on the fault). "
        "False alarms (FA) count validity findings (replaced or not yet published) unless marked any. Controls cite the "
        "replacing RFC; date controls cite the replaced RFC as of a date before its replacement; decoys cite an RFC that a "
        "newer one updates but does not replace. \\texttt{conflict-damaged} is exploratory: a \\texttt{record\\_conflict} finding "
        "counts under any, not as a catch or a validity false alarm. All counts are of 48.", "tab:e123-main", "llccccccc",
        [r" & & \multicolumn{2}{c}{Faults} & \multicolumn{2}{c}{Controls} & Date controls & \multicolumn{2}{c}{Decoys} \\",
         r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-7}\cmidrule(lr){8-9}",
         r"Judge & Context & Catch & any & FA & any & FA & FA & any \\"], rows[:-1]), encoding="utf-8", newline="\n")
    rows = [f"{name} & \\E{st}GapTexts & \\E{st}GapDamaged & \\E{st}BareDamaged & \\E{st}GapNorecord & \\E{st}GapLowauth & "
            f"\\E{st}GapCaveat & \\E{st}HTwoaHolm & \\E{st}ArmNorecordHolm & \\E{st}ArmLowauthHolm & \\E{st}ArmCaveatHolm \\\\"
            for st, name in MODELS.values()]
    (t / "tab_e123_gap.tex").write_text(wrap(
        "The 24 gap faults per judge: faults whose link the damaged record dropped (half the 48 links, seed 0). Same items "
        "in every column. The four damaged-record presentations use the same damaged record. Bare: passes with no finding "
        "under the authoritative ``in force'' line. $p$: exact McNemar, Holm-adjusted; H2a compares the authoritative "
        "line with no record, H2b each other presentation with the authoritative line.", "tab:e123-gap",
        "lcccccc cccc",
        [r" & No record & \multicolumn{5}{c}{Damaged record, presented as} & \multicolumn{4}{c}{Holm $p$} \\",
         r"\cmidrule(lr){3-7}\cmidrule(lr){8-11}",
         r"Judge & (texts) & record, ``in force'' & (bare) & ``no replacement recorded'' & unverified note & record + warning & H2a & "
         r"wording & authority & warning \\"], rows), encoding="utf-8", newline="\n")
    rows = [f"{name} & \\E{st}SameCatch & \\E{st}SameDecoy & \\E{st}DifferentCatch & \\E{st}DifferentDecoy & "
            f"\\E{st}HOne{{}} \\E{st}HOneCI \\\\" for st, name in MODELS.values()]
    (t / "tab_e123_decoy.tex").write_text(wrap(
        "Shortcut test with both texts and no record. Faults and their matched decoys, split by whether the two RFCs of "
        "the pair share a (near-)identical title. Discrimination: catch minus decoy false alarm, paired by link, in "
        "points with a 95\\% bootstrap interval over the 48 pairs.", "tab:e123-decoy", "lccccc",
        [r" & \multicolumn{2}{c}{Same title} & \multicolumn{2}{c}{Different title} & \\",
         r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
         r"Judge & Fault catch & Decoy FA & Fault catch & Decoy FA & Discrimination \\"], rows), encoding="utf-8",
        newline="\n")
    rows = [f"{name} & \\E{st}GapTexts{{}} $\\to$ \\E{st}GapDamaged & \\E{st}HTwoaLost/\\E{st}HTwoaGained & \\E{st}HTwoaHolm & "
            f"\\E{st}SOneOwn{{}} $\\to$ \\E{st}SOneWith & \\E{st}SOneLost/\\E{st}SOneGained & \\E{st}SOneHolm & \\E{st}SOneShared & "
            f"\\E{st}PoolLinks & \\E{st}PoolMean{{}} {{\\scriptsize \\E{st}PoolCI}} & \\E{st}PoolLost/\\E{st}PoolGained & \\E{st}PoolP \\\\"
            for st, name in MODELS.values()]
    (t / "tab_e123_seeds.tex").write_text(wrap(
        "H2a on two random draws of dropped links. Each seed drops 24 of the 48 links; the two draws share some links "
        "(Shared). Per seed: gap faults caught with no record $\\to$ with the damaged record (authoritative form), "
        "lost/gained, Holm-adjusted exact McNemar $p$ (across judges, within seed). Pooled: unique links in either gap "
        "set, a shared link counted once (its reply is the same under both seeds); mean drop in points with a 95\\% "
        "bootstrap interval over links, lost/gained, exact sign test. Seed 0 is the planned test; seed 1 and the pooled "
        "estimate were added before any seed-1 run, when seed-0 results existed for three judges.", "tab:e123-seeds", "l ccc cccc cccc",
        [r" & \multicolumn{3}{c}{Seed 0} & \multicolumn{4}{c}{Seed 1} & \multicolumn{4}{c}{Pooled over unique links} \\",
         r"\cmidrule(lr){2-4}\cmidrule(lr){5-8}\cmidrule(lr){9-12}",
         r"Judge & Caught & Lost/gained & $p$ & Caught & Lost/gained & $p$ & Shared & Links & Drop & Lost/gained & $p$ \\"],
        rows), encoding="utf-8", newline="\n")
    # one rendered prompt (a gap fault under the authoritative line) and the header of each presentation
    rec = ek.damaged({(lk.old, lk.new) for lk in links}, 0.5, 0)
    it = next(x for x in ek.items(links, docs) if x.role == "fault" and tuple(x.link.split(">")) not in rec)
    heads = [next(ln for ln in ek.render(it, c, docs, rec).splitlines() if ln.startswith("[") and ("RECORD" in ln or "NOTE" in ln))
             + "\n" + next(ln for ln in ek.render(it, c, docs, rec).splitlines() if ln.startswith("- "))
             for c in ("status-damaged", "norecord-damaged", "lowauth-damaged", "caveat-damaged")]
    def wr(x: str) -> str:
        import textwrap
        return "\n".join(w for ln in x.splitlines() for w in (textwrap.wrap(ln, 70, subsequent_indent="  ") or [""]))
    (t / "prompt_example.tex").write_text("\\begin{figure}[p]\n{\\fontsize{6.5}{7.3}\\selectfont\\begin{verbatim}\n" + wr(ek.SYSTEM + "\n\n" + ek.render(
        it, "status-damaged", docs, rec)) + "\n\\end{verbatim}}\n{\\fontsize{6.5}{7.3}\\selectfont\\begin{verbatim}\n" + wr("\n\n".join(heads))
        + "\n\\end{verbatim}}\n\\caption{Top: system text and prompt for one gap fault under the authoritative line. Bottom: the "
        "record block of each damaged context, in table order.}\n\\label{fig:prompt}\n\\end{figure}\n", encoding="utf-8",
        newline="\n")
    # per-item outcomes on the gap faults: one column per judge x presentation
    gap = sorted({r["item_id"] for r in items_csv if r["dropped"] and r["role"] == "fault"},
                 key=lambda i: [f"{lk.old}>{lk.new}#fault" for lk in links].index(i))
    cell = {(r["model"], r["context"], r["item_id"]): r["right"] for r in items_csv}
    order = [c for c in CTX if c != "status"]
    rows = []
    for i in gap:
        old, new = i.split("#")[0].split(">")
        marks = []
        for m in MODELS:
            marks.append(" ".join("--" if (m, c, i) not in cell else ("\\ding{51}" if cell[(m, c, i)] else "$\\cdot$")
                                  for c in order))
        rows.append(f"{old.replace('RFC', '')}$\\to${new.replace('RFC', '')} & "
                    + " & ".join(marks) + " \\\\")
    (t / "tab_e123_items.tex").write_text(wrap(
        "Per-item outcomes on the gap faults (\\ding{51} caught for the right reason, $\\cdot$ missed, -- not run). Within "
        "each judge, the six marks are, in order T F N U W C: texts only (no record), ``in force'', ``no replacement "
        "recorded'', unverified note, record with warning, record with the conflict code (a conflict finding is not a "
        "catch).", "tab:e123-items", "l" + "c" * len(MODELS),
        ["Link (RFC) & " + " & ".join(n for _, n in MODELS.values()) + r" \\",
         " & " + " & ".join(["{\\scriptsize T F N U W C}"] * len(MODELS)) + r" \\"], rows), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
