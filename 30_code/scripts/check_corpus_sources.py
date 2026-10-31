"""T5 (P2-1, H-02 first pass): source checks for every corpus-r3 document, and a first-pass authentication of the
UNVERIFIED ones. Reads 40_data/corpus_r3/MANIFEST.json and the saved files; fetches each source URL once.

1. 40_data/corpus_r3/SOURCE_CHECK.csv (all documents): the URL's HTTP status and type now, whether the saved file
   still hashes to the manifest, text length, language, needs_human (Y for every UNVERIFIED document).
2. 40_data/corpus_r3/SOURCE_VERIFICATION.csv (UNVERIFIED documents only): AGENT_VERIFIED or NEEDS_HUMAN, with the
   evidence. AGENT_VERIFIED needs all of:
   - the source domain belongs to the issuer, a regulator, a government (``*.gov.in``, ``*.nic.in``) or a
     state-owned DISCOM publishing its own document (a DISCOM's copy of someone else's document is not enough);
   - the bytes fetched now from the recorded URL hash to the saved copy (or, for an archive, to the saved archive);
   - the saved text carries the recorded title (most of its words) and, where recorded, its number and date.
   Anything else is NEEDS_HUMAN, with the failed checks named.
3. The agent's manual follow-up of NEEDS_HUMAN rows (issuer's own copy looked up and compared by hand) is kept in
   40_data/corpus_r3/SOURCE_VERIFICATION_FOLLOWUP.csv and merged here (``followup`` columns); its verdict replaces the
   mechanical one. Humans decide the rows still NEEDS_HUMAN in USER-TASKS U1 (H-02).

Usage (repository root): PYTHONPATH=30_code/src python 30_code/scripts/check_corpus_sources.py
"""

import csv
import hashlib
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from suryabench.paths import CORPUS_R3_DIR

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SuryaBench source check"
# Regulators and governments (issuer-independent), and state-owned DISCOMs (official only for their own documents).
OFFICIAL = ("gov.in", "nic.in", "gercin.org", "uperc.org", "merc.gov.in", "cbip.org")
STATE_DISCOM = {"srtpv.bescom.org": "BESCOM", "www.tnebltd.gov.in": "TNEB", "tneb.tnebnet.org": "TNEB",
                "www.mahadiscom.in": "MSEDCL"}
PLACEHOLDER = ("not ", "unknown", "n/a", "per portal", "draft", "landing page")  # manifest notes, not numbers
STOP = {"the", "of", "and", "for", "in", "on", "to", "a", "an", "under", "with", "by", "from", "regulations", "order"}


def fetch(url: str) -> dict[str, Any]:
    """GET the URL with curl (redirects followed; curl uses the system certificate store, which accepts the
    incomplete chains several Indian government sites serve): status, final URL, type, size and sha256 of the body."""
    if not url:
        return {"http_status": "no_url"}
    with tempfile.NamedTemporaryFile() as tmp:
        p = subprocess.run(["curl", "-sSL", "-m", "120", "-A", UA, "-o", tmp.name, "-w",
                            "%{http_code}\t%{content_type}\t%{url_effective}", quote(url, safe=":/?&=%#+,;@!$'()*~")],
                           capture_output=True, text=True)
        if p.returncode:
            return {"http_status": f"error: {p.stderr.strip()[:80]}"}
        code, ctype, final = (p.stdout.split("\t") + ["", ""])[:3]
        body = Path(tmp.name).read_bytes()
    out: dict[str, Any] = {"http_status": int(code) if code.isdigit() else code, "final_url": final,
                           "content_type": ctype.split(";")[0], "bytes": len(body)}
    if out["http_status"] == 200:
        out["fetched_sha256"] = hashlib.sha256(body).hexdigest()
    return out


def language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "none (scan without text)"
    deva = sum("ऀ" <= c <= "ॿ" for c in letters) / len(letters)
    return "hi" if deva > 0.5 else "en+hi" if deva > 0.05 else "en"


def domain_kind(url: str, doc: dict[str, Any]) -> tuple[bool, str]:
    host = urlparse(url).netloc.lower()
    if any(host == d or host.endswith("." + d) for d in OFFICIAL):
        return True, f"{host}: regulator or government domain"
    if host in STATE_DISCOM:
        own = doc.get("source_class") == "discom_original"
        return own, f"{host}: state-owned DISCOM ({STATE_DISCOM[host]}), " + (
            "its own document" if own else "a copy of another issuer's document")
    return False, f"{host or 'no URL'}: not a regulator, government or issuer domain"


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def identity(doc: dict[str, Any], prov: dict[str, Any], text: str) -> tuple[bool, str]:
    """Does the saved text carry the recorded title, number and date?"""
    flat = " ".join(text.split()).lower()
    title = str(prov.get("printed_title") or doc.get("title") or "")
    tw = words(title)
    hit = len(tw & words(flat[:20000])) / len(tw) if tw else 0.0
    notes = [f"title words found {hit:.0%}"]
    ok = hit >= 0.6
    number = str(prov.get("number") or doc.get("doc_number") or "").strip()
    if any(m in number.lower() for m in PLACEHOLDER) or not re.search(r"\d", number):
        notes.append(f"no number recorded ({number or 'blank'})")
    else:  # every integer of the recorded number appears in the text (so "No. 2 of 2022" matches "NO. 02 OF 2022")
        ints = {str(int(n)) for n in re.findall(r"\d+", number)}
        found = ints <= {str(int(n)) for n in re.findall(r"\d+", flat)}
        notes.append(f"number {number!r} {'found' if found else 'NOT found'}")
        ok &= found
    date = str(prov.get("printed_date") or doc.get("doc_date") or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        y, m, d = date.split("-")
        forms = [f"{int(d)}.{int(m)}.{y}", f"{d}.{m}.{y}", f"{d}/{m}/{y}", f"{int(d)}/{int(m)}/{y}", f"{d}-{m}-{y}",
                 y]  # the year alone is the weakest form; recorded as such
        found_form = next((f for f in forms if f in flat), None)
        notes.append(f"date {date} " + (f"found as '{found_form}'" if found_form else "NOT found"))
        ok &= found_form is not None
    return ok, "; ".join(notes)


def check(doc: dict[str, Any]) -> dict[str, Any]:
    did = doc["doc_id"]
    raw = next(iter(sorted((CORPUS_R3_DIR / "raw").glob(f"{did}.*"))), None)
    local = hashlib.sha256(raw.read_bytes()).hexdigest() if raw else ""
    text_file = CORPUS_R3_DIR / "text" / f"{did}.txt"
    text = text_file.read_text(encoding="utf-8") if text_file.exists() else ""
    prov_file = CORPUS_R3_DIR / str(doc.get("provenance_file") or f"provenance/{did}.provenance.json")
    prov = json.loads(prov_file.read_text(encoding="utf-8")) if prov_file.exists() else {}
    url = str(doc.get("retrieved_url") or prov.get("source_url") or "")
    got = fetch(url)
    expected = {doc["sha256"], str(prov.get("archive_sha256") or "")} - {""}
    return {"doc": doc, "prov": prov, "url": url, "text": text, "fetch": got,
            "sha256_ok": bool(local) and local == doc["sha256"],
            "remote_same_bytes": got.get("fetched_sha256") in expected}


def main() -> None:
    docs = json.loads((CORPUS_R3_DIR / "MANIFEST.json").read_text(encoding="utf-8"))["documents"]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(check, docs))
    rows, ver = [], []
    for r in results:
        d, f = r["doc"], r["fetch"]
        unverified = d.get("verification_status") == "UNVERIFIED"
        rows.append([d["doc_id"], r["url"] or "(none)", f.get("http_status"), f.get("content_type") or "-",
                     "Y" if r["sha256_ok"] else "N", "Y" if r["remote_same_bytes"] else "N", len(r["text"]),
                     language(r["text"]), d.get("verification_status") or "r2", "Y" if unverified else "N"])
        if not unverified:
            continue
        official, why_domain = domain_kind(r["url"], d)
        ident, why_ident = identity(d, r["prov"], r["text"])
        checks = {"official domain": official, "same bytes at the source now": r["remote_same_bytes"],
                  "saved file matches manifest": r["sha256_ok"], "title/number/date in text": ident}
        failed = [k for k, v in checks.items() if not v]
        ver.append([d["doc_id"], d.get("title") or "", d.get("issuer") or "", d.get("source_class") or "", r["url"],
                    f.get("http_status"), why_domain, "Y" if r["remote_same_bytes"] else "N", why_ident,
                    "AGENT_VERIFIED" if not failed else "NEEDS_HUMAN", "; ".join(failed)])
    fu_file = CORPUS_R3_DIR / "SOURCE_VERIFICATION_FOLLOWUP.csv"
    followup = {}
    if fu_file.exists():
        with open(fu_file, encoding="utf-8", newline="") as fh:
            followup = {r["doc_id"]: r for r in csv.DictReader(fh)}
    for v in ver:
        f = followup.get(v[0])
        v += [f["verdict"], f["official_url"], f["evidence"], f["for_human"]] if f else ["", "", "", ""]
        if f:
            v[9] = f["verdict"]
    with open(CORPUS_R3_DIR / "SOURCE_CHECK.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["doc_id", "url", "http_status", "content_type", "sha256_ok", "same_bytes_at_source", "text_chars",
                    "language", "verification_status", "needs_human"])
        w.writerows(rows)
    with open(CORPUS_R3_DIR / "SOURCE_VERIFICATION.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["doc_id", "title", "issuer", "source_class", "url", "http_status", "domain", "same_bytes_at_source",
                    "identity_in_text", "agent_verdict", "failed_checks", "followup_verdict", "followup_official_url",
                    "followup_evidence", "for_human"])
        w.writerows(ver)
    n = sum(v[9] == "AGENT_VERIFIED" for v in ver)
    print(f"SOURCE_CHECK: {len(rows)} documents; SOURCE_VERIFICATION: {len(ver)} UNVERIFIED -> {n} AGENT_VERIFIED, "
          f"{len(ver) - n} NEEDS_HUMAN")


if __name__ == "__main__":
    main()
