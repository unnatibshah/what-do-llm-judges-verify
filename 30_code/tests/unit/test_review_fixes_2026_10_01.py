"""Decisions D26, D27, D29 and D30 (hostile review v2, 2026-10-01): schedule vs analysis, metadata view, invalid replies."""

import re
import shlex

from suryabench.analysis import prereg
from suryabench.analysis.paper import _flagged, verifier_label
from suryabench.arms.verify_shared import relabel, unlabel
from suryabench.gate0.retriever import LocalRetriever, TextChunk, strip_title
from suryabench.paths import CODE_DIR


def _scheduled() -> set[tuple[str, str, bool]]:
    """(label, condition, metadata) of every run line in run_dev_pilot_v2.sh, as the analysis labels them."""
    text = (CODE_DIR / "scripts" / "run_dev_pilot_v2.sh").read_text(encoding="utf-8")
    env = dict(re.findall(r'^([A-Z]+)="([^"]*)"', text, re.M))
    out: set[tuple[str, str, bool]] = set()
    for line in re.findall(r"^run \S+\s+(.*)$", text, re.M):
        for k, v in env.items():
            line = line.replace(f"${k}", v)
        args, opts, key = shlex.split(line), {}, None
        for a in args:
            if a.startswith("--"):
                key = a[2:]
                opts[key] = []
            elif key:
                opts[key].append(a)
        row = {"variant": (opts.get("variant") or ["support"])[0], "taxonomy": "taxonomy" in opts,
               "model": "g", "verifier_model": "x" if "verifier-model" in opts else "g"}
        for arm in opts["arms"]:
            lab = prereg.canon(verifier_label({**row, "arm": arm}).replace("@x:x", "@x:other"))
            for meta in opts["meta"]:
                out |= {(lab, c, meta == "on") for c in opts["conditions"]}
    return out


def test_pilot_schedule_produces_every_configuration_the_analysis_needs() -> None:
    have = _scheduled()
    need = {(lab, c, True) for lab in prereg.EXPECTED_LABELS for c in prereg.EXPECTED_CONDS}
    need |= {(lab, c, False) for lab, c in prereg.EXPECTED_META_OFF}
    need |= {(a[0], c, a[1]) for pair in prereg.EXPLORATORY_CONTRASTS.values() for a in pair
             for c in prereg.PRIMARY_CONDITIONS + ["C"] if a[0] not in prereg.NOISE_LEVELS}
    assert need - have == set()


def test_metadata_off_relabels_document_ids_and_maps_findings_back() -> None:
    labels = {"UP-C3-001": "SRC-AB12CD", "UP-C3-002": "SRC-0F0F0F"}
    text = relabel("cited UP-C3-001#cl-6.2 and UP-C3-002 (UP-C3-0011 is not a doc)", labels)
    assert "UP-C3-001#" not in text and "SRC-AB12CD#cl-6.2" in text and "UP-C3-0011" in text
    findings, flags = unlabel([{"class": "ANY", "clause_id": "SRC-AB12CD#cl-6.2", "reason": "not_in_force",
                                "rationale": ""}], labels)
    assert findings[0]["clause_id"] == "UP-C3-001#cl-6.2" and flags == ["ANY:UP-C3-001#cl-6.2:not_in_force"]  # D32


def test_metadata_off_header_has_no_dates_and_no_metadata() -> None:
    assert strip_title("Guidelines (original, 2024)") == "Guidelines"
    assert strip_title("UPERC RSPV Regulations, 2015") == "UPERC RSPV Regulations"
    r = LocalRetriever([TextChunk(chunk_id="D-C1-001#chk-0", doc_id="D-C1-001", text="body", char_start=0, char_end=4)])
    r.doc_titles = {"D-C1-001": "Amended Order dated 01.06.2023 (FY24)"}
    r.doc_meta = {"D-C1-001": {"issuer": "X", "jurisdiction": "IN", "effective_date": "2023-06-01"}}
    r.meta = False
    off = r.format_chunk(r.chunks[0])
    assert "2023" not in off and "issuer=" not in off and "Amended" not in off and "FY" not in off
    r.meta = True
    on = r.format_chunk(r.chunks[0])
    assert "effective=2023-06-01" in on and "jurisdiction=IN" in on and "superseded" not in on.lower()


def test_invalid_verifier_reply_is_a_false_alarm_and_a_miss() -> None:
    rec = {"raw": {"verifier": {"verdict": "INVALID", "is_flagged": False}}, "verifier_flags": []}
    assert _flagged(rec)  # D30: FPR counts it as a flag; it has no findings, so it catches nothing
