"""T1 (P3-1): which distinct replaced clauses can yield outdated-rule pairs, per rule group. No model is run.

For every rule group of the candidate pool (the 20 v2 groups and the groups added in D38) the verifier-probe pair
builder (``arms/verifier_probe.build_items``) is run over the generated cases (case structure only). For each
planted superseded clause it reports the S-both and S-swap pairs (outcome-changing or basis-only, approve or
reject), the gold supersession edge, and what the non-gold registry (``registry_real_v2_r3.json``) says about it:
the registry entries the citation resolves to, their links, the EXPLICIT/IMPLICIT tag and whether the deterministic
registry calls the clause not in force at each case date (the R4/R5 information).

EXPLICIT/IMPLICIT (P2-6, confirmed by annotators in H-03): EXPLICIT when a link from a resolved entry is of type
``supersedes`` or ``amends`` with confidence ``high`` and its note does not call it implicit; IMPLICIT when there
are links but none qualifies; NONE when the registry has no link for the clause.

Output: 50_analysis/results/ladder_design/available_items.json

Usage (repository root): PYTHONPATH=30_code/src:30_code/scripts python 30_code/scripts/count_ladder_items.py
"""

import json
from collections import Counter, defaultdict
from typing import Any

from suryabench.applicability.schema import ApplicabilityPredicate
from suryabench.arms import verifier_probe as vp
from suryabench.arms.controlled_exposure import cluster_anchor
from suryabench.arms.verify_independent import (
    Registry,
    load_registry,
    norm_clause_id,
    resolve_citation,
)
from suryabench.cases.generator_v3 import ADDED_V3_CLUSTERS, generate_v3_pool
from suryabench.cases.schema import BenchmarkCase
from suryabench.corpus.manifest import load_manifest
from suryabench.eval.runner import default_real_registry
from suryabench.gate0.retriever import LocalRetriever, build_corpus_chunks, map_chunks_to_clauses
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import SupersessionGraph
from suryabench.paths import RESULTS_DIR, corpus_dir

OUT_DIR = RESULTS_DIR / "ladder_design"
S_CONDITIONS = ("S-both", "S-swap")
MIN_PAIRS = 3


class ProbeWorld:
    """Corpus r3 as the probe sees it (graph, predicates, chunk -> clause map, real registry), without the dense index:
    pair building and registry lookups never retrieve."""

    def __init__(self) -> None:
        d = corpus_dir("r3")
        self.graph = SupersessionGraph.model_validate(json.loads((d / "graph" / "supersession.json").read_text(encoding="utf-8")))
        self.predicates = [ApplicabilityPredicate.model_validate(p)
                           for p in json.loads((d / "graph" / "applicability.json").read_text(encoding="utf-8"))]
        chunks = build_corpus_chunks(d / "text")
        self.retriever = LocalRetriever(chunks)
        self.retriever.chunk_clauses = map_chunks_to_clauses(chunks, self.graph.nodes.values(), d / "text")
        self.manifest = load_manifest(d / "MANIFEST.json")
        self.retriever.doc_titles = {m.doc_id: m.title for m in self.manifest.documents}
        path, _ = default_real_registry("r3")
        self.registry_file = path
        real = load_registry(path, {m.doc_id: str(m.effective_date) for m in self.manifest.documents})
        self.registry = Registry("reg-real", real, map_chunks_to_clauses(chunks, real.nodes.values(), d / "text"))
        self.links = json.loads(path.read_text(encoding="utf-8"))["edges"]  # link id = "L" + index in this list

    def registry_links(self, clause: str) -> tuple[list[str], list[dict[str, Any]]]:
        """(registry entries the citation resolves to, links out of them, each with its link id)."""
        nodes = resolve_citation(clause, self.registry, self.retriever) or []
        keys = {norm_clause_id(n) for n in nodes}
        links = [{"link_id": f"L{i:03d}", **e} for i, e in enumerate(self.links) if norm_clause_id(e["from_node"]) in keys]
        return nodes, links

    def registry_flags(self, clause: str, nodes: list[str], date: str) -> bool:
        """Does the deterministic registry call ``clause`` not in force at ``date`` (what R4/R5 are told)?"""
        stale = ("superseded", "partially_superseded")
        since = self.registry.graph.superseded_documents.get(clause.split("#")[0])
        return any(in_force(n, date, self.registry.graph).value in stale for n in nodes) or bool(since and since <= date)


def link_tag(links: list[dict[str, Any]]) -> str:
    if not links:
        return "NONE"
    explicit = any(e["type"] in {"supersedes", "amends"} and e.get("confidence") == "high"
                   and "implicit" not in str(e.get("note") or "").lower() for e in links)
    return "EXPLICIT" if explicit else "IMPLICIT"


def state_of(clause: str) -> str:
    return clause.split("-", 1)[0]


def count(world: ProbeWorld, cases: list[BenchmarkCase]) -> dict[str, Any]:
    """Per rule group and per planted superseded clause: S pairs, registry facts, skip reasons."""
    items, skips = vp.build_items(cases, world.graph, world.predicates, world.retriever)
    by_id = {c.case_id: c for c in cases}
    gold_edge = {e.from_node: e for e in world.graph.edges if e.relation.value == "superseded_by"}
    groups: dict[str, dict[str, Any]] = {}
    for c in cases:
        g = groups.setdefault(str(c.cluster_id), {"group": str(c.cluster_id), "state": c.facts.state.value,
                                                  "added_v3": c.cluster_id in ADDED_V3_CLUSTERS, "n_cases": 0,
                                                  "replaced_clauses": {}, "s_skips": Counter()})
        g["n_cases"] += 1
    for key, why in skips.items():
        case_id, cond = key.split("#")[:2]
        if cond in S_CONDITIONS:
            groups[str(by_id[case_id].cluster_id)]["s_skips"][f"{cond}: {why}"] += 1

    per: dict[tuple[str, str], list[vp.ProbeItem]] = defaultdict(list)
    for it in items:
        if it.condition in S_CONDITIONS and it.planted:
            per[(it.cluster, str(it.planted))].append(it)
    for (group, plant), its in sorted(per.items()):
        nodes, links = world.registry_links(plant)
        edge = gold_edge.get(plant)
        entry: dict[str, Any] = {
            "clause": plant, "state": state_of(plant), "successor": cluster_anchor(by_id[its[0].case_id], world.graph),
            "gold_edge": {"to": edge.to_node, "evidence_type": edge.evidence.type.value, "confidence": edge.confidence.value,
                          "from_date": edge.from_date} if edge else None,
            "registry": {"entries": nodes, "links": [{k: e[k] for k in ("link_id", "from_node", "to_node", "type",
                                                                        "confidence", "effective_date")} for e in links],
                         "explicit_implicit": link_tag(links)},
        }
        flagged = []
        for cond in S_CONDITIONS:
            faults = [i for i in its if i.condition == cond and i.role == "fault"]
            entry[cond] = {"pairs": len(faults), "outcome_changing": sum(i.outcome_changing for i in faults),
                           "basis_only": sum(not i.outcome_changing for i in faults),
                           "gold_approve": sum(i.answer.decision == "APPROVED" for i in faults if not i.outcome_changing)
                           + sum(i.answer.decision != "APPROVED" for i in faults if i.outcome_changing),
                           "controls": sum(i.condition == cond and i.role == "control" for i in its),
                           "cases": sorted(i.case_id for i in faults)}
        for cid in entry["S-both"]["cases"]:
            flagged.append(world.registry_flags(plant, nodes, str(by_id[cid].facts.case_date)))
        entry["registry"]["flags_superseded_at_case_date"] = f"{sum(flagged)}/{len(flagged)}"
        groups[group]["replaced_clauses"][plant] = entry

    out = []
    for g in sorted(groups.values(), key=lambda g: g["group"]):
        g["replaced_clauses"] = list(g["replaced_clauses"].values())
        g["s_skips"] = dict(sorted(g["s_skips"].items()))
        out.append(g)
    usable = [r for g in out for r in g["replaced_clauses"] if r["S-both"]["pairs"] >= MIN_PAIRS]
    return {
        "groups": out,
        "summary": {
            "n_groups": len(out), "n_groups_added_v3": sum(g["added_v3"] for g in out),
            f"distinct_replaced_clauses_with_at_least_{MIN_PAIRS}_S_both_pairs": len(usable),
            "states": dict(sorted(Counter(r["state"] for r in usable).items())),
            "explicit_implicit": dict(sorted(Counter(r["registry"]["explicit_implicit"] for r in usable).items())),
            "clauses": [r["clause"] for r in usable],
        },
    }


def main() -> None:
    world = ProbeWorld()
    result = count(world, generate_v3_pool(world.graph))
    result["inputs"] = {"cases": "generated in memory by cases/generator_v3.generate_v3_pool (structure only)",
                        "registry": world.registry_file.name, "pair_builder": "arms/verifier_probe.build_items"}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "available_items.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    s = result["summary"]
    print(f"{s[f'distinct_replaced_clauses_with_at_least_{MIN_PAIRS}_S_both_pairs']} distinct replaced clauses with "
          f">= {MIN_PAIRS} S-both pairs; states {s['states']}; {s['explicit_implicit']}")
    for g in result["groups"]:
        for r in g["replaced_clauses"]:
            print(f"  {g['group']:34} {r['clause']:36} S-both {r['S-both']['pairs']:2} (oc {r['S-both']['outcome_changing']})"
                  f" S-swap {r['S-swap']['pairs']:2} ctrl {r['S-swap']['controls']:2} {r['registry']['explicit_implicit']:8}"
                  f" reg {r['registry']['flags_superseded_at_case_date']}")


if __name__ == "__main__":
    main()
