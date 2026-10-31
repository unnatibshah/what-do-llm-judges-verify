# paper_v6 (review version after v5r, 2026-10-30; editorial pass 2026-10-31): "What Do LLM Judges Actually Verify? Matched Controls and Record Gaps for Document Currency"

For *Artificial Intelligence and Law* (Springer Nature `sn-jnl`, double-anonymous). Scope: `00_tracking/final/FINAL-RESEARCH-LOCK.md`
(v2, D52). paper_v5 is kept unchanged; the revision's diagnosis, change log, issue register, verified claims and reviewer reports are in
`80_review/REVISION-2026-10-30/`; the editorial pass of 2026-10-31 (assessment, removal report, change report, AI-disclosure
recommendation, unresolved concerns) is `80_review/EDITORIAL-PASS-2026-10-31.md`.

**Status: submission version (2026-10-31).** All runs complete; no placeholder or draft banner prints in the authored
builds. arXiv source: `70_papers/arxiv/surya_arxiv_src.tar.gz` (`30_code/scripts/make_arxiv.py`). Public release
(cited in the paper): https://github.com/unnatibshah/what-do-llm-judges-verify, a snapshot of this repository's
harness, data, replies and paper with a provenance file of commit times. The anonymous build still needs an anonymised
mirror URL (`\anonurl`) for a double-anonymous venue.

## Build

    source .venv/bin/activate
    PYTHONPATH=30_code/src python 30_code/scripts/analyse_final_e123.py --tex 60_paper_drafts/paper_v6/generated  # final runs
    PYTHONPATH=30_code/src python -m suryabench.evalkit --tex 60_paper_drafts/paper_v6/generated                   # pilot
    cd 60_paper_drafts/paper_v6 && for f in main main_2col main_anon main_full supplement supplement_anon; do tectonic -X compile $f.tex; done

- `main.tex`: single column, with authors, preprint layout (A4, 1-inch margins via `\wideformat`; 22 pp.). The case study's full report is not in it; its summary is Appendix D.
- `main_2col.tex`: the same body in the journal's two-column layout (`iicol`), with authors, tables and figures full width.
- `main_anon.tex`: single column, anonymised, in the journal's own layout (131 mm text block). **Upload this one for review** (AI and Law is double-anonymous); names,
  affiliations and the email go on the separate title page in the submission system.
- `supplement.tex` / `supplement_anon.tex`: the supplementary material, the case study in full (`sections/supplement_body.tex`:
  `appendix_study1.tex` and `appendix_study1_extra.tex`, sections S1–S7). Upload the anonymised one with `main_anon.pdf`.
- `main_full.tex`: `main.tex` with the supplementary material appended after the references, one PDF (35 pp., preprint layout), for arXiv or
  for anyone who wants everything in one file. `make_arxiv.py` still packages `main.tex`; pointing it at `main_full.tex` is an
  author decision (see the editorial-pass report).

All share `preamble.tex` (which also holds the authors row, `\authorsrow`) and `body.tex`. Every number is a macro:
`generated/numbers_e123.tex` (final runs), `generated/numbers_rfc.tex` (pilot), `numbers.tex` (case study; paper_v3
outputs). The case-study files (`appendix_study1*.tex`, `case_setting.tex`) are carried over from paper_v4 unchanged except
for cross-references between the paper and the supplement.
