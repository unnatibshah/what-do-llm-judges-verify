"""Auditor for evaluating regulatory corpus text extraction, layout, and table fidelity."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from suryabench.corpus.manifest import load_manifest
from suryabench.paths import CORPUS_DIR, RESULTS_DIR

MANIFEST_PATH = CORPUS_DIR / "MANIFEST.json"
TEXT_DIR = CORPUS_DIR / "text"

# 20 Gold benchmark targets across all 4 themes
CRITICAL_REGULATORY_TARGETS: list[dict[str, str]] = [
    {"name": "PM_Surya_Ghar_Slab1", "term": "30,000", "doc_id": "IN-C1-001", "theme": "subsidy"},
    {"name": "PM_Surya_Ghar_Slab2", "term": "18,000", "doc_id": "IN-C1-001", "theme": "subsidy"},
    {"name": "PM_Surya_Ghar_Cap", "term": "78,000", "doc_id": "IN-C1-001", "theme": "subsidy"},
    {"name": "Phase2_Rate_Pre_Revision", "term": "14,588", "doc_id": "IN-C1-001", "theme": "subsidy"},
    {"name": "Phase2_Subsidy_Percentage", "term": "40%", "doc_id": "IN-C1-002", "theme": "subsidy"},
    {"name": "MERC_2019_DT_Cap", "term": "70%", "doc_id": "MH-C3-001", "theme": "capacity"},
    {"name": "MERC_2024_Virtual_NM", "term": "Virtual Net-Metering", "doc_id": "MH-C3-002", "theme": "capacity"},
    {"name": "MERC_2024_Deemed_10kW", "term": "upto 10 kW", "doc_id": "MH-C3-002", "theme": "timelines"},
    {"name": "CEA_Rules_2024_10kW", "term": "10 kW", "doc_id": "IN-C3-001", "theme": "timelines"},
    {"name": "CEA_Rules_2024_15_Days", "term": "fifteen days", "doc_id": "IN-C3-001", "theme": "timelines"},
    {"name": "RERC_2024_1MW", "term": "one megawatt", "doc_id": "RJ-C3-004", "theme": "capacity"},
    {"name": "RERC_2023_80_DT_Cap", "term": "80%", "doc_id": "RJ-C3-003", "theme": "capacity"},
    {"name": "RERC_2021_20_Days", "term": "twenty (20) days", "doc_id": "RJ-C3-002", "theme": "timelines"},
    {"name": "RERC_2024_15_Days", "term": "fifteen days", "doc_id": "RJ-C3-005", "theme": "timelines"},
    {"name": "JVVNL_NM_Rate", "term": "3.26", "doc_id": "RJ-C3-006", "theme": "tariff"},
    {"name": "ALMM_Efficiency_Rooftop", "term": "19.5", "doc_id": "IN-C2-004", "theme": "equipment"},
    {"name": "ALMM_Abeyance_2024", "term": "held in abeyance", "doc_id": "IN-C2-003", "theme": "equipment"},
    {"name": "ALMM_Effective_2024", "term": "1st April, 2024", "doc_id": "IN-C2-002", "theme": "equipment"},
    {"name": "ALMM_List_II", "term": "List-II", "doc_id": "IN-C2-006", "theme": "equipment"},
    {"name": "DCR_Verification", "term": "Domestic Content", "doc_id": "IN-C2-005", "theme": "equipment"},
]


@dataclass
class TargetAuditResult:
    """Audit result for an individual critical regulatory parameter."""

    name: str
    term: str
    doc_id: str
    theme: str
    found: bool
    context_snippet: str | None


@dataclass
class IngestionAuditReport:
    """Consolidated corpus ingestion quality and parameter recall report."""

    total_documents: int
    text_completeness_rate: float
    total_characters: int
    total_pages: int
    total_tables_extracted: int
    documents_with_tables: int
    ocr_documents_count: int
    parameter_recall_rate: float
    total_targets_tested: int
    targets_found_count: int
    target_results: list[TargetAuditResult]


def audit_corpus_ingestion(
    manifest_path: Path = MANIFEST_PATH,
    text_dir: Path = TEXT_DIR,
) -> IngestionAuditReport:
    """Execute complete ingestion accuracy audit across the active regulatory corpus."""
    manifest = load_manifest(manifest_path)
    total_docs = len(manifest.documents)

    total_chars = 0
    total_pages = 0
    total_tables = 0
    docs_with_tables = 0
    ocr_count = 0
    empty_docs = 0

    doc_texts: dict[str, str] = {}

    for doc in manifest.documents:
        txt_path = text_dir / f"{doc.doc_id}.txt"
        meta_path = text_dir / f"{doc.doc_id}.meta.json"

        if not txt_path.exists() or txt_path.stat().st_size == 0:
            empty_docs += 1
            doc_texts[doc.doc_id] = ""
            continue

        text = txt_path.read_text(encoding="utf-8")
        doc_texts[doc.doc_id] = text
        total_chars += len(text)

        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            total_pages += meta.get("page_count", 1)
            tbl_count = meta.get("tables_extracted", 0)
            if tbl_count > 0:
                total_tables += tbl_count
                docs_with_tables += 1
            if meta.get("text_layer") == "ocr":
                ocr_count += 1
        else:
            total_pages += 1

    # Audit critical regulatory parameters
    target_results: list[TargetAuditResult] = []
    found_count = 0

    for target in CRITICAL_REGULATORY_TARGETS:
        doc_id = target["doc_id"]
        term = target["term"]
        text = doc_texts.get(doc_id, "")

        found = term.lower() in text.lower()
        context_snippet = None

        if found:
            found_count += 1
            idx = text.lower().find(term.lower())
            start = max(0, idx - 40)
            end = min(len(text), idx + len(term) + 40)
            context_snippet = text[start:end].replace("\n", " ").strip()

        target_results.append(
            TargetAuditResult(
                name=target["name"],
                term=term,
                doc_id=doc_id,
                theme=target["theme"],
                found=found,
                context_snippet=context_snippet,
            )
        )

    completeness_rate = (total_docs - empty_docs) / total_docs if total_docs > 0 else 0.0
    recall_rate = (
        found_count / len(CRITICAL_REGULATORY_TARGETS) if CRITICAL_REGULATORY_TARGETS else 0.0
    )

    return IngestionAuditReport(
        total_documents=total_docs,
        text_completeness_rate=completeness_rate,
        total_characters=total_chars,
        total_pages=total_pages,
        total_tables_extracted=total_tables,
        documents_with_tables=docs_with_tables,
        ocr_documents_count=ocr_count,
        parameter_recall_rate=recall_rate,
        total_targets_tested=len(CRITICAL_REGULATORY_TARGETS),
        targets_found_count=found_count,
        target_results=target_results,
    )


def save_and_print_audit_report(report: IngestionAuditReport, out_path: Path) -> None:
    """Save report to JSON and print structured CLI table."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_dict = asdict(report)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report_dict, f, indent=2)

    print("=" * 70)
    print("SURYABENCH REGULATORY CORPUS INGESTION QUALITY REPORT")
    print("=" * 70)
    print(f"Total Corpus Documents:        {report.total_documents}")
    print(f"Text Completeness Rate:        {report.text_completeness_rate:.1%}")
    print(f"Total Characters Extracted:    {report.total_characters:,}")
    print(f"Total Document Pages:          {report.total_pages}")
    print(f"Structured Tables Extracted:   {report.total_tables_extracted}")
    print(f"Documents with Table Slabs:    {report.documents_with_tables}")
    print(f"OCR Fallback Documents:        {report.ocr_documents_count}")
    print(
        f"Critical Parameter Recall:     {report.parameter_recall_rate:.1%} ({report.targets_found_count}/{report.total_targets_tested})"
    )
    print("-" * 70)
    print("CRITICAL TARGET AUDIT BREAKDOWN:")
    for res in report.target_results:
        status_tag = "[PASS]" if res.found else "[FAIL]"
        print(f"  {status_tag} {res.name:<28} ({res.doc_id}): '{res.term}'")
        if res.context_snippet:
            print(f'         Context: "...{res.context_snippet}..."')
    print("=" * 70)


if __name__ == "__main__":
    report = audit_corpus_ingestion()
    save_and_print_audit_report(report, RESULTS_DIR / "ingestion_quality.json")
