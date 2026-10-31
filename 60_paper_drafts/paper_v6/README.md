# paper_v6 (review version after v5r, 2026-10-30): "What Do LLM Judges Actually Verify? Matched Controls and Record Gaps for Document Currency"

For *Artificial Intelligence and Law* (Springer Nature `sn-jnl`, double-anonymous). Scope: `00_tracking/final/FINAL-RESEARCH-LOCK.md`
(v2, D52). paper_v5 is kept unchanged; the revision's diagnosis, change log, issue register, verified claims and reviewer reports are in
`80_review/REVISION-2026-10-30/`.

**Status: submission version (2026-10-30).** All runs complete; no placeholder or draft banner prints in the authored
builds. arXiv source: `70_papers/arxiv/surya_arxiv_src.tar.gz` (`30_code/scripts/make_arxiv.py`). Public release
(cited in the paper): https://github.com/unnatibshah/what-do-llm-judges-verify, a snapshot of this repository's
harness, data, replies and paper with a provenance file of commit times. The anonymous build still needs an anonymised
mirror URL (`\anonurl`) for a double-anonymous venue.

## Build

    source .venv/bin/activate
    PYTHONPATH=30_code/src python 30_code/scripts/analyse_final_e123.py --tex 60_paper_drafts/paper_v6/generated  # final runs
    PYTHONPATH=30_code/src python -m suryabench.evalkit --tex 60_paper_drafts/paper_v6/generated                   # pilot
    cd 60_paper_drafts/paper_v6 && for f in main main_2col main_anon; do tectonic -X compile $f.tex; done

- `main.tex`: single column, with authors.
- `main_2col.tex`: the same body in the journal's two-column layout (`iicol`), with authors, tables and figures full width.
- `main_anon.tex`: single column, anonymised. **Upload this one for review** (AI and Law is double-anonymous); names,
  affiliations and the email go on the separate title page in the submission system.

Both share `preamble.tex` and `body.tex`. Every number is a macro: `generated/numbers_e123.tex` (final runs),
`generated/numbers_rfc.tex` (pilot), `numbers.tex` (case study; paper_v3 outputs). The case-study files
(`appendix_study1*.tex`, `case_setting.tex`) are carried over from paper_v4 unchanged.
