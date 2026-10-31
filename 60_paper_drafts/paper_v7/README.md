# paper_v7 (arXiv version, 2026-10-31): "What Do LLM Judges Actually Verify? Matched Controls and Record Gaps for Document Currency"

paper_v6 after the co-author review loop of 2026-10-31 (Samruddhi Kakade): four rounds of three-lens review and fixes,
then a final review on a different model, all in `80_review/SAMRUDDHI-REVIEW-2026-10-31/` (`README.md` lists each round,
`LEDGER.md` the settled items). The author line is "Samruddhi Sanjaykumar Kakade, Independent Researcher". No number
changed; the generated number files are the same as paper_v6's, which is kept unchanged as the lead author left it.

**Status: arXiv version.** arXiv source: `70_papers/arxiv/paper_v7/surya_arxiv_src.tar.gz`, built with
`PYTHONPATH=30_code/src python 30_code/scripts/make_arxiv.py --paper paper_v7`; the upload sheet is
`70_papers/arxiv/paper_v7/ARXIV-SUBMISSION.md`. Public release (cited in the paper):
https://github.com/unnatibshah/what-do-llm-judges-verify; it still holds the paper_v6 text and the old author line and
needs a resync before the upload. The anonymous build still needs an anonymised mirror URL (`nonurl`) for a
double-anonymous venue.

## Build

    source .venv/bin/activate
    PYTHONPATH=30_code/src python 30_code/scripts/analyse_final_e123.py --tex 60_paper_drafts/paper_v7/generated  # final runs
    PYTHONPATH=30_code/src python -m suryabench.evalkit --tex 60_paper_drafts/paper_v7/generated                   # pilot
    cd 60_paper_drafts/paper_v7 && for f in main main_2col main_anon main_full supplement supplement_anon; do tectonic -X compile $f.tex; done

- `main.tex`: single column, with authors, preprint layout (A4, 1-inch margins via `\wideformat`; 23 pp.). The case study's full report is not in it; its summary is Appendix D.
- `main_2col.tex`: the same body in the journal's two-column layout (`iicol`), with authors, tables and figures full width.
- `main_anon.tex`: single column, anonymised, in the journal's own layout (131 mm text block). **Upload this one for review** (AI and Law is double-anonymous); names,
  affiliations and the email go on the separate title page in the submission system.
- `supplement.tex` / `supplement_anon.tex`: the supplementary material, the case study in full (`sections/supplement_body.tex`:
  `appendix_study1.tex` and `appendix_study1_extra.tex`, sections S1–S7). Upload the anonymised one with `main_anon.pdf`.
- `main_full.tex`: `main.tex` with the supplementary material appended after the references, one PDF (36 pp., preprint layout), for arXiv or
  for anyone who wants everything in one file. `make_arxiv.py` packages `main.tex` with `\withsupplement` defined, which gives this
  same PDF (author decision register, item 14).

All share `preamble.tex` (which also holds the authors row, `\authorsrow`) and `body.tex`. Figures 2 and 3 are drawn from the number macros by `30_code/scripts/make_figures_v6.py` (it writes into `paper_v6/generated/`; copy the two figures here after a rerun); Figure 1 is TikZ (`sections/fig_design.tex`). Every number is a macro:
`generated/numbers_e123.tex` (final runs), `generated/numbers_rfc.tex` (pilot), `numbers.tex` (case study; paper_v3
outputs). The case-study files (`appendix_study1*.tex`, `case_setting.tex`) are carried over from paper_v4 unchanged except
for cross-references between the paper and the supplement.
