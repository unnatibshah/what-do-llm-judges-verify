"""Unit tests for corpus ingestion accuracy, table preservation, and parameter recall."""

from suryabench.corpus.eval_ingestion import audit_corpus_ingestion


def test_audit_corpus_ingestion_accuracy() -> None:
    """The authentic corpus (46 documents) has full text coverage and recalls every audited parameter."""
    report = audit_corpus_ingestion()

    assert report.total_documents >= 30
    assert report.text_completeness_rate == 1.0  # Zero empty documents
    assert report.total_tables_extracted >= 5  # Tables extracted into Markdown
    assert report.parameter_recall_rate >= 0.95  # At least 95% of critical regulatory figures found
    assert report.targets_found_count == report.total_targets_tested  # 20 / 20 targets found
