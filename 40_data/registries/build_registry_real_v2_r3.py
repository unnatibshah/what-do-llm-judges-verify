"""Rebuild registry_real.json from fragments/*.json and verify every snippet/quote verbatim.

Usage:
  python3 build_registry.py                 # merge all fragments, check, write registry_real.json
  python3 build_registry.py --check F.json  # check one fragment only (no write); dangling refs to
                                            # nodes in other fragments are reported as warnings
Exit status 1 on any error.
"""
import datetime
import glob
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = {d["doc_id"]: d for d in json.load(open(os.path.join(HERE, "documents.json"), encoding="utf-8"))}
EDGE_TYPES = {"supersedes", "amends", "partially_supersedes"}
CONF = {"high", "medium", "low"}
_text = {}


def text(doc_id):
    if doc_id not in _text:
        _text[doc_id] = open(os.path.join(HERE, "text", doc_id + ".txt"), encoding="utf-8").read()
    return _text[doc_id]


def is_draft(doc_id):
    d = DOCS[doc_id]
    return "draft" in (d.get("doc_number") or "").lower() or d["title"].lower().startswith("draft")


def check(frags, strict_refs=True):
    errs, warns = [], []
    nodes, edges, dsup = {}, {}, {}
    for name, f in frags:
        for n in f.get("nodes", []):
            nid = n.get("node_id")
            if nid in nodes:
                if nodes[nid] != n:
                    errs.append(f"{name}: node {nid} defined twice with different content")
                continue
            nodes[nid] = n
        for e in f.get("edges", []):
            edges.setdefault((e["from_node"], e["to_node"]), e)
        for d in f.get("document_supersessions", []):
            dsup.setdefault((d["doc_from"], d["doc_to"]), d)

    for nid, n in nodes.items():
        doc = n.get("doc_id")
        if doc not in DOCS:
            errs.append(f"node {nid}: unknown doc_id {doc}")
            continue
        if nid != f"{doc}#cl-{n.get('clause_ref')}":
            errs.append(f"node {nid}: node_id != doc_id#cl-clause_ref")
        if n.get("jurisdiction") != DOCS[doc]["jurisdiction"]["code"]:
            errs.append(f"node {nid}: jurisdiction {n.get('jurisdiction')} != {DOCS[doc]['jurisdiction']['code']}")
        s = n.get("snippet") or ""
        if not s or s not in text(doc):
            errs.append(f"node {nid}: snippet not verbatim in text/{doc}.txt")
        if len(s) > 600:
            errs.append(f"node {nid}: snippet {len(s)} chars > 600")
        if n.get("confidence") not in CONF:
            errs.append(f"node {nid}: bad confidence {n.get('confidence')}")
        for k in ("topic", "effective_date"):
            if not n.get(k):
                errs.append(f"node {nid}: missing {k}")

    for (a, b), e in edges.items():
        if e.get("type") not in EDGE_TYPES:
            errs.append(f"edge {a}->{b}: bad type {e.get('type')}")
        if e.get("confidence") not in CONF:
            errs.append(f"edge {a}->{b}: bad confidence")
        for x in (a, b):
            if x not in nodes:
                (errs if strict_refs else warns).append(f"edge {a}->{b}: node {x} not defined")
        newer = b.split("#")[0]
        if newer not in DOCS:
            errs.append(f"edge {a}->{b}: unknown newer doc")
            continue
        if is_draft(newer):
            errs.append(f"edge {a}->{b}: drafts are never superseding instruments")
        q = e.get("evidence_quote") or ""
        if not q or q not in text(newer):
            errs.append(f"edge {a}->{b}: evidence_quote not verbatim in text/{newer}.txt")
        if e.get("confidence") == "low" and not e.get("note"):
            warns.append(f"edge {a}->{b}: low-confidence edge without a note/reason")

    for (a, b), d in dsup.items():
        if b in DOCS:
            if is_draft(b):
                errs.append(f"doc supersession {a}->{b}: draft cannot supersede")
            if not d.get("evidence_quote") or d["evidence_quote"] not in text(b):
                errs.append(f"doc supersession {a}->{b}: evidence_quote not verbatim in text/{b}.txt")
        else:
            errs.append(f"doc supersession {a}->{b}: doc_to not in corpus")
        if d.get("confidence") not in CONF:
            errs.append(f"doc supersession {a}->{b}: bad confidence")
    return nodes, edges, dsup, errs, warns


def report(nodes, edges, dsup):
    nj = Counter(n["jurisdiction"] for n in nodes.values())
    ej = Counter(nodes[b]["jurisdiction"] if b in nodes else b[:2] for (_, b) in edges)
    docs_cov = Counter(DOCS[n["doc_id"]]["jurisdiction"]["code"] for n in {n["doc_id"]: n for n in nodes.values()}.values())
    docs_all = Counter(d["jurisdiction"]["code"] for d in DOCS.values())
    print("jur  nodes edges(by newer) docs_with_nodes/docs")
    for j in sorted(docs_all):
        print(f"{j:4} {nj[j]:5} {ej[j]:5} {docs_cov[j]:3}/{docs_all[j]}")
    print(f"TOTAL nodes={len(nodes)} edges={len(edges)} document_supersessions={len(dsup)}")
    missing = sorted(set(DOCS) - {n["doc_id"] for n in nodes.values()})
    print("docs without nodes:", missing)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        f = json.load(open(sys.argv[2], encoding="utf-8"))
        nodes, edges, dsup, errs, warns = check([(sys.argv[2], f)], strict_refs=False)
    else:
        paths = sorted(glob.glob(os.path.join(HERE, "fragments", "*.json")))
        frags = [(os.path.basename(p), json.load(open(p, encoding="utf-8"))) for p in paths]
        nodes, edges, dsup, errs, warns = check(frags)
    for w in warns:
        print("WARN", w)
    for e in errs:
        print("ERROR", e)
    report(nodes, edges, dsup)
    if errs:
        sys.exit(1)
    if len(sys.argv) == 1:
        out = {
            "generated_by": "Claude Opus (Claude Code agent), blind to gold graph, from corpus text r3",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "nodes": sorted(nodes.values(), key=lambda n: n["node_id"]),
            "edges": sorted(edges.values(), key=lambda e: (e["to_node"], e["from_node"])),
            "document_supersessions": sorted(dsup.values(), key=lambda d: (d["doc_to"], d["doc_from"])),
        }
        with open(os.path.join(HERE, "registry_real.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        # re-read and re-check what was written
        again = json.load(open(os.path.join(HERE, "registry_real.json"), encoding="utf-8"))
        *_, errs2, _ = check([("registry_real.json", again)])
        assert not errs2, errs2
        print("wrote registry_real.json (re-verified)")


if __name__ == "__main__":
    main()
