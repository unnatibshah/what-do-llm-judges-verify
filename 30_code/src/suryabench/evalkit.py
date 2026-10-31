"""Evaluate an LLM reviewer on documents that replace each other (D51): a corpus-agnostic harness.

Input: a link table (old document -> the document that replaced it, with dates) and short texts for each document.
Output: matched items, a menu of contexts, damaged records, reason-coded scores and an evaluator report card.

Per link it builds three items that share one question ("as of D, which document specifies T?"):
- ``fault``: the answer cites the old document, as of a date after it was replaced;
- ``control``: the answer cites the replacing document, same date;
- ``date-control``: the answer cites the old document, as of a date before the replacement existed (correct).
A reviewer that flags citations of old documents without reading dates fails the date control; one that never
flags fails the fault. Optional ``decoy`` items (``rfc_decoys``) cite an older document that a newer one only updates,
not replaces: a reviewer that flags any older document beside a newer one on the same topic fails them. The contexts (``CONTEXTS``) vary what the reviewer is given; the record can be damaged.

Scoring (reason-coded, as in the solar study): a fault is caught when a finding names the cited document with the
reason ``superseded``; a control is a false alarm under ``any`` finding, and a validity false alarm when a finding
gives ``superseded`` or ``not_yet_published``. The unit is the link (pair).

The first corpus adapter is the IETF RFC index (``rfc_links``): publisher-curated "Obsoletes"/"Obsoleted-by" links,
publication dates and abstracts. Run: ``30_code/scripts/run_evalkit.py``; analysis: ``python -m suryabench.evalkit``.
"""

import argparse
import hashlib
import inspect
import json
import random
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from suryabench.paths import RESULTS_DIR, ROOT, resolve

AS_OF = "2026-10-01"
REASONS = {"superseded": "the cited document had been replaced or obsoleted by a later one on the date asked about",
           "not_yet_published": "the cited document did not yet exist on the date asked about",
           "not_applicable": "the cited document does not address the question",
           "content_error": "the answer misstates what the document says",
           "unsupported": "the evidence does not support the answer",
           "other": "any other problem"}
VALIDITY = {"superseded", "not_yet_published"}
SYSTEM = "You review answers that cite documents. Be precise and brief. Respond in strict JSON."
CURRENCY_STEP = ("Before judging anything else, check each cited document against the evidence and any record: has a "
                 "later document replaced it on or before the date asked about? Compare the dates.")
CONTEXTS = {  # name -> what the reviewer sees (the practitioner's menu)
    "cite-only": "the question and answer, no evidence (what the model already knows)",
    "cited-text": "the cited document's text only",
    "both-texts": "both documents' texts, with any statement of replacement removed",
    "both-masked": "both texts with document numbers masked (no memory of the identifiers)",
    "both-explicit": "both texts, the newer one keeping its own 'Obsoletes:' notice",
    "status": "both texts and a record line giving each cited document's status on the date",
    "status-damaged": "as status, but the record has lost half its links (a dropped link reads 'in force')",
    "norecord-damaged": "as status-damaged, but a document with no recorded replacement reads 'no replacement recorded'",
    "caveat-damaged": "as status-damaged, but the record is labelled incomplete (it may omit replacements)",
    "lowauth-damaged": "as status-damaged, but the line is presented as an unverified automated note, not a record",
    "check-first": "both texts and an instruction to check replacement and dates before anything else",
    "few-shot": "both texts and two worked examples (one caught fault, one passed correct answer)",
}


@dataclass(frozen=True)
class Doc:
    doc_id: str
    title: str
    date: str  # YYYY-MM
    text: str


@dataclass(frozen=True, order=True)
class Link:
    old: str
    new: str


@dataclass(frozen=True)
class Item:
    item_id: str
    link: str  # "old>new"
    role: str  # fault | control | date-control
    cited: str
    as_of: str
    topic: str


def code_hash() -> str:
    return hashlib.sha256(inspect.getsource(inspect.getmodule(code_hash)).encode()).hexdigest()[:12]  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------------- RFC adapter
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}
RFC_INDEX = ROOT / "40_data" / "corpus_staging" / "rfc" / "rfc-index.xml"
SAMPLE = 48


def rfc_links(index: Path = RFC_INDEX, n: int = 48, seed: int = 0, min_year: int = 2005
              ) -> tuple[dict[str, Doc], list[Link], list[Link]]:
    """Docs, ``n`` test links and 2 few-shot links (disjoint), sampled with ``seed`` from one-to-one replacements: the
    old RFC is obsoleted by exactly one RFC, which is itself current, published from ``min_year``, replacing at most
    two RFCs, and both have abstracts."""
    ns = {"r": "https://www.rfc-editor.org/rfc-index"}
    docs: dict[str, Doc] = {}
    meta: dict[str, dict[str, Any]] = {}
    for e in ET.parse(index).getroot().findall("r:rfc-entry", ns):
        d = e.findtext("r:doc-id", namespaces=ns) or ""
        ab = e.find("r:abstract", ns)
        text = " ".join(" ".join("".join(p.itertext()).split()) for p in ab.findall("r:p", ns)) if ab is not None else ""
        month = MONTHS.get(e.findtext("r:date/r:month", namespaces=ns) or "", 1)
        docs[d] = Doc(d, e.findtext("r:title", namespaces=ns) or "", f"{e.findtext('r:date/r:year', namespaces=ns)}-{month:02d}", text)
        meta[d] = {"by": [x.text for x in e.findall("r:obsoleted-by/r:doc-id", ns)],
                   "obsoletes": [x.text for x in e.findall("r:obsoletes/r:doc-id", ns)]}
    pool = sorted(Link(o, m["by"][0]) for o, m in meta.items()
                  if len(m["by"]) == 1 and m["by"][0] in docs and not meta[m["by"][0]]["by"]
                  and int(docs[m["by"][0]].date[:4]) >= min_year and len(meta[m["by"][0]]["obsoletes"]) <= 2
                  and docs[o].text and docs[m["by"][0]].text and docs[o].date < docs[m["by"][0]].date)
    picked = random.Random(seed).sample(pool, SAMPLE + 2)  # one fixed sample: a smaller n is its prefix
    return docs, picked[:min(n, SAMPLE)], picked[SAMPLE:]


def title_ratio(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    x, y = (re.sub(r"[^a-z0-9 ]", "", t.lower()).strip() for t in (a, b))
    return SequenceMatcher(None, x, y).ratio()


def pair_features(lk: Link, docs: dict[str, Doc], area: dict[str, str]) -> dict[str, Any]:
    """What a decoy is matched on: IETF area (topic), title similarity, both dates, the gap and both abstract lengths."""
    o, n = docs[lk.old], docs[lk.new]
    def year(d: Doc) -> float:
        return int(d.date[:4]) + (int(d.date[5:]) - 1) / 12
    return {"area": area.get(lk.old, ""), "title_ratio": title_ratio(o.title, n.title), "old_year": year(o),
            "new_year": year(n), "gap_years": year(n) - year(o), "old_words": len(o.text.split()),
            "new_words": len(n.text.split())}


def decoy_cost(f: dict[str, Any], g: dict[str, Any]) -> float:
    from math import log
    return float(2.0 * (f["area"] != g["area"]) + 4.0 * abs(f["title_ratio"] - g["title_ratio"])
            + abs(f["old_year"] - g["old_year"]) / 5 + abs(f["new_year"] - g["new_year"]) / 5
            + abs(log(f["old_words"] / g["old_words"])) + abs(log(f["new_words"] / g["new_words"])))


def rfc_area(index: Path = RFC_INDEX) -> dict[str, str]:
    ns = {"r": "https://www.rfc-editor.org/rfc-index"}
    return {e.findtext("r:doc-id", namespaces=ns) or "": e.findtext("r:area", namespaces=ns) or "none"
            for e in ET.parse(index).getroot().findall("r:rfc-entry", ns)}


def rfc_decoys(links: list[Link], docs: dict[str, Doc], index: Path = RFC_INDEX) -> list[Link]:
    """One decoy per test link: an RFC pair where the newer one *updates* the older one, which stays in force (never
    obsoleted), under the same filters as ``rfc_links`` and disjoint from its documents. Nearest neighbour (``decoy_cost``)
    within the link's ``same_title`` stratum, greedy in link order without reuse of a document, so the decoys of a
    prefix of the links are the prefix of the decoys. Deterministic; balance: ``decoy_balance``."""
    ns = {"r": "https://www.rfc-editor.org/rfc-index"}
    meta = {e.findtext("r:doc-id", namespaces=ns) or "": {k: [x.text or "" for x in e.findall(f"r:{k}/r:doc-id", ns)]
                                                           for k in ("obsoleted-by", "updated-by")}
            for e in ET.parse(index).getroot().findall("r:rfc-entry", ns)}
    _, test, shots = rfc_links(index)
    used = {d for lk in test + shots for d in (lk.old, lk.new)}
    area = rfc_area(index)
    pool = sorted(Link(o, n) for o, m in meta.items() for n in m["updated-by"]
                  if not m["obsoleted-by"] and n in docs and not meta[n]["obsoleted-by"] and docs[o].text
                  and docs[n].text and int(docs[n].date[:4]) >= 2005 and docs[o].date < docs[n].date
                  and o not in used and n not in used)
    feats = {lk: pair_features(lk, docs, area) for lk in pool}
    out: list[Link] = []
    seen: set[str] = set()
    for lk in links:
        f = pair_features(lk, docs, area)
        stratum = same_title(docs[lk.old].title, docs[lk.new].title)
        cands = [d for d in pool if same_title(docs[d.old].title, docs[d.new].title) == stratum
                 and d.old not in seen and d.new not in seen]
        pick = min(cands, key=lambda d: (decoy_cost(f, feats[d]), d))
        seen |= {pick.old, pick.new}
        out.append(pick)
    return out


def decoy_balance(links: list[Link], decoys: list[Link], docs: dict[str, Doc]) -> dict[str, Any]:
    """Means of each matching feature for links and decoys, the standardised mean difference, and area agreement."""
    area = rfc_area()
    fl = [pair_features(lk, docs, area) for lk in links]
    fd = [pair_features(lk, docs, area) for lk in decoys]
    out: dict[str, Any] = {"same_area": f"{sum(a['area'] == b['area'] for a, b in zip(fl, fd, strict=True))}/{len(fl)}"}
    for k in ("title_ratio", "old_year", "new_year", "gap_years", "old_words", "new_words"):
        x, y = np.array([f[k] for f in fl], float), np.array([f[k] for f in fd], float)
        sd = float(np.sqrt((x.var(ddof=1) + y.var(ddof=1)) / 2)) or 1.0
        out[k] = {"links": round(float(x.mean()), 2), "decoys": round(float(y.mean()), 2),
                  "smd": round(float((y.mean() - x.mean()) / sd), 2)}
    return out


def decoy_items(decoys: list[Link], docs: dict[str, Doc]) -> list[Item]:
    """A correct answer citing the older document of an update pair, as of ``AS_OF`` (it is still in force)."""
    return [Item(f"{lk.old}>{lk.new}#decoy", f"{lk.old}>{lk.new}", "decoy", lk.old, AS_OF, docs[lk.old].title)
            for lk in decoys]


# --------------------------------------------------------------------------------------------- items and prompts
def items(links: list[Link], docs: dict[str, Doc]) -> list[Item]:
    out = []
    for lk in links:
        old, new = docs[lk.old], docs[lk.new]
        y, m = int(new.date[:4]), int(new.date[5:])
        before = f"{y - 1}-{m:02d}-15" if f"{y - 1}-{m:02d}" > old.date else f"{old.date}-28"
        key = f"{lk.old}>{lk.new}"
        out += [Item(f"{key}#fault", key, "fault", lk.old, AS_OF, old.title),
                Item(f"{key}#control", key, "control", lk.new, AS_OF, old.title),
                Item(f"{key}#date-control", key, "date-control", lk.old, before, old.title)]
    return out


REPLACEMENT_WORDS = re.compile(r"obsolet|supersed|replac|updat", re.I)


def scrub(text: str, other: str) -> str:
    """The text without sentences that state a replacement or name the other document of the pair."""
    num = re.sub(r"\D", "", other)
    keep = [s for s in re.split(r"(?<=[.!?])\s+", text)
            if not REPLACEMENT_WORDS.search(s) and not re.search(rf"RFC\s*{num}\b", s)]
    return " ".join(keep)


def mask(text: str, ids: dict[str, str]) -> str:
    """Document numbers replaced by stable opaque labels; numbers outside the pair become 'DOC-other'."""
    def sub(m: re.Match[str]) -> str:
        return ids.get(f"RFC{m.group(1)}", "DOC-other")
    return re.sub(r"RFC\s*(\d+)", sub, text)


def status_line(doc: str, as_of: str, record: set[tuple[str, str]], docs: dict[str, Doc], no_record: bool) -> str:
    repl = [n for o, n in record if o == doc and docs[n].date <= as_of[:7]]
    if repl:
        return f"- {doc}: status on {as_of}: superseded (by {repl[0]}, from {docs[repl[0]].date})"
    return f"- {doc}: status on {as_of}: {'no_replacement_recorded' if no_record else 'in_force'}"


def render(item: Item, context: str, docs: dict[str, Doc], record: set[tuple[str, str]],
           examples: list[tuple[str, str]] | None = None) -> str:
    old_id, new_id = item.link.split(">")
    old, new = docs[old_id], docs[new_id]
    cited = docs[item.cited]
    answer = f'The document that specifies this is {cited.doc_id}, "{cited.title}" ({cited.date}).'
    question = f'As of {item.as_of}, which document specifies "{item.topic}"?'

    def show(d: Doc, keep_notice: bool) -> str:
        other = new_id if d.doc_id == old_id else old_id
        body = d.text if keep_notice else scrub(d.text, other)
        verb = "Updates" if item.role == "decoy" else "Obsoletes"
        notice = f"{verb}: {old_id}\n" if keep_notice and d.doc_id == new_id else ""
        return f"[{d.doc_id}] {d.title} (published {d.date})\n{notice}{body}"
    evidence, record_block, extra = "", "", ""
    if context == "cited-text":
        evidence = show(cited, False)
    elif context != "cite-only":
        evidence = "\n\n".join(show(d, context == "both-explicit") for d in (old, new))
    if context in {"status", "status-damaged", "norecord-damaged", "caveat-damaged", "lowauth-damaged"}:
        caveat = (" (this record is incomplete: it omits some replacements, so a document it lists as in force may "
                  "have been replaced)") if context == "caveat-damaged" else ""
        header = ("UNVERIFIED NOTE FROM AN AUTOMATED TAGGER ABOUT THE CITED DOCUMENT" if context == "lowauth-damaged"
                  else f"AMENDMENT RECORD LOOKUP OF THE CITED DOCUMENT{caveat}")
        record_block = (f"\n[{header}]\n"
                        + status_line(item.cited, item.as_of, record, docs, context == "norecord-damaged"))
    if context == "check-first":
        extra = CURRENCY_STEP + "\n"
    if context == "few-shot" and examples:
        extra = "Worked examples:\n" + "\n\n".join(f"{p}\nCorrect reply: {r}" for p, r in examples) + "\n\n"
    reasons = "\n".join(f"- {k}: {v}" for k, v in REASONS.items())
    text = (f"{extra}[QUESTION]\n{question}\n[ANSWER UNDER REVIEW]\n{answer}\n[EVIDENCE]\n{evidence or '(none)'}"
            f"{record_block}\n[TASK]\nDecide whether the answer is valid as of the date in the question. For each "
            f"problem give a finding naming the cited document and one reason from:\n{reasons}\nReply as JSON: "
            '{"verdict": "PASS" or "FLAG", "findings": [{"doc_id": "...", "reason": "...", "rationale": "..."}]}')
    if context == "both-masked":
        text = mask(text, masked_ids(item))
    return text


def masked_ids(item: Item) -> dict[str, str]:
    """The opaque label each document of the item's link gets in the masked context."""
    return {d: "DOC-" + hashlib.sha256(d.encode()).hexdigest()[:4].upper() for d in item.link.split(">")}


def damaged(record: set[tuple[str, str]], fraction: float, seed: int) -> set[tuple[str, str]]:
    links = sorted(record)
    random.Random(seed).shuffle(links)
    return set(links[round(len(links) * fraction):])


# --------------------------------------------------------------------------------------------- scoring
def score(item: Item, reply: dict[str, Any] | None, masked_ids: dict[str, str] | None = None) -> dict[str, Any]:
    """right: a ``superseded`` finding on the cited document; any: any finding; validity: a validity-reason finding."""
    if reply is None:
        return {"invalid": True, "any": item.role != "fault", "right": False, "validity": item.role != "fault"}
    cited = (masked_ids or {}).get(item.cited, item.cited)
    findings = [f for f in reply.get("findings") or [] if isinstance(f, dict)]
    def norm(x: Any) -> str:
        return re.sub(r"[\s_-]", "", str(x)).upper()
    on_cited = [f for f in findings if norm(cited) in norm(f.get("doc_id", "")) or norm(f.get("doc_id", "")) in norm(cited)]
    flagged = str(reply.get("verdict", "")).upper() == "FLAG" or bool(findings)
    return {"invalid": False, "any": flagged,
            "right": any(str(f.get("reason", "")).strip() == "superseded" for f in on_cited),
            "validity": any(str(f.get("reason", "")).strip() in VALIDITY for f in findings),
            "reasons": sorted({str(f.get("reason", "")).strip() for f in findings})}


def summarise(rows: list[dict[str, Any]], boot: int = 2000, seed: int = 0) -> dict[str, Any]:
    """Per role: k/n; discrimination = catch (right) - false alarm, per link, mean and bootstrap over links."""
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_role[r["role"]].append(r)
    out: dict[str, Any] = {}
    for role, rs in by_role.items():
        out[role] = {k: {"k": sum(bool(r[k]) for r in rs), "n": len(rs)} for k in ("right", "any", "validity", "invalid")}
    per: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        per[r["link"]][r["role"]] = r
    for name, (ctrl, key) in {"disc_any": ("control", "any"), "disc_validity": ("control", "validity"),
                              "disc_date": ("date-control", "validity"), "disc_date_any": ("date-control", "any")}.items():
        d = [float(bool(v["fault"]["right"])) - float(bool(v[ctrl][key])) for v in per.values() if "fault" in v and ctrl in v]
        if not d:
            continue
        rng = np.random.default_rng(seed)
        bs = [float(np.mean(rng.choice(d, len(d)))) for _ in range(boot)]
        out[name] = {"mean": round(float(np.mean(d)), 4), "ci95": [round(float(np.percentile(bs, 2.5)), 4),
                                                                   round(float(np.percentile(bs, 97.5)), 4)], "links": len(d)}
    return out


def same_title(old: str, new: str) -> bool:
    """Replacement pairs whose titles are (near-)identical: recency alone then identifies the replacement."""
    from difflib import SequenceMatcher
    a, b = (re.sub(r"[^a-z0-9 ]", "", t.lower()).strip() for t in (old, new))
    return SequenceMatcher(None, a, b).ratio() >= 0.8


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p over b and c discordant pairs."""
    from math import comb
    n, k = b + c, min(b, c)
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


RECORD_WORDS = re.compile(r"record|status|lookup|in.force|registry", re.I)


def rationale_kind(reply: dict[str, Any] | None) -> str:
    """On a fault: what the reply leans on (post hoc coding, keyword-based)."""
    if not reply:
        return "invalid"
    findings = [f for f in reply.get("findings") or [] if isinstance(f, dict)]
    if not findings:
        return "pass, no finding"
    text = " ".join(str(f.get("rationale", "")) for f in findings)
    return "cites the record" if RECORD_WORDS.search(text) else "cites texts or dates"


def deference(blocks: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """On the faults whose link the damaged record dropped (so it reads 'in force' or 'no replacement recorded'), the
    reviewer's catch there against its own catch on the same items with no record (``both-texts``), per item."""
    base = {r["item_id"]: bool(r["right"]) for r in blocks.get("both-texts", []) if r["role"] == "fault"}
    out = {}
    for ctx in ("status-damaged", "norecord-damaged", "caveat-damaged", "lowauth-damaged"):
        pairs = [(base[r["item_id"]], bool(r["right"])) for r in blocks.get(ctx, [])
                 if r["role"] == "fault" and r.get("dropped") and r["item_id"] in base]
        if pairs:
            b = sum(a and not w for a, w in pairs)
            c = sum(w and not a for a, w in pairs)
            kinds: dict[str, int] = defaultdict(int)
            for r in blocks[ctx]:
                if r["role"] == "fault" and r.get("dropped") and r["item_id"] in base:
                    kinds[rationale_kind(r.get("reply"))] += 1
            out[ctx] = {"items": len(pairs), "own": sum(a for a, _ in pairs), "with_record": sum(w for _, w in pairs),
                        "mcnemar_p": round(mcnemar(b, c), 4), "kinds": dict(sorted(kinds.items()))}
    return out


def title_split(blocks: dict[str, list[dict[str, Any]]], docs: dict[str, Doc]) -> dict[str, Any]:
    """Right-reason catch on faults by context, for same-title and different-title links."""
    out: dict[str, Any] = {}
    for ctx, rows in blocks.items():
        for r in rows:
            if r["role"] != "fault":
                continue
            old, new = r["link"].split(">")
            key = "same" if same_title(docs[old].title, docs[new].title) else "different"
            cell = out.setdefault(ctx, {}).setdefault(key, {"k": 0, "n": 0})
            cell["k"] += bool(r["right"])
            cell["n"] += 1
    return out


def analyse(out_dir: Path) -> dict[str, Any]:
    res: dict[str, Any] = {}
    blocks: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for f in sorted(out_dir.glob("*/*.json")):
        b = json.loads(f.read_text(encoding="utf-8"))
        res.setdefault(b["model"], {})[b["context"]] = summarise(b["rows"])
        blocks.setdefault(b["model"], {})[b["context"]] = b["rows"]
    docs = rfc_links()[0]
    for m, bl in blocks.items():
        d = deference(bl)
        if d:
            res[m]["_deference"] = d
        res[m]["_title_split"] = title_split(bl, docs)
    (out_dir / "summary.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description="evalkit analysis: summary.json over saved blocks")
    ap.add_argument("--out", default=str(RESULTS_DIR / "evalkit_rfc"))
    ap.add_argument("--tex", help="folder for numbers_rfc.tex and tab_rfc_*.tex (paper)")
    a = ap.parse_args()
    res = analyse(Path(resolve(a.out)))
    if a.tex:
        t = Path(resolve(a.tex))
        t.mkdir(parents=True, exist_ok=True)
        (t / "tab_rfc_deference.tex").write_text("\n".join(deference_table(res)) + "\n", encoding="utf-8", newline="\n")
        (t / "numbers_rfc.tex").write_text("\n".join(macros(res)) + "\n", encoding="utf-8", newline="\n")
        for metric, cap, lab in (
                ("disc_date", "Currency discrimination by context (points): right-reason catch on faults minus validity "
                 "false alarms on date controls, which cite the same old document as of a date before it was replaced. "
                 "Mean over links.", "tab:rfc-date"),
                ("disc_validity", "Discrimination against current-document controls (points): right-reason catch minus "
                 "validity false alarms on answers citing the replacing document. Mean over links.", "tab:rfc-current"),
                ("disc_date_any", "As Table~\\ref{tab:rfc-date}, with any finding on a date control counted as a false "
                 "alarm.", "tab:rfc-date-any")):
            (t / f"tab_rfc_{metric}.tex").write_text("\n".join(table(res, metric, cap, lab)) + "\n", encoding="utf-8",
                                                     newline="\n")
    for m, ctx in res.items():
        for c, v in ctx.items():
            if c.startswith("_"):
                print(f"{m:28} deference {v}")
                continue
            print(f"{m:28} {c:18} catch {v['fault']['right']['k']}/{v['fault']['right']['n']}  "
                  f"disc_validity {v.get('disc_validity', {}).get('mean')}  disc_date {v.get('disc_date', {}).get('mean')}")



__all__ = ["CONTEXTS", "Doc", "Item", "Link", "asdict", "damaged", "decoy_items", "items", "render", "rfc_decoys",
           "rfc_links", "score", "summarise"]


# --------------------------------------------------------------------------------------------- paper outputs
SHORT = {"gemini-3.5-flash-lite": "Flash-Lite", "qwen2.5:7b": "Qwen 7B", "llama3.1:8b": "Llama 8B", "qwen2.5:14b": "Qwen 14B",
         "qwen2.5:32b": "Qwen 32B", "kbench-claude-opus-4-5": "Claude Opus 4.5", "kbench-gemini-3-pro": "Gemini 3 Pro",
         "kbench-deepseek-v3-2": "DeepSeek V3.2", "kbench-qwen3-235b": "Qwen3 235B", "gemma-4-26b-a4b-it": "Gemma 4 26B",
         "gemini-3-flash-preview": "Gemini 3 Flash", "kbench-gemini-pro": "Gemini Pro", "kbench-deepseek-v3": "DeepSeek V3",
         "kbench-claude-sonnet-4-5": "Claude Sonnet 4.5", "kbench-gpt-5-5": "GPT-5.5", "kbench-gemini-3-1-pro": "Gemini 3.1 Pro",
         "kbench-claude-opus-5-5": "Claude Opus 5.5", "kbench-gpt-oss-120b": "GPT-OSS 120B", "kbench-grok-4-6": "Grok 4.6",
         "kbench-claude-haiku-4-5": "Claude Haiku 4.5"}
ORDER = ["llama3.1:8b", "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b", "gemma-4-26b-a4b-it", "gemini-3.5-flash-lite",
         "kbench-claude-haiku-4-5", "kbench-gpt-oss-120b",
         "kbench-qwen3-235b", "kbench-deepseek-v3", "kbench-gemini-pro", "kbench-claude-sonnet-4-5",
         "kbench-grok-4-6", "kbench-gemini-3-1-pro", "kbench-gpt-5-5", "kbench-claude-opus-4-5", "kbench-claude-opus-5-5"]


REPORT_RULE = ("both-texts", "status-damaged")  # a reviewer is in the paper's tables if it ran the deference pair


def reported(res: dict[str, Any]) -> list[str]:
    """Models in the paper's tables, in display order: those that ran every context of ``REPORT_RULE``."""
    return [m for m in [m for m in ORDER if m in res] + sorted(m for m in res if m not in ORDER)
            if all(c in res[m] for c in REPORT_RULE)]


def table(res: dict[str, Any], metric: str, caption: str, label: str) -> list[str]:
    """Contexts x models, one metric (points, mean over links); a blank cell is a context not run for that model."""
    models = reported(res)
    rows = []
    for c in CONTEXTS:
        cells = []
        for m in models:
            v = res[m].get(c, {}).get(metric)
            cells.append("--" if not v else f"{100 * v['mean']:+.0f}".replace("-", "$-$"))
        rows.append(f"\\texttt{{{c}}} & " + " & ".join(cells) + " \\\\")
    return [r"\begin{table*}[t]\centering\scriptsize", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
            r"\setlength{\tabcolsep}{3pt}", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{l" + "r" * len(models) + "}",
            r"\toprule", "Context & " + " & ".join(SHORT.get(m, m) for m in models) + r" \\", r"\midrule", *rows,
            r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]


def deference_table(res: dict[str, Any]) -> list[str]:
    """Per model: right-reason catches on all faults with no record, a correct record and a damaged one; then, on the
    faults whose link the damaged record dropped, catches with no record, with the damaged record ('in force') and with
    'no replacement recorded' (same items), and the bare passes among the damaged-record replies there."""
    def catch(m: str, c: str) -> str:
        v = res[m].get(c, {}).get("fault", {}).get("right")
        return f"{v['k']}/{v['n']}" if v else "--"
    rows = []
    for m in reported(res):
        d = res[m].get("_deference", {})
        if not d:
            continue
        sd = d.get("status-damaged", next(iter(d.values())))
        n, own = sd["items"], sd["own"]
        cells = [f"{d[c]['with_record']}/{n}" if c in d else "--" for c in ("status-damaged", "norecord-damaged")]
        bare = sd["kinds"].get("pass, no finding", 0)
        rows.append(f"{SHORT.get(m, m)} & {catch(m, 'both-texts')} & {catch(m, 'status')} & {catch(m, 'status-damaged')} & "
                    f"{own}/{n} & {cells[0]} & {cells[1]} & {bare} \\\\")
    return [r"\begin{table*}[t]\centering\small",
            r"\caption{Where the record is silent. Left: right-reason catches on all faults with no record "
            r"(\texttt{both-texts}), a correct record line (\texttt{status}) and a record with half its links dropped "
            r"(\texttt{status-damaged}, seed 0); a lookup in the damaged record catches exactly half. Right: the faults "
            r"whose link was dropped, with no record, with the damaged record (the line reads ``in force''), and with the "
            r"line worded ``no replacement recorded''; same items in every column. Bare: damaged-record replies on these "
            r"faults that pass the answer with no finding. Qwen~32B ran 48 links, the others 24.}",
            r"\label{tab:rfc-deference}", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{l ccc cccc}", r"\toprule",
            r" & \multicolumn{3}{c}{All faults} & \multicolumn{4}{c}{Faults whose link was dropped} \\",
            r"\cmidrule(lr){2-4}\cmidrule(lr){5-8}",
            r"Reviewer & No record & Correct & Damaged & No record & ``In force'' & ``No replacement'' & Bare \\",
            r"\midrule", *rows, r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]


def stem(s: str) -> str:
    """A model or context name as letters only, for LaTeX macro names."""
    words = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven",
             "8": "Eight", "9": "Nine"}
    s = SHORT.get(s, s)
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", "".join(words.get(ch, ch) for ch in s)) if w)


def macros(res: dict[str, Any]) -> list[str]:
    """\\newcommand lines: Rfc<Metric><Context><Model> (points or k/n) for every model x context, from summary.json."""
    lines = ["% Generated by python -m suryabench.evalkit --tex; do not edit by hand.",
             f"\\newcommand{{\\RfcNContexts}}{{{len(CONTEXTS)}}}", f"\\newcommand{{\\RfcSample}}{{{SAMPLE}}}",
             f"\\newcommand{{\\RfcNModels}}{{{len(res)}}}", f"\\newcommand{{\\RfcAsOf}}{{{AS_OF}}}"]
    for m, ctx in res.items():
        for ctxname, sp in ctx.get("_title_split", {}).items():
            for kind, cell in sp.items():
                lines.append(f"\\newcommand{{\\RfcTitle{kind.capitalize()}{stem(ctxname)}{stem(m)}}}{{{cell['k']}/{cell['n']}}}")
        for ctxname, d in ctx.get("_deference", {}).items():
            k = f"{stem(ctxname)}{stem(m)}"
            lines.append(f"\\newcommand{{\\RfcDeferP{k}}}{{{d['mcnemar_p']:.4f}}}")
            lines.append(f"\\newcommand{{\\RfcDeferBarePass{k}}}{{{d['kinds'].get('pass, no finding', 0)}}}")
            lines += [f"\\newcommand{{\\RfcDeferItems{k}}}{{{d['items']}}}",
                      f"\\newcommand{{\\RfcDeferOwn{k}}}{{{d['own']}}}",
                      f"\\newcommand{{\\RfcDeferWith{k}}}{{{d['with_record']}}}"]
        for c, v in ctx.items():
            if c.startswith("_"):
                continue
            key = f"{stem(c)}{stem(m)}"
            for metric in ("disc_validity", "disc_date", "disc_any", "disc_date_any"):
                if metric in v:
                    val = f"{100 * v[metric]['mean']:+.0f}".replace("-", "$-$")
                    lines.append(f"\\newcommand{{\\Rfc{stem(metric)}{key}}}{{{val}}}")
            for role, name in (("fault", "Catch"), ("control", "FA"), ("date-control", "DateFA")):
                kk = "right" if role == "fault" else "validity"
                if role in v:
                    lines.append(f"\\newcommand{{\\Rfc{name}{key}}}{{{v[role][kk]['k']}/{v[role][kk]['n']}}}")
                    lines.append(f"\\newcommand{{\\Rfc{name}Inv{key}}}{{{v[role]['invalid']['k']}}}")
                    if role != "fault":
                        lines.append(f"\\newcommand{{\\Rfc{name}Any{key}}}{{{v[role]['any']['k']}/{v[role]['any']['n']}}}")
    return lines


if __name__ == "__main__":
    main()
