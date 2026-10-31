"""D51: the evalkit harness builds matched items, renders each context as specified and scores by reason."""

from suryabench import evalkit as ek

DOCS = {"RFC1": ek.Doc("RFC1", "Old spec", "2001-03", "Defines the thing. This document is obsoleted later."),
        "RFC2": ek.Doc("RFC2", "New spec", "2010-06", "Defines the thing again. This document obsoletes RFC 1.")}
LINK = ek.Link("RFC1", "RFC2")


def test_items_and_dates() -> None:
    f, c, d = ek.items([LINK], DOCS)
    assert (f.role, f.cited, c.cited, d.cited) == ("fault", "RFC1", "RFC2", "RFC1")
    assert f.as_of == ek.AS_OF and d.as_of < DOCS["RFC2"].date and d.as_of[:7] > DOCS["RFC1"].date


def test_contexts_show_only_what_they_name() -> None:
    f, _, d = ek.items([LINK], DOCS)
    rec = {("RFC1", "RFC2")}
    both = ek.render(f, "both-texts", DOCS, rec)
    assert "obsolete" not in both.split("[EVIDENCE]")[1].split("[TASK]")[0].lower()  # replacement wording scrubbed
    assert "Obsoletes: RFC1" in ek.render(f, "both-explicit", DOCS, rec)
    assert "superseded (by RFC2" in ek.render(f, "status", DOCS, rec)
    assert "in_force" in ek.render(d, "status", DOCS, rec)  # before the replacement existed
    assert "no_replacement_recorded" in ek.render(f, "norecord-damaged", DOCS, set())
    assert "RFC1" not in ek.render(f, "both-masked", DOCS, rec) and "(none)" in ek.render(f, "cite-only", DOCS, rec)


def test_scoring_is_reason_coded() -> None:
    f, c, _ = ek.items([LINK], DOCS)
    right = {"verdict": "FLAG", "findings": [{"doc_id": "RFC1", "reason": "superseded"}]}
    wrong_reason = {"verdict": "FLAG", "findings": [{"doc_id": "RFC1", "reason": "content_error"}]}
    assert ek.score(f, right)["right"] and not ek.score(f, wrong_reason)["right"] and ek.score(f, wrong_reason)["any"]
    assert not ek.score(c, {"verdict": "PASS", "findings": []})["any"] and ek.score(f, None)["invalid"]
    masked = ek.masked_ids(f)
    assert ek.score(f, {"findings": [{"doc_id": masked["RFC1"], "reason": "superseded"}]}, masked)["right"]


def test_rfc_adapter_and_summary() -> None:
    docs, links, shots = ek.rfc_links(n=10)
    assert len(links) == 10 and len(shots) == 2 and not set(links) & set(shots)
    assert ek.rfc_links(n=48)[1][:10] == links and ek.rfc_links(n=48)[2] == shots  # a smaller run is a prefix
    assert all(docs[lk.old].date < docs[lk.new].date for lk in links)
    rows = [{**ek.asdict(i), "right": i.role == "fault", "any": False, "validity": False, "invalid": False}
            for i in ek.items(links, docs)]
    s = ek.summarise(rows, boot=50)
    assert s["disc_validity"]["mean"] == 1.0 and s["fault"]["right"]["k"] == 10


def test_deference_pairs_dropped_faults_with_the_no_record_catch() -> None:
    blocks = {"both-texts": [{"item_id": "a#fault", "role": "fault", "right": True},
                             {"item_id": "b#fault", "role": "fault", "right": True}],
              "status-damaged": [{"item_id": "a#fault", "role": "fault", "right": False, "dropped": True},
                                 {"item_id": "b#fault", "role": "fault", "right": True, "dropped": False}]}
    d = ek.deference(blocks)["status-damaged"]
    assert (d["items"], d["own"], d["with_record"]) == (1, 1, 0) and d["kinds"] == {"invalid": 1}


def test_title_split_mcnemar_and_rationale_coding() -> None:
    assert ek.same_title("Mobile IPv6 Deployment", "Mobile IPv6 deployment") and not ek.same_title("SMTP", "Unicode Format")
    assert ek.mcnemar(12, 0) < 0.001 and ek.mcnemar(1, 1) == 1.0
    assert ek.rationale_kind({"verdict": "PASS", "findings": []}) == "pass, no finding"
    assert ek.rationale_kind({"findings": [{"rationale": "the record says it is in force"}]}) == "cites the record"


def test_decoys_match_title_type_and_stay_in_force() -> None:
    docs, links, _ = ek.rfc_links(n=24)
    dec = ek.rfc_decoys(links, docs)
    assert len(dec) == 24 and len({d for lk in dec for d in (lk.old, lk.new)}) == 48
    assert [ek.same_title(docs[d.old].title, docs[d.new].title) for d in dec] == \
        [ek.same_title(docs[lk.old].title, docs[lk.new].title) for lk in links]
    assert not {d for lk in dec for d in (lk.old, lk.new)} & {d for lk in links for d in (lk.old, lk.new)}
    it = ek.decoy_items(dec, docs)[0]
    rec = {(lk.old, lk.new) for lk in links}
    assert it.role == "decoy" and "in_force" in ek.render(it, "status", docs, rec)
    assert "Updates: " in ek.render(it, "both-explicit", docs, rec)
    assert not ek.score(it, {"verdict": "PASS", "findings": []})["validity"]


def test_caveat_context_labels_the_record_and_old_contexts_are_unchanged() -> None:
    f, _, _ = ek.items([LINK], DOCS)
    assert "incomplete" in ek.render(f, "caveat-damaged", DOCS, set())
    assert ek.render(f, "caveat-damaged", DOCS, set()).replace(ek.render(f, "status-damaged", DOCS, set()), "") != ""
    assert "incomplete" not in ek.render(f, "status-damaged", DOCS, set())
    low = ek.render(f, "lowauth-damaged", DOCS, set())
    assert "UNVERIFIED NOTE" in low and "RECORD LOOKUP" not in low and "in_force" in low


def test_decoys_are_balanced_on_dates() -> None:
    docs, links, _ = ek.rfc_links()
    b = ek.decoy_balance(links, ek.rfc_decoys(links, docs), docs)
    assert all(abs(b[k]["smd"]) < 0.25 for k in ("old_year", "new_year", "gap_years", "title_ratio"))
