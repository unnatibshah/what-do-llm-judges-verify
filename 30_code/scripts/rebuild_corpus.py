"""Replace the 38 script-generated corpus documents with authentic originals (2026-09-23).

Background: `30_code/scripts/ingest_corpus_expansion.py` (commit 36311db) wrote 38 documents from
inline text with `make_pdf()` and recorded them in MANIFEST.json as web retrievals. This
script removes them and ingests the authentic originals located by the retrieval audit
(`scratch/corpus_rebuild/<group>/report.json`), with metadata taken from each document
as actually published. Documents with no authentic original are excluded and logged.

Run once from the repository root after staged extraction has written
`scratch/corpus_rebuild/text/`. Idempotent for a given staging directory.
"""

import json
import shutil
from datetime import UTC, datetime

from suryabench.corpus.manifest import compute_file_sha256, load_manifest, save_manifest
from suryabench.corpus.schema import CorpusManifest, DocumentInventory, Jurisdiction
from suryabench.paths import CORPUS_DIR, ROOT

CORPUS = CORPUS_DIR
STAGE = ROOT / "scratch" / "corpus_rebuild"
GENERATED = json.loads((STAGE / "spec.json").read_text(encoding="utf-8"))  # the 38 generated entries
CORPUS_VERSION = "SuryaBench-Corpus-2026.11-r2"

# staged file -> final doc_id (None: not ingested)
STAGED = {
    **{f"central/{d}": d for d in [
        "IN-C1-003", "IN-C1-004", "IN-C1-005", "IN-C1-006", "IN-C1-007", "IN-C1-008", "IN-C1-009",
        "IN-C2-004", "IN-C2-005", "IN-C2-006", "IN-C3-003"]},
    "critical/IN-C2-002-reimposition": "IN-C2-002",
    "critical/IN-C2-003": "IN-C2-003",
    "critical/IN-C3-001": "IN-C3-001",
    "critical/IN-C3-002": "IN-C3-002",
    "critical/RJ-C3-004": "RJ-C3-004",
    "critical/RJ-C5-005-substitute": "RJ-C5-005",
    **{f"mh/{d}": d for d in [
        "MH-C3-003", "MH-C3-004", "MH-C3-005", "MH-C5-006", "MH-C5-008", "MH-C5-010", "MH-C5-011", "MH-C5-012"]},
    **{f"rj/{d}": d for d in ["RJ-C3-005", "RJ-C3-006", "RJ-C5-001", "RJ-C5-002", "RJ-C5-003", "RJ-C5-004"]},
}
EXCLUDED = {
    "MH-C5-007": "Claimed 3-working-day deemed sanction rule not stated in any authentic document; the real "
                 "MSEDCL Commercial Circular 342 (10.07.2023) is an unrelated tariff corrigendum.",
    "MH-C5-009": "No authentic circular revising the MSEDCL DT limit to 85% exists; the real Circular 338 is on "
                 "industrial tariff concessions.",
    "MH-C5-013": "No authentic circular found; the consumption-linked cap is a portal change without a circular.",
    "MH-C6-002": "No such MEDA guideline exists; PM Surya Ghar vendor registration is done by MSEDCL.",
    "RJ-C3-007": "No RERC 2021 APPC/banking order exists.",
    "RJ-C6-001": "RRECL issued no residential rooftop guideline (63-entry order index checked).",
    "RJ-C5-006": "Claimed JVVNL circular not found; the rule it asserted is authentically stated by RERC "
                 "Regulation No. 154 (2024), ingested as RJ-C3-005.",
}
ISSUER_DISCOM = {"MSEDCL": "MSEDCL", "JVVNL": "JVVNL", "Jaipur": "JVVNL", "JdVVNL": "JdVVNL", "Jodhpur": "JdVVNL"}


def reports() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for group in ("critical", "central", "mh", "rj"):
        data = json.loads((STAGE / group / "report.json").read_text(encoding="utf-8"))
        for r in data if isinstance(data, list) else data.get("documents", []):
            out[f"{group}/{r['doc_id']}"] = r
    return out


def _date(s: str | None, fallback: str) -> str:
    s = (s or "").strip()[:10]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return fallback


def _layer(r: dict, meta: dict) -> str:
    text = str(r.get("text_layer") or meta.get("text_layer") or "native").lower()
    return "ocr" if "ocr" in text or "scan" in text else "native"


def _status(r: dict) -> str:
    s = str(r.get("status_guess") or "").lower()
    return "presumed_superseded" if s.startswith("presumed_superseded") else "presumed_current"


def main() -> None:
    manifest = load_manifest(CORPUS / "MANIFEST.json")
    kept = {d.doc_id: d for d in manifest.documents if d.doc_id not in {g["doc_id"] for g in GENERATED}}
    old = {d.doc_id: d for d in manifest.documents}
    rep = reports()

    # 1. Remove every generated document (raw + text + meta).
    for g in GENERATED:
        for p in (CORPUS / "raw" / f"{g['doc_id']}.pdf", CORPUS / "text" / f"{g['doc_id']}.txt",
                  CORPUS / "text" / f"{g['doc_id']}.meta.json"):
            if p.exists() and g["doc_id"] != "IN-C2-002":
                p.unlink()

    # 2. The authentic file previously filed as IN-C2-002 is the 06.05.2025 OM: re-file as IN-C2-007.
    if (CORPUS / "raw" / "IN-C2-002.pdf").exists():
        for ext in (".pdf",):
            shutil.move(CORPUS / "raw" / f"IN-C2-002{ext}", CORPUS / "raw" / f"IN-C2-007{ext}")
        for ext in (".txt", ".meta.json"):
            src = CORPUS / "text" / f"IN-C2-002{ext}"
            if src.exists():
                shutil.move(src, CORPUS / "text" / f"IN-C2-007{ext}")
    raw7 = CORPUS / "raw" / "IN-C2-007.pdf"
    o = old["IN-C2-002"]
    kept["IN-C2-007"] = DocumentInventory.model_validate({
        **o.model_dump(by_alias=True),
        "doc_id": "IN-C2-007",
        "title": "Amendment to ALMM Order regarding reduction of module efficiency thresholds for off-grid "
                 "projects/applications requiring individual module capacity of less than 200 Wp",
        "doc_number": "32/33/2024-SPV Division",
        "doc_date": "2025-05-06", "effective_date": "2025-05-06",
        "retrieved_url": None, "sha256": compute_file_sha256(raw7),
        "notes": "Authentic MNRE OM previously mis-catalogued as IN-C2-002 (ALMM re-imposition, 2024) with an "
                 "invented URL; metadata corrected from the document itself. Original retrieval URL not recorded.",
    })

    # 3. Ingest the authentic originals.
    for staged, doc_id in STAGED.items():
        group, name = staged.split("/")
        r = rep[f"{group}/{name.replace('-substitute', '').replace('-reimposition', '')}"]
        src_pdf = STAGE / group / f"{name}.pdf"
        dst_pdf = CORPUS / "raw" / f"{doc_id}.pdf"
        shutil.copyfile(src_pdf, dst_pdf)
        meta_src = STAGE / "text" / f"{name}.meta.json"
        meta = json.loads(meta_src.read_text(encoding="utf-8")) if meta_src.exists() else {}
        shutil.copyfile(STAGE / "text" / f"{name}.txt", CORPUS / "text" / f"{doc_id}.txt")
        if meta:
            meta["doc_id"] = doc_id
            (CORPUS / "text" / f"{doc_id}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8", newline="\n")
        claimed = next(g for g in GENERATED if g["doc_id"] == doc_id)
        prefix = doc_id[:2]
        issuer = r.get("actual_issuer") or claimed["issuer"]
        is_state = prefix in {"MH", "RJ"}
        discom = next((v for k, v in ISSUER_DISCOM.items() if k in issuer), None) if doc_id[3:5] == "C5" else None
        doc_date = _date(r.get("actual_doc_date"), claimed["doc_date"])
        via = str(r.get("retrieved_via") or "web_search")
        via = via if via in {"nav", "site_search", "web_search", "linked", "orphan"} else "web_search"
        kept[doc_id] = DocumentInventory.model_validate({
            "doc_id": doc_id,
            "title": r.get("actual_title") or claimed["title"],
            "class": doc_id[3:5],
            "issuer": issuer,
            "jurisdiction": Jurisdiction(level="state" if is_state else "central", code=prefix, discom=discom),
            "doc_number": r.get("actual_doc_number"),
            "doc_date": doc_date,
            "effective_date": _date(r.get("effective_date"), doc_date),
            "effective_date_basis": "E1",
            "effective_date_confidence": "high" if r.get("effective_date") else "medium",
            "retrieved_url": r.get("source_url"),
            "retrieved_via": via,
            "retrieved_at": datetime.fromtimestamp(src_pdf.stat().st_mtime, UTC).isoformat(),
            "sha256": compute_file_sha256(dst_pdf),
            "pages": int(r.get("pages") or meta.get("page_count") or 1),
            "text_layer": _layer(r, meta),
            "status": _status(r),
            "discoverability": via,
            "notes": (f"Authentic original ({r.get('outcome')}) replacing a script-generated placeholder "
                      f"(commit 36311db). {str(r.get('notes') or '')[:600]}").strip(),
        })

    docs = sorted(kept.values(), key=lambda d: d.doc_id)
    save_manifest(CorpusManifest(corpus_version=CORPUS_VERSION, created_at=datetime.now(UTC).isoformat(),
                                 documents=docs), CORPUS / "MANIFEST.json")
    (STAGE / "excluded.json").write_text(json.dumps(EXCLUDED, indent=2), encoding="utf-8", newline="\n")
    by = {p: sum(d.doc_id.startswith(p) for d in docs) for p in ("IN", "MH", "RJ")}
    print(f"corpus: {len(docs)} documents {by}; excluded {len(EXCLUDED)}")


if __name__ == "__main__":
    main()
