"""Write the annotation sheets of 20_method/ANNOTATION-PACKET.md into 20_method/annotation/.

- clauses_to_check.csv: every clause node and every supersession edge of corpus r3 (r2 + staged), with the
  document URL and the agent's quote; the annotator's columns are left blank.
- cases_to_label.csv: the candidate v3 test cases (up to PER_CLUSTER per rule group across trap types, which for
  v3's four applications per replaced clause is every case): application facsimile text only, no expected answer,
  no cluster or trap type.
- ANSWER_KEY_DO_NOT_SHARE.csv: the agent's labels for the sampled cases (for kappa later).
- links_to_verify.csv (P2-2, H-03): every link of the non-gold registry that a v3 probe answer's citation resolves
  to (the R3 quote and the R4/R5 status come from these), plus a seeded 20% of the other links as a quality
  sample. Blind: the old clause and the newer document only; the link's type, date, quote, target clause and the
  agent's EXPLICIT/IMPLICIT tag (P2-6) are in LINKS_KEY_DO_NOT_SHARE.csv, which annotators never see (D41).
- controls_check.csv (H-05): 40 seeded correct answers of the v3 probe (matched controls and clean answers,
  spread over rule groups), each with the clauses its evidence shows. Done after the case labels are submitted.
- sources_to_check.csv (H-02 for the test scope, D42): every document behind a v3 test item's evidence or registry
  status line, with its URL and saved hash; the agent's verdict is not shown.
- r3_quotes_check.csv (H-06): every amendment quote rung R3 shows for a v3 answer, beside the old and new
  clause. Done after the link sheet is submitted.

Reads 40_data/benchmark/test_cases_v3_CANDIDATE.json directly: this is not a model run. Never reads
test_cases_100.json or benchmark_cases_160.json.

Usage (repository root): PYTHONPATH=30_code/src:30_code/scripts python 30_code/scripts/build_annotation_materials.py
"""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import build_corpus_r3 as b
from build_test_candidate_v3 import CANDIDATE_V3
from count_ladder_items import ProbeWorld, link_tag

from suryabench.arms import verifier_probe as vp
from suryabench.cases.schema import BenchmarkCase
from suryabench.paths import ANNOTATION_DIR, BENCHMARK_DIR, CORPUS_R3_DIR

PER_CLUSTER = 6
SEED = "SuryaBench-annotation-sample-2026-10"
CLAUSE_COLS = ["doc_url_ok", "quote_matches", "rule_in_own_words", "values", "conditions", "effective_date",
               "superseded_by", "supersession_quote", "confidence", "notes"]
CASE_COLS = ["decision", "blocking_stage", "deciding_clauses", "minutes_spent", "notes"]
LINK_SAMPLE = 0.2
LINK_COLS = ["new_clause_id", "relation", "effective_date", "substitution_quote", "wording", "confidence", "source_page",
             "annotator_id", "minutes", "notes"]  # H-03
N_CONTROLS = 40


def write(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def pages() -> dict[str, Any]:
    """node_id -> page of the quote, from the staging provenance records."""
    stem_id = {stem.split("/")[1]: v[0] for stem, v in b.DOCS.items()}
    out: dict[str, Any] = {}
    for stem in b.DOCS:
        prov = json.loads((b.CORPUS_STAGING_DIR / f"{stem}.provenance.json").read_text(encoding="utf-8"))
        short = stem.split("/")[1]
        for c in prov.get("candidate_clauses", []):
            out[f"{stem_id[short]}#cl-{b.NID[(short, c['clause_ref'])][0]}"] = c.get("page")
    return out


def sample(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per cluster, one case of each probed class in turn (round robin) until PER_CLUSTER are taken."""
    rng = random.Random(SEED)
    by: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for c in sorted(cases, key=lambda c: c["case_id"]):
        by[c["cluster_id"]][c["failure_class_probed"]].append(c)
    chosen = []
    for cluster in sorted(by):
        pools = [by[cluster][k] for k in sorted(by[cluster])]
        for p in pools:
            rng.shuffle(p)
        taken: list[dict[str, Any]] = []
        while len(taken) < PER_CLUSTER and any(pools):
            for p in pools:
                if p and len(taken) < PER_CLUSTER:
                    taken.append(p.pop())
        chosen += taken
    rng.shuffle(chosen)
    return chosen


def links_sheet(world: ProbeWorld, items: list[vp.ProbeItem], manifest: dict[str, Any]
                ) -> tuple[list[list[Any]], list[list[Any]]]:
    """(key rows, blind annotator rows): links used by a v3 probe answer's citations, then the quality sample."""
    used: dict[str, set[str]] = defaultdict(set)
    for it in items:
        for cited in it.answer.cited_rules:
            for e in world.registry_links(cited)[1]:
                used[e["link_id"]].add(f"{'planted' if cited == it.planted else 'cited'}:{cited}")
    rest = sorted(f"L{i:03d}" for i in range(len(world.links)) if f"L{i:03d}" not in used)
    sample = set(random.Random(SEED + "|links").sample(rest, round(len(rest) * LINK_SAMPLE)))

    def url(node: str) -> str:
        return str(manifest.get(node.split("#")[0], {}).get("retrieved_url") or "")

    snippet = {n["node_id"]: " ".join(str(n.get("snippet") or "").split()) for n in
               json.loads(world.registry_file.read_text(encoding="utf-8"))["nodes"]}
    key, blind = [], []
    for i, e in enumerate(world.links):
        lid = f"L{i:03d}"
        if lid in used or lid in sample:
            key.append([lid, e["from_node"], e["to_node"], e["type"], e.get("confidence") or "", link_tag([e]),
                        e.get("effective_date") or "", url(e["from_node"]), url(e["to_node"]),
                        " ".join(str(e.get("evidence_quote") or "").split()),
                        "test_pair" if lid in used else "quality_sample", ";".join(sorted(used.get(lid, set())))])
            new_doc = e["to_node"].split("#")[0]
            blind.append([lid, e["from_node"], snippet.get(e["from_node"], ""), url(e["from_node"]), new_doc,
                          str(manifest.get(new_doc, {}).get("title") or ""), url(e["to_node"]), *[""] * len(LINK_COLS)])
    return key, blind


def controls_sheet(world: ProbeWorld, items: list[vp.ProbeItem]) -> list[list[Any]]:
    """H-05: N_CONTROLS correct answers, round robin over rule groups (seeded), with the clauses their evidence shows."""
    rng = random.Random(SEED + "|controls")
    pools: dict[str, list[vp.ProbeItem]] = defaultdict(list)
    for it in sorted((i for i in items if i.role != "fault"), key=lambda i: i.item_id):
        pools[it.cluster].append(it)
    for p in pools.values():
        rng.shuffle(p)
    chosen: list[vp.ProbeItem] = []
    while len(chosen) < N_CONTROLS and any(pools.values()):
        for g in sorted(pools):
            if pools[g] and len(chosen) < N_CONTROLS:
                chosen.append(pools[g].pop())
    rows = []
    for it in sorted(chosen, key=lambda i: i.item_id):
        a = it.answer
        rows.append([it.item_id, it.case_id, a.decision, a.blocking_stage or "", ";".join(a.cited_rules), a.root_cause,
                     ";".join(sorted(vp.shown_clauses(it.evidence_ids, world.retriever))), "", "", ""])
    return rows


def sources_sheet(world: ProbeWorld, items: list[vp.ProbeItem], manifest: dict[str, Any]) -> list[list[Any]]:
    """H-02 within annotation (D42): documents a reported number depends on, i.e. those of the clauses each v3 item's
    evidence shows, and those of the registry entries and links its citations resolve to (the R3-R5 information)."""
    used: dict[str, set[str]] = defaultdict(set)
    for it in items:
        for c in vp.shown_clauses(it.evidence_ids, world.retriever):
            used[c.split("#")[0]].add("evidence")
        for cited in it.answer.cited_rules:
            nodes, links = world.registry_links(cited)
            for n in nodes:
                used[n.split("#")[0]].add("registry status")
            for e in links:
                used[e["to_node"].split("#")[0]].add("registry link")
    return [[d, manifest.get(d, {}).get("title", ""), manifest.get(d, {}).get("issuer", ""),
             manifest.get(d, {}).get("retrieved_url", ""), manifest.get(d, {}).get("sha256", ""), ";".join(sorted(u)),
             "", "", "", ""] for d, u in sorted(used.items()) if d in manifest]


def r3_quotes_sheet(world: ProbeWorld, items: list[vp.ProbeItem]) -> list[list[Any]]:
    """H-06: every (link, quote) rung R3 can show for a v3 answer (amendment_quotes), with both clauses' text."""
    nodes = {n["node_id"]: " ".join(str(n.get("snippet") or "").split()) for n in
             json.loads(world.registry_file.read_text(encoding="utf-8"))["nodes"]}
    cited_by: dict[str, set[str]] = defaultdict(set)
    links: dict[str, dict[str, Any]] = {}
    for it in items:
        for cited in it.answer.cited_rules:
            for e in world.registry_links(cited)[1]:
                if " ".join(str(e.get("evidence_quote") or "").split()):
                    links[e["link_id"]] = e
                    cited_by[e["link_id"]].add(cited)
    return [[lid, e["from_node"], nodes.get(e["from_node"], ""), e["to_node"], nodes.get(e["to_node"], ""),
             " ".join(str(e["evidence_quote"]).split()), ";".join(sorted(cited_by[lid])), "", "", ""]
            for lid, e in sorted(links.items())]


def decision(c: dict[str, Any]) -> str:
    if c["expected_decision"] == "ABSTAIN":
        return "ABSTAIN"
    return "REJECTED" if c["expected_answer"]["blocking_stage"] else "APPROVED"


def main() -> None:
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads((CORPUS_R3_DIR / "graph" / "supersession.json").read_text(encoding="utf-8"))
    manifest = {d["doc_id"]: d for d in json.loads((CORPUS_R3_DIR / "MANIFEST.json").read_text(encoding="utf-8"))["documents"]}
    cases = json.loads((BENCHMARK_DIR / CANDIDATE_V3).read_text(encoding="utf-8"))
    dev = json.loads((BENCHMARK_DIR / "dev_cases_v2.json").read_text(encoding="utf-8"))
    decisive = {r["rule_id"] for c in cases for r in c["applicable_rules"]}
    traps = {e for c in cases for f in c["fault_events"] for e in f["gold_evidence"] if "#" in e}
    dev_rules = {r["rule_id"] for c in dev for r in c["applicable_rules"]}
    page = pages()

    rows = []
    for nid, n in sorted(graph["nodes"].items()):
        d = manifest[n["doc_id"]]
        role = ";".join(r for r, s in (("decisive_test_candidate", decisive), ("trap_test_candidate", traps),
                                        ("dev", dev_rules)) if nid in s) or "other"
        rows.append(["clause", nid, n["doc_id"], n["clause_ref"], role, d.get("retrieved_url") or "",
                     d.get("source_class") or "r2", n.get("verification_status") or "r2 (agent-built, not human-checked)",
                     page.get(nid, ""), n["clause_text_snippet"], *[""] * len(CLAUSE_COLS)])
    for e in graph["edges"]:
        d = manifest[e["evidence"]["doc_id"]]
        rows.append(["edge", f"{e['from']} -> {e['to']}", e["evidence"]["doc_id"], e["relation"], "supersession_edge",
                     d.get("retrieved_url") or "", d.get("source_class") or "r2",
                     e.get("verification_status") or "r2 (agent-built, not human-checked)", "",
                     e["evidence"]["quote_text"], *[""] * len(CLAUSE_COLS)])
    write(ANNOTATION_DIR / "clauses_to_check.csv",
          ["item_type", "clause_id", "doc_id", "clause_ref_or_relation", "role", "doc_url", "source_class",
           "verification_status", "page", "agent_quote", *CLAUSE_COLS], rows)

    chosen = sample(cases)
    # The sample is fixed once drawn: a rebuild keeps the sheet's cases (and order) while all still exist,
    # so dropping an unsampled case (2026-10-01) does not reshuffle what annotators already hold.
    prev_sheet = ANNOTATION_DIR / "cases_to_label.csv"
    by_id = {c["case_id"]: c for c in cases}
    if prev_sheet.exists():
        with open(prev_sheet, encoding="utf-8", newline="") as f:
            prev = [r["case_id"] for r in csv.DictReader(f)]
        if prev and all(i in by_id for i in prev):
            chosen = [by_id[i] for i in prev]
        else:  # ponytail: a missing case redraws the whole sample; per-cluster replacement if annotation has begun
            print("WARNING: a sampled case no longer exists; the sample was redrawn")
    write(ANNOTATION_DIR / "cases_to_label.csv", ["case_id", "bill", "proposal", "portal_state", *CASE_COLS],
          [[c["case_id"], c["inputs"]["bill"], c["inputs"]["proposal"], c["inputs"]["portal_state"],
            *[""] * len(CASE_COLS)] for c in chosen])
    write(ANNOTATION_DIR / "ANSWER_KEY_DO_NOT_SHARE.csv",
          ["case_id", "decision", "blocking_stage", "deciding_clauses", "cluster_id", "failure_class_probed",
           "ground_truth_confidence"],
          [[c["case_id"], decision(c), c["expected_answer"]["blocking_stage"] or "",
            ";".join(sorted(r["rule_id"] for r in c["applicable_rules"])), c["cluster_id"], c["failure_class_probed"],
            c["ground_truth_provenance"]["confidence"]] for c in sorted(chosen, key=lambda c: c["case_id"])])
    world = ProbeWorld()
    items, _ = vp.build_items([BenchmarkCase.model_validate(c) for c in cases], world.graph, world.predicates,
                              world.retriever)
    key, blind = links_sheet(world, items, manifest)
    write(ANNOTATION_DIR / "LINKS_KEY_DO_NOT_SHARE.csv",
          ["link_id", "old_clause_id", "new_clause_id", "link_type", "confidence", "explicit_implicit_agent",
           "effective_date", "old_doc_url", "new_doc_url", "quote", "selected_as", "cited_by_test_pairs"], key)
    write(ANNOTATION_DIR / "links_to_verify.csv",
          ["link_id", "old_clause_id", "old_clause_text_to_locate_it", "old_doc_url", "newer_doc_id", "newer_doc_title",
           "newer_doc_url", *LINK_COLS], blind)
    controls = controls_sheet(world, items)
    write(ANNOTATION_DIR / "controls_check.csv",
          ["item_id", "case_id", "answer_decision", "answer_blocking_stage", "answer_cited_clauses", "answer_rationale",
           "clauses_in_its_evidence", "decision", "reason", "annotator_id"], controls)
    sources = sources_sheet(world, items, manifest)
    write(ANNOTATION_DIR / "sources_to_check.csv",
          ["doc_id", "title", "issuer", "url", "saved_sha256", "used_as", "url_is_official", "document_matches_saved",
           "annotator_id", "notes"], sources)
    quotes = r3_quotes_sheet(world, items)
    write(ANNOTATION_DIR / "r3_quotes_check.csv",
          ["link_id", "old_clause_id", "old_clause_text", "new_clause_id", "new_clause_text", "quote_shown_at_R3",
           "shown_for_cited_clauses", "decision", "annotator_id", "notes"], quotes)
    print(f"clauses_to_check: {len(rows)} rows; cases_to_label: {len(chosen)} cases from "
          f"{len({c['cluster_id'] for c in chosen})} clusters; links_to_verify: {len(blind)} links "
          f"({sum(r[10] == 'test_pair' for r in key)} used by test pairs); controls_check: {len(controls)}; "
          f"r3_quotes_check: {len(quotes)}; sources_to_check: {len(sources)}")


if __name__ == "__main__":
    main()
