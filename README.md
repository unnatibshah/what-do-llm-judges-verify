# What Do LLM Judges Actually Verify? Matched Controls and Record Gaps for Document Currency

Code, data and every model reply for the paper by Unnati Shah (University of Southern California), Samruddhi Kakade
(Illinois Institute of Technology) and Aum Patel (New York University). The paper's source and PDF are in
`60_paper_drafts/paper_v6/`.

The test turns a table of document replacements into matched answers (a fault citing a replaced document; a control
citing its successor; a date control citing the replaced document before its replacement; a decoy citing an older
document that a newer one updated without replacing), removes links from the amendment record, and scores each judge
finding by its stated reason. Applied to 48 replacements from the IETF RFC index with four LLM judges.

## Layout

| Path | Contents |
|---|---|
| `30_code/src/suryabench/evalkit.py` | The harness: items, contexts, prompts, scoring |
| `30_code/scripts/run_evalkit.py`, `30_code/scripts/kaggle/` | Running a judge (locally or through the Kaggle Benchmarks proxy) |
| `30_code/scripts/analyse_final_e123.py` | Rescoring check, H1/H2a/H2b, Holm, damage seed 1, every number and table of the results |
| `40_data/corpus_staging/rfc/` | RFC Editor index used (with its SHA-256) |
| `50_analysis/results/evalkit_rfc_v2/` | Final replies: `<judge>/<context>.json`, one row per item with raw reply and score; `analysis/` |
| `50_analysis/results/evalkit_rfc_v2_seed1/` | Second draw of removed links (damage seed 1) |
| `50_analysis/results/evalkit_rfc/` | Pilot replies |
| `00_tracking/final/FINAL-EXECUTION-PLAN.md` | Hypotheses, tests and amendments; `PROVENANCE.md` gives when each was committed |
| `40_data/benchmark/`, `registries/`, `link_audit_v1/`, `corpus_r3/` (manifest, graph, provenance), `20_method/`, other `50_analysis/results/` folders | Case study (Indian rooftop-solar rules), reported descriptively in the appendices; documents as URLs and hashes |
| `50_analysis/RESULTS-OF-RECORD.md`, `REPRODUCE.md` | Which file every number comes from; commands |

## Reproduce the numbers (no model calls)

    python3 -m venv .venv && . .venv/bin/activate && pip install -e .     # Python >= 3.11
    PYTHONPATH=30_code/src python 30_code/scripts/analyse_final_e123.py --tex 60_paper_drafts/paper_v6/generated
    cd 60_paper_drafts/paper_v6 && tectonic -X compile main.tex

The analysis rescores every stored reply from its raw text and stops if any stored score differs; its outputs
reproduce byte for byte. The pilot and the case study are regenerated with the commands in
`50_analysis/REPRODUCE.md`, which also notes the one known difference (two empty rows in two pilot tables).
`50_analysis/RESULTS-OF-RECORD.md` maps every number to its file; `PROVENANCE.md` records when the plan and each
block of results were committed in the (private) development repository and what was changed for this release.

Tests: `pip install pytest && python -m pytest -q 30_code/tests/unit/test_evalkit.py`. The other tests cover the
case-study pipeline and need files not included here.

## Licences

Code: Apache-2.0 (`LICENSE`). Data: see `LICENSE-DATA.md` (case-study cases, labels, annotation sheets, graph and
record under CC BY 4.0; government documents listed by URL and hash, not redistributed; the RFC index included
unchanged as a third-party file).
