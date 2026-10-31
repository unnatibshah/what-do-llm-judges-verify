"""Build the staging corpus SuryaBench-Corpus-2026.10-r3 (D19, D23) in 40_data/corpus_r3/.

r3 = the frozen r2 corpus (40_data/corpus/, read only, copied unchanged) + the staged candidate
documents in 40_data/corpus_staging/{GJ,KA,TN,DL,UP,IN}/. Same layout and schemas as r2: raw/,
text/ (extracted with suryabench.corpus.extract), provenance/, MANIFEST.json + MANIFEST.sha256,
graph/supersession.json.

Rules applied here:
- Every new document carries verification_status "UNVERIFIED", its source_class (D23: copies of
  regulator or central documents hosted on a DISCOM portal are "discom_copy") and its provenance file.
- Draft instruments are included as distractors with status "draft_not_in_force"; no supersession
  edge is drawn from a draft.
- Doc ids follow r2: <JUR>-C<class>-<nnn>, numbered within jurisdiction and class (r2 numbering is
  acquisition order; r3 continues each sequence after the r2 maximum, chronologically, undated last).
- Graph nodes are verbatim snippets: the staged candidate_clauses, the predecessor quotes recorded in
  their amends_or_supersedes evidence, and a short list of extra decisive clauses quoted by this
  script (EXTRA_NODES). Every snippet is matched against the r3 text (quote_check). Every new node and
  edge is "UNVERIFIED".
- No LLM is called: machine translation is switched off (SURYABENCH_TRANSLATE=0) and blocked.
  Scanned PDFs for which staging holds a macOS Vision OCR file (*.ocr.txt) are extracted from that
  file through the same extraction code (text_layer ocr); other scans go through the code's own OCR.

Usage (from the repository root): PYTHONPATH=30_code/src python 30_code/scripts/build_corpus_r3.py
Re-running reuses text already extracted from an unchanged raw file.
"""

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ["SURYABENCH_TRANSLATE"] = "0"

import pypdf  # noqa: E402

from suryabench.core.enums import TextLayer  # noqa: E402
from suryabench.corpus import extract as _extract  # noqa: E402
from suryabench.corpus.manifest import (  # noqa: E402
    compute_file_sha256,
    load_manifest,
    save_manifest,
)
from suryabench.corpus.schema import CorpusManifest, DocumentInventory  # noqa: E402
from suryabench.graph.oracle import validate_graph  # noqa: E402
from suryabench.graph.schema import SupersessionGraph  # noqa: E402
from suryabench.paths import CORPUS_DIR, CORPUS_R3_DIR, CORPUS_STAGING_DIR  # noqa: E402

CORPUS_VERSION = "SuryaBench-Corpus-2026.10-r3"
SNAPSHOT = "2026-10-01"
UNVERIFIED = "UNVERIFIED"


def _no_translate(text: str, *args: Any, **kwargs: Any) -> str:
    raise RuntimeError("machine translation is disabled for corpus r3 (no LLM calls)")


_extract.translate_text_to_english = _no_translate  # type: ignore[assignment]

# --------------------------------------------------------------------------------------------
# Documents: staged stem -> metadata. (doc_id, class, jurisdiction code, discom, issuer,
# doc_date, effective_date, basis, confidence, status, source_class, note)
# --------------------------------------------------------------------------------------------
GERC, KERC, BESCOM = ("Gujarat Electricity Regulatory Commission (GERC)",
                      "Karnataka Electricity Regulatory Commission (KERC)", "BESCOM")
DERC, UPERC, MNRE = ("Delhi Electricity Regulatory Commission (DERC)",
                     "Uttar Pradesh Electricity Regulatory Commission (UPERC)",
                     "Ministry of New and Renewable Energy (MNRE)")
TANGEDCO = "TANGEDCO (Tamil Nadu Generation and Distribution Corporation)"
D = tuple[str, str, str, str | None, str, str, str, str, str, str, str, str]
DOCS: dict[str, D] = {
    # --- Gujarat (gercin.org) --------------------------------------------------------------
    "GJ/GERC-NetMetering-2016-Reg": ("GJ-C3-001", "C3", "GJ", None, GERC, "2016-06-17", "2016-06-17", "E5",
                                     "medium", "presumed_current", "regulator_original",
                                     "Principal regulations, amended 2017, 2020, 2022, 2024, 2025; date from the landing page."),
    "GJ/GERC-NetMetering-2017-1stAmend": ("GJ-C3-002", "C3", "GJ", None, GERC, "2017-10-06", "2017-10-06", "E4",
                                          "medium", "presumed_current", "regulator_original", "Gazette date."),
    "GJ/GERC-NetMetering-2020-2ndAmend": ("GJ-C3-003", "C3", "GJ", None, GERC, "2020-01-22", "2020-01-22", "E5",
                                          "medium", "presumed_current", "regulator_original",
                                          "The extracted text prints no date; date from the landing page."),
    "GJ/GERC-NetMetering-2022-3rdAmend": ("GJ-C3-004", "C3", "GJ", None, GERC, "2022-05-31", "2022-05-31", "E5",
                                          "medium", "presumed_current", "regulator_original", "Date from the landing page."),
    "GJ/GERC-NetMetering-2024-4thAmend": ("GJ-C3-005", "C3", "GJ", None, GERC, "2024-09-06", "2024-09-06", "E4",
                                          "medium", "presumed_current", "regulator_original",
                                          "Gazette Extra No. 98 dated 06-09-2024; signed 04/09/2024."),
    "GJ/GERC-NetMetering-2025-5thAmend-DRAFT": ("GJ-C3-006", "C3", "GJ", None, GERC, "2025-10-14", "UNKNOWN", "E9",
                                                "low", "draft_not_in_force", "regulator_original",
                                                "DRAFT Fifth Amendment; distractor, not in force."),
    "GJ/GERC-NetMetering-2025-5thAmend": ("GJ-C3-007", "C3", "GJ", None, GERC, "2025-11-03", "2025-11-03", "E4",
                                          "medium", "presumed_current", "regulator_original", "Gazette Extra No. 328."),
    "GJ/GERC-DRE-2026-Draft": ("GJ-C3-008", "C3", "GJ", None, GERC, "2026-05-15", "UNKNOWN", "E9", "low",
                               "draft_not_in_force", "regulator_original",
                               "DRAFT Grid Interactive DRES Regulations 2026 (would repeal the 2016 regulations); "
                               "distractor, not in force."),
    "GJ/GERC-NetMetering-2020-2ndAmend-SoR": ("GJ-C4-001", "C4", "GJ", None, GERC, "2020-01-22", "2020-01-22", "E5",
                                              "low", "context", "regulator_original", "Statement of Reasons; context only."),
    "GJ/GERC-NetMetering-2022-3rdAmend-SoR": ("GJ-C4-002", "C4", "GJ", None, GERC, "2022-05-31", "2022-05-31", "E5",
                                              "low", "context", "regulator_original", "Statement of Reasons; context only."),
    "GJ/GERC-NetMetering-2024-4thAmend-SoR": ("GJ-C4-003", "C4", "GJ", None, GERC, "2024-09-04", "2024-09-04", "E5",
                                              "low", "context", "regulator_original", "Statement of Reasons; context only."),
    "GJ/GERC-NetMetering-2025-5thAmend-SoR": ("GJ-C4-004", "C4", "GJ", None, GERC, "2025-11-04", "2025-11-04", "E5",
                                              "low", "context", "regulator_original", "Statement of Reasons; context only."),
    # --- Karnataka (all from srtpv.bescom.org; KERC hosts unreachable) ----------------------
    "KA/KERC-SRTPV-tariff-order-2023-06-01": ("KA-C3-001", "C3", "KA", None, KERC, "2023-06-01", "2023-06-01", "E1",
                                              "medium", "presumed_current", "discom_copy",
                                              "KERC tariff order that substitutes Reg 6(a),(e),(f),(g) of the 2016 SRTPV "
                                              "Regulations; BESCOM-hosted copy, verify against the KERC original (D23)."),
    "KA/KERC-tariff-order-2024-06-11": ("KA-C3-002", "C3", "KA", None, KERC, "2024-06-11", "2024-06-11", "E6", "low",
                                        "presumed_current", "discom_copy", "Scan; BESCOM-hosted copy (D23)."),
    "KA/KERC-DSPV-Regulations-2026": ("KA-C3-003", "C3", "KA", None, KERC, "2026-08-19", "2026-08-19", "E6", "low",
                                      "presumed_current", "discom_copy",
                                      "KERC DSPV Regulations 2026 (repeal the 2016 regulations from coming into force); "
                                      "Gazette date partly illegible, notification date used as the lower bound of the "
                                      "effective date. BESCOM-hosted Gazette copy (D23)."),
    "KA/KERC-tariff-order-2026-08-25": ("KA-C3-004", "C3", "KA", None, KERC, "2026-08-25", "2026-08-25", "E6", "low",
                                        "context", "discom_copy", "Tariff order; context only. BESCOM-hosted copy (D23)."),
    "KA/KERC-order-2024-12-05": ("KA-C4-001", "C4", "KA", None, KERC, "2024-12-05", "2024-12-05", "E1", "medium",
                                 "presumed_current", "discom_copy",
                                 "Order under Reg 13 (removal of difficulties); BESCOM-hosted copy (D23)."),
    "KA/BESCOM-SRTPV-Guidelines-2023-08-05": ("KA-C5-001", "C5", "KA", "BESCOM", BESCOM, "2023-08-05", "2023-08-05",
                                              "E1", "medium", "presumed_superseded", "discom_original",
                                              "BESCOM/BC-51/2023-24/1317."),
    "KA/BESCOM-SRTPV-1-10kW-domestic-procedure": ("KA-C5-002", "C5", "KA", "BESCOM", BESCOM, "UNKNOWN", "UNKNOWN",
                                                  "E9", "low", "unknown", "discom_original", "Undated procedure sheet."),
    "KA/BESCOM-SRTPV-1-500kW-procedure": ("KA-C5-003", "C5", "KA", "BESCOM", BESCOM, "UNKNOWN", "UNKNOWN", "E9", "low",
                                          "unknown", "discom_original", "Undated procedure sheet."),
    "KA/BESCOM-SRTPV-500-1000kW-procedure": ("KA-C5-004", "C5", "KA", "BESCOM", BESCOM, "UNKNOWN", "UNKNOWN", "E9",
                                             "low", "unknown", "discom_original", "Undated procedure sheet."),
    "KA/BESCOM-SRTPV-1000-2000kW-procedure": ("KA-C5-005", "C5", "KA", "BESCOM", BESCOM, "UNKNOWN", "UNKNOWN", "E9",
                                              "low", "unknown", "discom_original", "Undated procedure sheet."),
    "KA/BESCOM-SRTPV-Common-SOP-DSPV": ("KA-C5-006", "C5", "KA", "BESCOM", BESCOM, "2025-12-01", "2025-12-01", "E1",
                                        "medium", "presumed_current", "discom_original",
                                        "BESCOM/BC-51/GM(DSM)/DSPV/SOP/CYS-48. DISCOM-level authority (A6)."),
    "KA/KERC-Common-SOP-VNM-GNM-2026-05-12": ("KA-C5-007", "C5", "KA", "BESCOM", BESCOM, "2026-05-12", "2026-05-12",
                                              "E1", "medium", "presumed_current", "discom_original",
                                              "BESCOM/BC-51/2026-27/CYS-22 common SOP for VNM/GNM; context."),
    "KA/BESCOM-Processing-DSPV-applications-2026-07-01": ("KA-C5-008", "C5", "KA", "BESCOM", BESCOM, "2026-07-01",
                                                          "2026-07-01", "E6", "low", "unknown", "discom_original",
                                                          "Scan; date from the portal label."),
    "KA/BESCOM-circular-2026-07-24": ("KA-C5-009", "C5", "KA", "BESCOM", BESCOM, "2026-07-24", "2026-07-24", "E6",
                                      "low", "unknown", "discom_original", "Scan; date from the portal label."),
    "KA/BESCOM-SRTPV-tariff-OM": ("KA-C5-010", "C5", "KA", "BESCOM", BESCOM, "UNKNOWN", "UNKNOWN", "E9", "low",
                                  "unknown", "discom_original", "Scan, undated."),
    "KA/BESCOM-SRTPV-simplified-notification": ("IN-C1-010", "C1", "IN", None, MNRE, "2022-06-10", "2022-06-10", "E1",
                                                "medium", "presumed_current", "discom_copy",
                                                "MNRE OM F. No. 318/6/2022-GCRT (simplification of procedure, RTS Ph-II); "
                                                "BESCOM-hosted copy (D23)."),
    # --- Tamil Nadu (TANGEDCO memos summarising TNERC orders; TNERC hosts unreachable) ------
    "TN/TANGEDCO-test1-soi-100519": ("TN-C5-001", "C5", "TN", "TANGEDCO", TANGEDCO, "2019-05-10", "2019-05-10", "E1",
                                     "medium", "presumed_superseded", "discom_copy",
                                     "TANGEDCO memo implementing TNERC Order 3/2019 (25.03.2019); DISCOM summary of a "
                                     "regulator order hosted on tnebnet.org: verify against the TNERC order (D23)."),
    "TN/TNEBLTD-usrp-Salientfeatures": ("TN-C5-002", "C5", "TN", "TANGEDCO", TANGEDCO, "UNKNOWN", "2021-10-22", "E1",
                                        "medium", "presumed_current", "discom_copy",
                                        "TANGEDCO salient features of TNERC Order 8/2021 (22-10-2021); memo undated; "
                                        "verify against the TNERC order (D23)."),
    "TN/TNEBLTD-usrp-policiesadopted": ("TN-C5-003", "C5", "TN", "TANGEDCO", TANGEDCO, "UNKNOWN", "UNKNOWN", "E9",
                                        "low", "context", "discom_copy", "Context only."),
    "TN/TNEBLTD-usrp-pmsolarfreescheme22022024": ("TN-C5-004", "C5", "TN", "TANGEDCO", TANGEDCO, "2024-02-22",
                                                  "2024-02-22", "E6", "low", "context", "discom_copy",
                                                  "Tamil notice; legacy-font text extracts as garbage."),
    "TN/TNEBLTD-usrp-solargo": ("TN-C5-005", "C5", "TN", "TANGEDCO", TANGEDCO, "UNKNOWN", "UNKNOWN", "E9", "low",
                                "unknown", "discom_copy", "Scan (scheme G.O. per portal label); class provisional."),
    # --- Delhi (derc.gov.in; one Govt of NCT Delhi SWS copy) --------------------------------
    "DL/DL-NM-2014-regs": ("DL-C3-001", "C3", "DL", None, DERC, "UNKNOWN", "UNKNOWN", "E9", "low", "presumed_current",
                           "regulator_original", "Notification date blank in the printed text; DERC listing says 2014."),
    "DL/DL-NM-2014-regs-and-guidelines-sws": ("DL-C3-002", "C3", "DL", None, DERC, "UNKNOWN", "UNKNOWN", "E9", "low",
                                              "presumed_current", "government_mirror",
                                              "NM Regulations 2014 with the Guidelines bound in, from sws.delhi.gov.in; "
                                              "check against the DERC gazette text."),
    "DL/DL-SC-2017-supply-code": ("DL-C3-003", "C3", "DL", None, DERC, "2017-07-07", "2017-07-07", "E6", "medium",
                                  "presumed_current", "regulator_original", "Context."),
    "DL/DL-GNMVNM-2019-guidelines": ("DL-C3-004", "C3", "DL", None, DERC, "2019-05-31", "2019-05-31", "E6", "medium",
                                     "presumed_current", "regulator_original", "GNM/VNM Guidelines 2019."),
    "DL/DL-GNMVNM-2020-first-amend": ("DL-C3-005", "C3", "DL", None, DERC, "2020-10-19", "2020-10-19", "E6", "medium",
                                      "presumed_current", "regulator_original", ""),
    "DL/DL-GNMVNM-2020-second-amend": ("DL-C3-006", "C3", "DL", None, DERC, "2020-12-24", "2020-12-24", "E6", "medium",
                                       "presumed_current", "regulator_original", ""),
    "DL/DL-GNMVNM-2021-third-amend": ("DL-C3-007", "C3", "DL", None, DERC, "2021-09-28", "2021-09-28", "E6", "medium",
                                      "presumed_current", "regulator_original", ""),
    "DL/DL-GNMVNM-2022-fourth-amend": ("DL-C3-008", "C3", "DL", None, DERC, "2022-02-24", "2022-02-24", "E6", "medium",
                                       "presumed_current", "regulator_original", ""),
    "DL/DL-GNMVNM-2024-fifth-amend": ("DL-C3-009", "C3", "DL", None, DERC, "2024-03-15", "2024-04-01", "E1", "medium",
                                      "presumed_current", "regulator_original",
                                      "Substituted Guideline 3(8) effective 01.04.2024 per the staging record."),
    "DL/DL-P2P-2024-guidelines": ("DL-C3-010", "C3", "DL", None, DERC, "2024-06-24", "2024-06-24", "E6", "low",
                                  "context", "regulator_original", "Context."),
    "DL/DL-SC-2024-fifth-amend": ("DL-C3-011", "C3", "DL", None, DERC, "2024-07-16", "2024-07-16", "E6", "medium",
                                  "presumed_current", "regulator_original", ""),
    "DL/DL-NM-2024-first-amend-regs": ("DL-C3-012", "C3", "DL", None, DERC, "2024-07-26", "2024-07-26", "E4", "medium",
                                       "presumed_current", "regulator_original",
                                       "In force from publication in the Gazette; signature date used."),
    "DL/DL-NM-2025-first-amend-guidelines": ("DL-C3-013", "C3", "DL", None, DERC, "2025-05-01", "2025-05-01", "E6",
                                             "medium", "presumed_current", "regulator_original", ""),
    "DL/DL-GNMVNM-2025-sixth-amend": ("DL-C3-014", "C3", "DL", None, DERC, "2025-06-05", "2025-06-05", "E6", "medium",
                                      "presumed_current", "regulator_original", ""),
    "DL/DL-GNMVNM-2025-seventh-amend": ("DL-C3-015", "C3", "DL", None, DERC, "2026-01-20", "2026-01-20", "E6",
                                        "medium", "presumed_current", "regulator_original",
                                        "Titled 2025, dated 20.01.2026."),
    "DL/DL-NM-2026-second-amend-guidelines": ("DL-C3-016", "C3", "DL", None, DERC, "2026-07-16", "2026-07-16", "E6",
                                              "medium", "presumed_current", "regulator_original", ""),
    # --- Uttar Pradesh (uperc.org; 2015/2019 PDFs extracted unmodified from .rar archives) --
    "UP/UP-RSPV-2015-regs": ("UP-C3-001", "C3", "UP", None, UPERC, "2015-03-20", "2015-03-20", "E4", "medium",
                             "presumed_superseded", "regulator_original",
                             "Printed March 2015; superseded by the 2019 Regulations (Reg 1(3)). Dated 20/03/2015 "
                             "in the notification header; Reg 1(2): in force from notification (D28, 2026-10-01)."),
    "UP/UP-RSPV-2019-regs": ("UP-C3-002", "C3", "UP", None, UPERC, "2019-01-04", "2019-01-04", "E4", "medium",
                             "presumed_current", "regulator_original", "Scan; text from macOS Vision OCR (staging)."),
    "UP/UP-RSPV-2019-first-amend-addendum": ("UP-C3-003", "C3", "UP", None, UPERC, "2022-06-01", "2022-06-01", "E6",
                                             "medium", "presumed_current", "regulator_original", ""),
    "UP/UP-RSPV-2019-second-amend": ("UP-C3-004", "C3", "UP", None, UPERC, "2023-11-17", "2023-11-17", "E6", "medium",
                                     "presumed_current", "regulator_original", "Bilingual; Hindi text layer is garbled."),
    "UP/UP-RSPV-2019-third-amend": ("UP-C3-005", "C3", "UP", None, UPERC, "2025-06-03", "2025-06-03", "E6", "medium",
                                    "presumed_current", "regulator_original", "Scan; text from macOS Vision OCR (staging)."),
    "UP/UP-RSPV-2019-statement-of-reasons": ("UP-C4-001", "C4", "UP", None, UPERC, "UNKNOWN", "UNKNOWN", "E9", "low",
                                             "context", "regulator_original", "Scan, not OCR'd; context only."),
    # --- Central -----------------------------------------------------------------------------
    "IN/IN-ROC-2021-amend-GSR448E": ("IN-C3-004", "C3", "IN", None, "Ministry of Power (MoP)", "2021-06-28",
                                     "2021-06-28", "E4", "medium", "presumed_current", "government_mirror",
                                     "G.S.R. 448(E), from the APERC nic.in mirror of the Gazette; confirm on egazette.gov.in."),
    "IN/IN-CEA-2013-DG-connectivity-regs-principal": ("IN-C3-005", "C3", "IN", None, "Central Electricity Authority (CEA)",
                                                      "2013-09-30", "2013-09-30", "E6", "low", "presumed_current",
                                                      "regulator_original", "Principal regulations; poor OCR. Base of IN-C3-003."),
    "IN/IN-ALMM-2025-07-28-amend-OM-283-59-2024": ("IN-C2-008", "C2", "IN", None, MNRE, "2025-07-28", "2025-07-28", "E1",
                                                   "medium", "presumed_current", "regulator_original", "Scan; Vision OCR."),
    "IN/IN-ALMM-2025-07-28-clarification-OM-283-76-2023": ("IN-C2-009", "C2", "IN", None, MNRE, "2025-07-28",
                                                           "2025-07-28", "E1", "medium", "presumed_current",
                                                           "regulator_original", "Scan; Vision OCR."),
    "IN/IN-ALMM-2025-07-31-publishing-List-II-OM-283-51-2025": ("IN-C2-010", "C2", "IN", None, MNRE, "2025-07-31",
                                                                "2025-07-31", "E1", "medium", "presumed_current",
                                                                "regulator_original", "First ALMM List-II (annex data)."),
    "IN/IN-ALMM-2026-05-25-OM-283-63-2025": ("IN-C2-011", "C2", "IN", None, MNRE, "2026-05-25", "2026-05-25", "E1",
                                             "medium", "presumed_superseded", "regulator_original",
                                             "Superseded by the 18.07.2026 OM; scan, Vision OCR."),
    "IN/IN-ALMM-2026-07-18-OM-283-53-2026": ("IN-C2-012", "C2", "IN", None, MNRE, "2026-07-18", "2026-07-18", "E1",
                                             "medium", "presumed_current", "regulator_original", "Scan; Vision OCR."),
    "IN/IN-ALMM-2026-08-04-clarification-OM-283-54-2026": ("IN-C2-013", "C2", "IN", None, MNRE, "2026-08-04",
                                                           "2026-08-04", "E1", "medium", "presumed_current",
                                                           "regulator_original", "Scan; Vision OCR."),
    "IN/IN-PMSG-2024-07-CFA-original-guidelines": ("IN-C1-011", "C1", "IN", None, MNRE, "2024-06-07", "2024-06-07",
                                                   "E1", "high", "presumed_superseded", "regulator_original",
                                                   "Original (unamended) CFA guidelines; IN-C1-001 bundles the 07.07.2025 "
                                                   "amendment OM 318/140/2024 with them."),
    "IN/IN-PMSG-2025-02-14-clarification": ("IN-C1-012", "C1", "IN", None, MNRE, "2025-02-13", "2025-02-13", "E1",
                                            "medium", "presumed_current", "regulator_original",
                                            "Ground-mounted elevated systems allowed; scan, Vision OCR."),
}

# --------------------------------------------------------------------------------------------
# Node ids for staged candidate clauses: (staged stem, clause_ref) -> (node suffix, subject, rank)
# --------------------------------------------------------------------------------------------
NID: dict[tuple[str, str], tuple[str, str]] = {
    ("GERC-DRE-2026-Draft", "Draft Reg 1.4 (repeal)"): ("1.4", "net_metering_capacity_cap"),
    ("GERC-DRE-2026-Draft", "Draft Reg 6.2 (no feasibility study up to 10 kW)"): ("6.2", "feasibility_sanction_stage"),
    ("GERC-NetMetering-2016-Reg", "Reg 5, proviso (DT hosting limit)"): ("5-proviso", "dt_capacity_limit"),
    ("GERC-NetMetering-2016-Reg", "Reg 5.1 proviso (augmentation cost)"): ("5.1-proviso", "dt_capacity_limit"),
    ("GERC-NetMetering-2016-Reg", "Reg 6.2 (capacity cap vs sanctioned load)"): ("6.2", "net_metering_capacity_cap"),
    ("GERC-NetMetering-2016-Reg", "Reg 6.2 first proviso (kW bounds)"): ("6.2-proviso1", "net_metering_capacity_cap"),
    ("GERC-NetMetering-2016-Reg", "Reg 7 row 4 (TFR request timeline)"): ("7-row4", "feasibility_sanction_stage"),
    ("GERC-NetMetering-2016-Reg", "Reg 7 row 6 (post-TFR consent timeline)"): ("7-row6", "feasibility_sanction_stage"),
    ("GERC-NetMetering-2016-Reg", "Reg 8(2) connectivity table"): ("8.2", "meter_phase_threshold"),
    ("GERC-NetMetering-2016-Reg", "Reg 13.5 (solar meter class; check meters)"): ("13.5-class", "meter_phase_threshold"),
    ("GERC-NetMetering-2016-Reg", "Reg 13.5 (check meter threshold)"): ("13.5-check", "meter_phase_threshold"),
    ("GERC-NetMetering-2017-1stAmend", "Amended Reg 6.2"): ("6.2", "net_metering_capacity_cap"),
    ("GERC-NetMetering-2020-2ndAmend", "Amended Reg 5 proviso (DT limit)"): ("5-proviso", "dt_capacity_limit"),
    ("GERC-NetMetering-2020-2ndAmend", "Amended Reg 6.2 (residential and MSME exempt from cap)"):
        ("6.2", "net_metering_capacity_cap"),
    ("GERC-NetMetering-2020-2ndAmend", "Amended Reg 13.5 (meter class)"): ("13.5-class", "meter_phase_threshold"),
    ("GERC-NetMetering-2020-2ndAmend", "Amended Reg 7 item 11.5 (no-volt relay above 10 kW)"):
        ("7-item11.5", "grid_inverter_safety_standard"),
    ("GERC-NetMetering-2022-3rdAmend", "Amended Reg 6.2(a)"): ("6.2a", "net_metering_capacity_cap"),
    ("GERC-NetMetering-2022-3rdAmend", "Amended Reg 6.2(b) (gross metering floor)"):
        ("6.2b", "gross_metering_capacity_cap"),
    ("GERC-NetMetering-2022-3rdAmend", "Amended Reg 6.2(c)(ii)"): ("6.2c-ii", "net_metering_capacity_cap"),
    ("GERC-NetMetering-2022-3rdAmend", "Amended Reg 6.2(c)(iii) (REC mechanism)"): ("6.2c-iii", "net_metering_capacity_cap"),
    ("GERC-NetMetering-2024-4thAmend", "Amended Reg 7 row 4 (TFR request timeline)"): ("7-row4", "feasibility_sanction_stage"),
    ("GERC-NetMetering-2024-4thAmend", "Amended Reg 7 row 6 (post-TFR timeline)"): ("7-row6", "feasibility_sanction_stage"),
    ("GERC-NetMetering-2024-4thAmend", "Amended Reg 7, proviso (no feasibility study up to 10 kW)"):
        ("7-proviso", "feasibility_sanction_stage"),
    ("GERC-NetMetering-2024-4thAmend", "Amended Reg 7, second proviso (compensation for delay)"):
        ("7-proviso2", "discom_approval_timeline"),
    ("GERC-NetMetering-2024-4thAmend", "Substituted Reg 5.1 proviso (strengthening cost up to 6 kW)"):
        ("5.1-proviso", "dt_capacity_limit"),
    ("GERC-NetMetering-2024-4thAmend", "Substituted Reg 5.1, (a) LT above 6 kW up to 100 kW"): ("5.1a", "dt_capacity_limit"),
    ("GERC-NetMetering-2025-5thAmend", "Substituted Reg 8(2) (connectivity level by Supply Code)"):
        ("8.2", "meter_phase_threshold"),
    ("GERC-NetMetering-2025-5thAmend", "Reg 7 new proviso (no separate agreement for PM Surya Ghar)"):
        ("7-proviso-pmsg", "commissioning_report_procedure"),
    ("BESCOM-SRTPV-Common-SOP-DSPV", "Item 18 (check meter threshold)"): ("18", "meter_phase_threshold"),
    ("BESCOM-SRTPV-Common-SOP-DSPV", "Item 4 note ii (deemed feasible up to 150 kW)"):
        ("4-note-ii", "feasibility_sanction_stage"),
    ("BESCOM-SRTPV-Common-SOP-DSPV", "Item 4 (DT hosting limit, LT)"): ("4", "dt_capacity_limit"),
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 15 (check meter threshold)"): ("15", "meter_phase_threshold"),
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 22 (interconnection voltage)"): ("22", "meter_phase_threshold"),
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 23 (DT hosting limit)"): ("23", "dt_capacity_limit"),
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 26 (SDO verifies feasibility for every application)"):
        ("26", "feasibility_sanction_stage"),
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 37 (non-residential cap at sanctioned load)"):
        ("37", "net_metering_capacity_cap"),
    ("KERC-DSPV-Regulations-2026", "Reg 24.1 (repeal)"): ("24.1", "net_metering_capacity_cap"),
    ("KERC-DSPV-Regulations-2026", "Reg 8.2 (DT hosting limit)"): ("8.2", "dt_capacity_limit"),
    ("KERC-DSPV-Regulations-2026", "Reg 15.1 (10 kW sanctioned-load tolerance)"): ("15.1", "load_enhancement_requirement"),
    ("KERC-DSPV-Regulations-2026", "Timeline (>150 kW): feasibility"): ("timeline-feasibility", "feasibility_sanction_stage"),
    ("KERC-SRTPV-tariff-order-2023-06-01", "Decision (i): substituted Reg 6(a) connectivity table"):
        ("6a", "meter_phase_threshold"),
    ("KERC-SRTPV-tariff-order-2023-06-01", "Decision (i): substituted Reg 6(e) (DT hosting limit)"): ("6e", "dt_capacity_limit"),
    ("KERC-SRTPV-tariff-order-2023-06-01", "Decision (i): substituted Reg 6(f) (HT feeder limit)"): ("6f", "dt_capacity_limit"),
    ("KERC-SRTPV-tariff-order-2023-06-01",
     "Decision (l) timeline: site verification / feasibility (1-2000 kW, non-domestic)"):
        ("l-feasibility", "feasibility_sanction_stage"),
    ("KERC-SRTPV-tariff-order-2023-06-01", "Decision (k): carport / cap at sanctioned load"):
        ("k-carport", "net_metering_capacity_cap"),
    ("KERC-order-2024-12-05", "Preamble (b): Rule 7A quoted (deemed accepted, no feasibility up to 10 kW)"):
        ("preamble-b", "feasibility_sanction_stage"),
    ("KERC-order-2024-12-05", "Order para 1 (auto-enhancement of sanctioned load up to 10 kW)"):
        ("1", "load_enhancement_requirement"),
    ("KERC-order-2024-12-05", "Order para 3 (10% DC tolerance)"): ("3", "load_enhancement_requirement"),
    ("TANGEDCO-test1-soi-100519", "Para 2 (capacity cap vs sanctioned demand)"): ("2", "net_metering_capacity_cap"),
    ("TANGEDCO-test1-soi-100519", "Para 3 (voltage/phase thresholds)"): ("3", "meter_phase_threshold"),
    ("TANGEDCO-test1-soi-100519", "Para 5 (DT hosting limit)"): ("5", "dt_capacity_limit"),
    ("TANGEDCO-test1-soi-100519", "Para 6 (feasibility timeline)"): ("6", "feasibility_sanction_stage"),
    ("TANGEDCO-test1-soi-100519", "Para 14 (inspection authority threshold)"): ("14", "commissioning_report_procedure"),
    ("TNEBLTD-usrp-Salientfeatures", "I.2 (net billing / net feed-in capacity)"): ("I.2", "net_metering_capacity_cap"),
    ("TNEBLTD-usrp-Salientfeatures", "VII.3 (DT hosting limit)"): ("VII.3", "dt_capacity_limit"),
    ("TNEBLTD-usrp-Salientfeatures", "VII.4 (power transformer limit, HT gross metering)"): ("VII.4", "dt_capacity_limit"),
    ("TNEBLTD-usrp-Salientfeatures", "I.3(a) (gross metering minimum size)"): ("I.3a", "gross_metering_capacity_cap"),
    ("TNEBLTD-usrp-Salientfeatures", "Check meter (optional up to 20 kW)"): ("check-meter", "meter_phase_threshold"),
    ("TNEBLTD-usrp-Salientfeatures", "Annexure I timeline (site verification / technical feasibility)"):
        ("annex1-feasibility", "feasibility_sanction_stage"),
    ("DL-GNMVNM-2019-guidelines", "Guideline 3(8)"): ("3.8", "net_metering_capacity_cap"),
    ("DL-GNMVNM-2022-fourth-amend", "Guideline 13 (substituted 24.02.2022)"): ("13", "application_fee_tariff"),
    ("DL-GNMVNM-2024-fifth-amend", "Guideline 3(8) (substituted, eff. 01.04.2024)"): ("3.8", "net_metering_capacity_cap"),
    ("DL-GNMVNM-2024-fifth-amend", "Guideline 13 (substituted)"): ("13", "application_fee_tariff"),
    ("DL-GNMVNM-2025-seventh-amend", "Guideline 3(6) (substituted, dated 20.01.2026)"): ("3.6", "application_fee_tariff"),
    ("DL-GNMVNM-2025-seventh-amend", "Guideline 9(2)(b) (substituted)"): ("9.2b", "billing_settlement_period"),
    ("DL-GNMVNM-2025-seventh-amend", "Guideline 3(2) (substituted)"): ("3.2", "net_metering_capacity_cap"),
    ("DL-GNMVNM-2025-sixth-amend", "Guideline 8(2)(c),(e) (substituted)"): ("8.2ce", "billing_settlement_period"),
    ("DL-NM-2014-regs-and-guidelines-sws", "Guidelines under DERC NM Regs 2014, cl. 1(1)"): ("g1.1", "dt_capacity_limit"),
    ("DL-NM-2014-regs-and-guidelines-sws", "Guidelines under DERC NM Regs 2014, cl. 3(3)"):
        ("g3.3", "feasibility_sanction_stage"),
    ("DL-NM-2014-regs-and-guidelines-sws", "Guidelines cl. 3(13)"): ("g3.13", "discom_approval_timeline"),
    ("DL-NM-2014-regs-and-guidelines-sws", "Guidelines cl. 3(16)"): ("g3.16", "discom_approval_timeline"),
    ("DL-NM-2014-regs", "Reg. 5(4) DERC NM Regs 2014"): ("5.4", "net_metering_capacity_cap"),
    ("DL-NM-2024-first-amend-regs", "Reg. 5(3) provisos (inserted 26.07.2024)"): ("5.3-proviso3", "feasibility_sanction_stage"),
    ("DL-NM-2024-first-amend-regs", "Reg. 5(3) proviso 1"): ("5.3-proviso1", "feasibility_sanction_stage"),
    ("DL-NM-2026-second-amend-guidelines", "Guideline 3 (substituted), Stage I"): ("g3-stage1", "feasibility_sanction_stage"),
    ("DL-NM-2026-second-amend-guidelines", "Guideline 3 (substituted), Stage II and cumulative cap"):
        ("g3-cumulative", "discom_approval_timeline"),
    ("DL-NM-2026-second-amend-guidelines", "Guideline 3(1) proviso (substituted)"): ("g3.1-proviso", "application_fee_tariff"),
    ("DL-SC-2024-fifth-amend", "Reg. 11(4)(i)(a) Supply Code 2017 (substituted 16.07.2024)"):
        ("11.4ia", "discom_approval_timeline"),
    ("IN-ALMM-2025-07-28-amend-OM-283-59-2024", "Para 5 modified (OM 28.07.2025)"): ("5", "almm_module_compliance"),
    ("IN-ALMM-2025-07-28-amend-OM-283-59-2024", "Para 8 (reiterated)"): ("8", "almm_module_compliance"),
    ("IN-ALMM-2026-05-25-OM-283-63-2025", "Para 7 (SUPERSEDED 18.07.2026)"): ("7", "almm_module_compliance"),
    ("IN-ALMM-2026-07-18-OM-283-53-2026", "Para 3"): ("3", "almm_module_compliance"),
    ("IN-ALMM-2026-08-04-clarification-OM-283-54-2026", "Para 1(b)"): ("1b-definition", "almm_module_compliance"),
    ("IN-ALMM-2026-08-04-clarification-OM-283-54-2026", "Para 1(a)"): ("1a", "almm_module_compliance"),
    ("IN-PMSG-2024-07-CFA-original-guidelines", "Para on Phase II claims (original 07.06.2024)"):
        ("annex-phase2-claims", "subsidy_disbursement_process"),
    ("IN-ROC-2021-amend-GSR448E", "Rule 11(4) (substituted by G.S.R. 448(E), 28.06.2021)"):
        ("11.4", "net_metering_capacity_cap"),
    ("UP-RSPV-2019-first-amend-addendum", "Reg. 10.6 (added 01.06.2022)"): ("10.6", "discom_approval_timeline"),
    ("UP-RSPV-2019-regs", "Reg. 6.2"): ("6.2", "dt_capacity_limit"),
    ("UP-RSPV-2019-regs", "Reg. 5.1 and proviso"): ("5.1", "net_metering_capacity_cap"),
    ("UP-RSPV-2019-regs", "Reg. 5.1 proviso"): ("5.1-proviso", "net_metering_capacity_cap"),
    ("UP-RSPV-2019-regs", "Reg. 6.2 second proviso"): ("6.2-proviso2", "dt_capacity_limit"),
    ("UP-RSPV-2019-regs", "Reg. 10.3(iii)/(iv) net-metering unadjusted credit rate"):
        ("10.3", "surplus_energy_purchase_rate"),
    ("UP-RSPV-2019-second-amend", "Reg. 2(k)(iii) Net Metering Scheme eligibility (17.11.2023)"):
        ("2k-iii", "net_metering_capacity_cap"),
    ("UP-RSPV-2019-third-amend", "Reg. 10.3(ii) proviso (03.06.2025)"): ("10.3ii", "surplus_energy_purchase_rate"),
}

# Predecessor clauses named in amends_or_supersedes that are not themselves candidate clauses:
# (doc stem or CORPUS:<id>, clause_ref) -> node suffix. The node snippet is the recorded evidence quote.
PREDECESSOR_NID: dict[tuple[str, str], str] = {
    ("GERC-NetMetering-2017-1stAmend", "Reg 6.2 (as amended 2017)"): "GJ-C3-002#cl-6.2",
    ("GERC-NetMetering-2020-2ndAmend", "Reg 6.2 (as amended 2017, 2020)"): "GJ-C3-003#cl-6.2",
    ("GERC-NetMetering-2020-2ndAmend", "Reg 6.2 (as amended)"): "GJ-C3-003#cl-6.2",
    ("GERC-NetMetering-2016-Reg", "Reg 5 proviso"): "GJ-C3-001#cl-5-proviso",
    ("GERC-NetMetering-2016-Reg", "Reg 6.2"): "GJ-C3-001#cl-6.2",
    ("GERC-NetMetering-2016-Reg", "Reg 13.5"): "GJ-C3-001#cl-13.5-class",
    ("GERC-NetMetering-2016-Reg", "Reg 7 row 4"): "GJ-C3-001#cl-7-row4",
    ("GERC-NetMetering-2016-Reg", "Reg 7 row 6"): "GJ-C3-001#cl-7-row6",
    ("GERC-NetMetering-2016-Reg", "Reg 5.1 proviso"): "GJ-C3-001#cl-5.1-proviso",
    ("GERC-NetMetering-2016-Reg", "Reg 8(2)"): "GJ-C3-001#cl-8.2",
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 15"): "KA-C5-001#cl-15",
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 26"): "KA-C5-001#cl-26",
    ("BESCOM-SRTPV-Guidelines-2023-08-05", "Para 23"): "KA-C5-001#cl-23",
    ("KERC-SRTPV-tariff-order-2023-06-01", "Substituted Reg 6(e)"): "KA-C3-001#cl-6e",
    ("KERC-SRTPV-tariff-order-2023-06-01", "Decision (k) / cap at sanctioned load"): "KA-C3-001#cl-k-carport",
    ("KERC-order-2024-12-05", "Order para 3"): "KA-C4-001#cl-3",
    ("TANGEDCO-test1-soi-100519", "Para 2"): "TN-C5-001#cl-2",
    ("TANGEDCO-test1-soi-100519", "Para 5"): "TN-C5-001#cl-5",
    ("TANGEDCO-test1-soi-100519", "Para 6"): "TN-C5-001#cl-6",
    ("DL-GNMVNM-2019-guidelines", "Guideline 3(8)"): "DL-C3-004#cl-3.8",
    ("DL-GNMVNM-2019-guidelines", "Guideline 13"): "DL-C3-004#cl-13",
    ("DL-GNMVNM-2022-fourth-amend", "Guideline 13"): "DL-C3-008#cl-13",
    ("DL-GNMVNM-2024-fifth-amend", "Guideline 3(6) second proviso"): "DL-C3-009#cl-3.6",
    ("DL-GNMVNM-2019-guidelines", "Guideline 9(2)(b)"): "DL-C3-004#cl-9.2b",
    ("DL-GNMVNM-2020-second-amend", "Guideline 3(2)"): "DL-C3-006#cl-3.2",
    ("DL-GNMVNM-2019-guidelines", "Guideline 8(2)(c),(e)"): "DL-C3-004#cl-8.2ce",
    ("DL-NM-2014-regs-and-guidelines-sws", "Guidelines cl. 3(3)"): "DL-C3-002#cl-g3.3",
    ("DL-NM-2014-regs-and-guidelines-sws", "Guidelines cl. 3(9),(13),(16)"): "DL-C3-002#cl-g3.13",
    ("DL-NM-2025-first-amend-guidelines", "Guideline 3(1) proviso"): "DL-C3-013#cl-g3.1-proviso",
    ("UP-RSPV-2015-regs", "Reg. 6.2"): "UP-C3-001#cl-6.2",
    ("UP-RSPV-2015-regs", "Reg. 5.1-5.2"): "UP-C3-001#cl-5.1",
    ("UP-RSPV-2015-regs", "Reg. 10 (unadjusted credit)"): "UP-C3-001#cl-10",
    ("UP-RSPV-2019-regs", "Reg. 10.3(ii) proviso"): "UP-C3-002#cl-10.3ii",
    ("CORPUS:IN-C2-006", "Para 5-6 OM 09.12.2024"): "IN-C2-006#cl-5",
    ("IN-ALMM-2026-07-18-OM-283-53-2026", "Para 3 supersession"): "IN-C2-012#cl-3",
    ("IN-ALMM-2026-05-25-OM-283-63-2025", "entire OM (superseded)"): "IN-C2-011#cl-7",
    ("CORPUS:IN-C1-001", "Phase II claims para (amended OM 318/140/2024)"): "IN-C1-001#cl-annex1-ii-amended",
    ("CORPUS:IN-C3-002", "Rule 11(4) ROC 2020"): "IN-C3-002#cl-11.4",
    # KERC 2016 Regulations are not in the corpus; the 2023 order quotes the old Reg 6(a) table verbatim.
    ("KERC (Implementation of Solar Rooftop Photovoltaic Power Plants) Regulations, 2016 (NOT in staging; not "
     "retrievable, see FAILURES.md)", "Reg 6(a)"): "KA-C3-001#cl-6a-2016-quoted",
}

# Edges recorded in staging that are not drawn, with the reason (logged in the build report).
SKIP_EDGES: dict[tuple[str, str], str] = {
    ("GERC-DRE-2026-Draft", "Draft Reg 1.4 (repeal)"): "draft instrument: not in force, no supersession edge",
    ("KERC-DSPV-Regulations-2026", "Reg 24.1 (repeal)"): "repealed KERC 2016 Regulations are not in the corpus",
    ("KERC-SRTPV-tariff-order-2023-06-01", "Decision (i): substituted Reg 6(e) (DT hosting limit)"):
        "the 2016 Reg 6(e) text (old percentage) is not in the corpus; recorded quote is the substitution sentence",
    ("GERC-NetMetering-2024-4thAmend", "Amended Reg 7, proviso (no feasibility study up to 10 kW)"):
        "proviso is an insertion; the recorded predecessor quote (T/C note) is not a superseded rule",
    ("IN-PMSG-2024-07-CFA-original-guidelines", "Para on Phase II claims (original 07.06.2024)"):
        "drawn as an EXTRA_EDGE with the amending OM's own date (07.07.2025)",
}

# Explicit substitution language for edges whose superseding document states it (evidence type explicit).
EXPLICIT_EVIDENCE: dict[str, str] = {
    "GJ-C3-003#cl-5-proviso": "The second para of Regulation 5 of the Principal Regulations shall stand amended as under:",
    "GJ-C3-003#cl-13.5-class": "Para 13.5 of the Principal Regulations, shall be replaced with the following para:",
    "GJ-C3-004#cl-6.2a": "shall stand amended and substituted by following clauses:",
    "DL-C3-009#cl-3.8": "In Guidelines 3(8), the following shall be substituted as:-",
    "IN-C2-012#cl-3": "In supersession of MNRE's O.M. No. 283/63/2025-GRID SOLAR dated 25th May 2026,",
    "UP-C3-002#cl-6.2": 'These Regulations supersede the "UPERC (Rooftop Solar PV Grid Interactive Systems Gross / '
                        'Net Metering) Regulations, 2015".',
    "UP-C3-002#cl-5.1": 'These Regulations supersede the "UPERC (Rooftop Solar PV Grid Interactive Systems Gross / '
                        'Net Metering) Regulations, 2015".',
}

# Decisive clauses not among the staged candidates, quoted verbatim from the r3 text by this script.
# (node_id, clause_ref, subject, quote)
EXTRA_NODES: list[tuple[str, str, str, str]] = [
    ("GJ-C3-004#cl-6.2c-i", "Reg 6.2(c)(i) (substituted 2022)", "net_metering_capacity_cap",
     "Solar Projects set up by residential consumers on their rooftop/premises shall be allowed irrespective of "
     "consumer sanctioned load."),
    ("GJ-C3-003#cl-13.5-check", "Reg 13.5 (replaced 2020), check meters", "meter_phase_threshold",
     "Check Meters shall be mandatory for Rooftop Solar PV Systems having capacity more than 20 kW."),
    ("DL-C3-016#cl-g3-stage1-deemed", "Guideline 3 (substituted 2026), Stage I provisos", "feasibility_sanction_stage",
     "Provided that no technical feasibility analysis shall be required in respect of a Renewable Energy System of "
     "capacity up to 10 kW on the same supply type"),
    ("DL-C3-016#cl-g3-stage1-lapse", "Guideline 3 (substituted 2026), Stage I second proviso",
     "feasibility_sanction_stage",
     "Provided further that where the Distribution Licensee fails to communicate the outcome of the feasibili ty "
     "analysis within the said period, the feasibility shall be deemed to have been granted;"),
    ("IN-C2-013#cl-1b", "Para 1(b) (net-metering window)", "almm_module_compliance",
     "b) For Net-Metering & Open Access Projects, if commissioned by 31.12.2026, the projects are exempt from "
     "ALMM List-ll for solar cells, else not."),
    ("IN-C2-013#cl-1b-giu", "Para 1(b) (Give It Up residential cases)", "almm_module_compliance",
     "be exempted from applicability of ALMM List-II (for solar PV cells) till the end of the scheme period, i.e., "
     "31st March 2027,"),
    ("IN-C2-013#cl-1e", "Para 1(e)(i) (behind-the-meter captive)", "almm_module_compliance",
     "ALMM List-I (for solar PV modules) and ALMM List-II (for solar PV cells) shall not apply to behind-the-meter "
     "solar power plants solely used for captive consumption"),
    ("IN-C1-001#cl-annex1-ii-amended", "Amendment OM 318/140/2024 (07.07.2025), Annexure 1 item ii (amended column)",
     "subsidy_disbursement_process",
     "CFAiftheclaimisreceived till October admissible for CFA.if claim is received till 2024.Theclaimsreceivedafter "
     "31.12.2025."),
    ("IN-C1-001#cl-phase2-pmsg-split", "Annexure (application date split, 13.02.2024)", "subsidy_disbursement_process",
     "Application received under PM - Surya Ghar : Muft Bijli Yojana (on and after 13th Feb 2024)"),
    ("UP-C3-001#cl-6.2", "Reg 6.2 (2015)", "dt_capacity_limit",
     "6.2 Provided that the capacity to be allowed in the area fed from the distribution transformer or any other "
     "transformer from which power is fed to the eligible consumer shall not exceed 15 % or any other percentage as "
     "may be fixed by the Commission of the rated capacity of such transformer(s)."),
    ("UP-C3-001#cl-5.1", "Reg 5.1 (2015)", "net_metering_capacity_cap",
     "5.1 The maximum peak capacity of the grid connected rooftop solar PV system to be installed by any eligible "
     "consumer shall not exceed 100% of the sanctioned connected load / contract demand of the consumer."),
    ("UP-C3-002#cl-1.3", "Reg 1(3) (supersession of the 2015 Regulations)", "net_metering_capacity_cap",
     'These Regulations supersede the "UPERC (Rooftop Solar PV Grid Interactive Systems Gross / Net Metering) '
     'Regulations, 2015".'),
    ("IN-C3-001#cl-11.7A", "rule 11(7A) (inserted 2024)", "feasibility_sanction_stage",
     "(7A) The applications for roof top solar photo voltaic systems upto 10 kW capacity, complete in all respects "
     "shall be deemed to have been accepted without requiring technical feasibility study and any commensurate "
     "enhancement of the sanctioned load of the consumer, as may be required, shall be carried out by the "
     "distribution licensee."),
]
# Effective dates of extra nodes that differ from their document's (amending OM bundled in an r2 document).
EXTRA_NODE_DATES = {"IN-C1-001#cl-annex1-ii-amended": ("2025-07-07", "E1", "medium"),
                    "IN-C3-001#cl-11.7A": ("2024-02-22", "E1", "high")}

# Extra edges (from, to, relation, from_date, type, confidence, quote doc, quote, note)
EXTRA_EDGES: list[tuple[str, str, str, str, str, str, str, str, str]] = [
    ("IN-C1-011#cl-annex-phase2-claims", "IN-C1-001#cl-annex1-ii-amended", "superseded_by", "2025-07-07", "explicit",
     "medium", "IN-C1-001", "Subject: Amendment in Guidelines for Implementation of PM-Surya Ghar: Muft Bijli",
     "Amendment OM 318/140/2024 dated 07.07.2025 (bundled in IN-C1-001) amends the Phase-II claim window; the "
     "two-column (existing/amended) table is OCR-interleaved: read the page image."),
    ("GJ-C3-001#cl-13.5-check", "GJ-C3-003#cl-13.5-check", "superseded_by", "2020-01-22", "explicit", "medium",
     "GJ-C3-003", "Para 13.5 of the Principal Regulations, shall be replaced with the following para:",
     "Para 13.5 replaced in full; the 20 kW check-meter threshold is restated unchanged."),
    ("GJ-C3-002#cl-6.2", "GJ-C3-004#cl-6.2c-i", "superseded_by", "2022-05-31", "explicit", "medium", "GJ-C3-004",
     "shall stand amended and substituted by following clauses:", "Residential exemption restated in 6.2(c)(i)."),
    ("IN-C2-008#cl-8", "IN-C2-012#cl-3", "amended_by", "2026-07-18", "implicit", "medium", "IN-C2-012",
     "Earlier this dispensation for Net-metering projects and Open Access renewable power projects was available "
     "till 31st May 2026.",
     "The 18.07.2026 OM extends the List-II exemption for net-metering / open-access projects from 01.06.2026 to "
     "31.12.2026; para 8 (as reiterated 28.07.2025) is amended to that extent."),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def loose(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("ll", "ii").replace("|", "i"))


def quote_check(text: str, q: str, raw: Path | None = None) -> str:
    """exact / loose (whitespace, case, punctuation) against the r3 text; else pypdf_text_only when the quote
    is in the raw PDF's pypdf text (staging matched quotes there; pdfplumber re-lays tables); else not_found."""
    if norm(q) in norm(text):
        return "exact"
    if loose(q) in loose(text):
        return "loose"
    if raw is not None and raw.suffix == ".pdf":
        try:
            ptext = " ".join(pg.extract_text() or "" for pg in pypdf.PdfReader(str(raw)).pages)
        except Exception:
            ptext = ""
        if loose(q) in loose(ptext):
            return "pypdf_text_only"
    return "not_found"


def pdf_pages(path: Path) -> int:
    try:
        return max(1, len(pypdf.PdfReader(str(path)).pages))
    except Exception:
        return 1


def extract(stem: str, doc_id: str, raw: Path, text_dir: Path) -> dict[str, Any]:
    """Extract text with the corpus code; reuse an existing extraction of the same raw file."""
    meta_path = text_dir / f"{doc_id}.meta.json"
    sha = compute_file_sha256(raw)
    if meta_path.exists() and (text_dir / f"{doc_id}.txt").exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("source_sha256") == sha:
            return meta
    ocr = CORPUS_STAGING_DIR / f"{stem}.ocr.txt"
    if ocr.exists():
        tmp = text_dir / f"{doc_id}.source.txt"
        lines = ocr.read_text(encoding="utf-8").splitlines()
        body = "\n".join(lines[1:] if lines and lines[0].startswith("DERIVED FILE") else lines)
        tmp.write_text(body, encoding="utf-8", newline="\n")
        _extract.extract_document(tmp, doc_id, text_dir, forced_text_layer=TextLayer.OCR)
        tmp.unlink()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.update(source_filename=f"{doc_id}.pdf", source_sha256=sha, page_count=pdf_pages(raw),
                    tool="macOS Vision OCR (staging *.ocr.txt) + suryabench native_text_reader")
    else:
        _extract.extract_document(raw, doc_id, text_dir)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    return meta


def build_documents(out: Path) -> list[DocumentInventory]:
    """Copy r2 unchanged, add every staged document, write MANIFEST.json and MANIFEST.sha256."""
    r2 = load_manifest(CORPUS_DIR / "MANIFEST.json")
    for sub in ("raw", "text", "provenance", "graph"):
        shutil.copytree(CORPUS_DIR / sub, out / sub, dirs_exist_ok=True)
    shutil.copyfile(CORPUS_DIR / "translation_cache.json", out / "translation_cache.json")
    docs = list(r2.documents)
    seen = {d.sha256 for d in docs}
    for stem, (doc_id, cls, code, discom, issuer, ddate, eff, basis, conf, status, srcc, note) in DOCS.items():
        src = CORPUS_STAGING_DIR / f"{stem}.pdf"
        prov_src = CORPUS_STAGING_DIR / f"{stem}.provenance.json"
        prov = json.loads(prov_src.read_text(encoding="utf-8"))
        raw = out / "raw" / f"{doc_id}.pdf"
        shutil.copyfile(src, raw)
        sha = compute_file_sha256(raw)
        assert sha not in seen, f"{stem}: duplicate of a document already in the corpus"
        assert prov.get("sha256") in (None, sha), f"{stem}: sha256 differs from the provenance record"
        seen.add(sha)
        (out / "provenance" / "r3").mkdir(parents=True, exist_ok=True)
        prov_rel = f"provenance/r3/{doc_id}.provenance.json"
        shutil.copyfile(prov_src, out / prov_rel)
        ocr = CORPUS_STAGING_DIR / f"{stem}.ocr.txt"
        if ocr.exists():
            shutil.copyfile(ocr, out / "provenance" / "r3" / f"{doc_id}.ocr.txt")
        meta = extract(stem, doc_id, raw, out / "text")
        layer = str(meta.get("text_layer") or "native")
        if int(meta.get("char_count") or 0) < 200:
            layer = "none"
        docs.append(DocumentInventory.model_validate({
            "doc_id": doc_id, "title": prov.get("title") or prov.get("printed_title") or stem.split("/")[1],
            "class": cls, "issuer": issuer,
            "jurisdiction": {"level": "central" if code == "IN" else "state", "code": code, "discom": discom},
            "doc_number": prov.get("number"), "doc_date": ddate, "effective_date": eff,
            "effective_date_basis": basis, "effective_date_confidence": conf,
            "retrieved_url": prov.get("source_url"), "retrieved_via": "nav",
            "retrieved_at": prov.get("fetched_at") or datetime.now(UTC).isoformat(), "sha256": sha,
            "pages": int(prov.get("pages") or meta.get("page_count") or pdf_pages(raw)), "text_layer": layer,
            "status": status, "discoverability": "nav",
            "notes": f"Staged as 40_data/corpus_staging/{stem}.pdf. {note}".strip(),
            "verification_status": UNVERIFIED, "source_class": srcc, "provenance_file": prov_rel,
        }))
    docs.sort(key=lambda d: d.doc_id)
    save_manifest(CorpusManifest(corpus_version=CORPUS_VERSION, created_at=datetime.now(UTC).isoformat(),
                                 documents=docs), out / "MANIFEST.json")
    return docs


RANK = {"C1": "A3", "C2": "A4", "C3": "A1", "C4": "A2", "C5": "A6", "C6": "A5"}


def build_graph(out: Path, docs: list[DocumentInventory]) -> dict[str, Any]:
    """r2 graph + nodes and edges for the staged clauses. Returns a build report."""
    graph = json.loads((CORPUS_DIR / "graph" / "supersession.json").read_text(encoding="utf-8"))
    by_id = {d.doc_id: d for d in docs}
    stem_id = {stem.split("/")[1]: v[0] for stem, v in DOCS.items()}
    text = {d: (out / "text" / f"{d}.txt").read_text(encoding="utf-8") for d in by_id}
    report: dict[str, Any] = {"skipped_edges": [], "quote_checks": {}, "unresolved": []}

    def node(nid: str, ref: str, subject: str, snippet: str, legal: str | None = None) -> None:
        doc = by_id[nid.split("#")[0]]
        draft = doc.status == "draft_not_in_force"
        check = quote_check(text[doc.doc_id], snippet, out / "raw" / f"{doc.doc_id}.pdf")
        report["quote_checks"][nid] = check
        graph["nodes"][nid] = {
            "node_id": nid, "doc_id": doc.doc_id, "clause_ref": ref, "clause_text_snippet": norm(snippet),
            "subject": subject, "jurisdiction": doc.jurisdiction.model_dump(mode="json"),
            "effective_date": "UNKNOWN" if draft else doc.effective_date,
            "effective_date_basis": "E9" if draft else doc.effective_date_basis.value,
            "effective_date_confidence": "low" if draft else doc.effective_date_confidence.value,
            "status_at_snapshot": "unknown" if draft else "in_force",
            "authority_rank": RANK[doc.doc_class.value], "verification_status": UNVERIFIED,
            "legal_status": "draft_not_in_force" if draft else legal, "quote_check": check,
        }

    def edge(frm: str, to: str, rel: str, date: str, etype: str, conf: str, qdoc: str, q: str, note: str) -> None:
        if any(e["from"] == frm and e["to"] == to for e in graph["edges"]):
            return
        graph["edges"].append({
            "from": frm, "to": to, "relation": rel, "from_date": date, "confidence": conf,
            "evidence": {"type": etype, "quote_text": norm(q), "doc_id": qdoc},
            "verification_status": UNVERIFIED, "notes": note or None,
        })
        report["quote_checks"][f"edge:{frm}->{to}"] = quote_check(text[qdoc], q, out / "raw" / f"{qdoc}.pdf")

    staged = []
    for stem in DOCS:
        prov = json.loads((CORPUS_STAGING_DIR / f"{stem}.provenance.json").read_text(encoding="utf-8"))
        for c in prov.get("candidate_clauses", []):
            short = stem.split("/")[1]
            suffix, subject = NID[(short, c["clause_ref"])]
            nid = f"{stem_id[short]}#cl-{suffix}"
            node(nid, c["clause_ref"], subject, c["verbatim_quote"])
            staged.append((short, nid, c))
    for nid, ref, subject, q in EXTRA_NODES:
        node(nid, ref, subject, q)
        if nid in EXTRA_NODE_DATES:
            d, b, c = EXTRA_NODE_DATES[nid]
            graph["nodes"][nid].update(effective_date=d, effective_date_basis=b, effective_date_confidence=c)
    for short, nid, c in staged:
        sup = c.get("amends_or_supersedes")
        if not sup:
            continue
        if (short, c["clause_ref"]) in SKIP_EDGES:
            report["skipped_edges"].append({"node": nid, "reason": SKIP_EDGES[(short, c["clause_ref"])]})
            continue
        pred = PREDECESSOR_NID.get((sup["doc"], sup["clause_ref"]))
        if pred is None:
            report["unresolved"].append({"node": nid, "predecessor": [sup["doc"], sup["clause_ref"]]})
            continue
        if pred not in graph["nodes"]:  # create the predecessor node from the recorded evidence quote
            pdoc = pred.split("#")[0]
            in_later = sup.get("evidence_in_file", "").startswith(short) and pdoc == nid.split("#")[0]
            node(pred, sup["clause_ref"] + (" (2016 text as quoted in this order)" if in_later else ""),
                 graph["nodes"][nid]["subject"], sup["evidence_quote"], "quoted_predecessor" if in_later else None)
            if in_later:  # the old rule's own date is not in the corpus
                graph["nodes"][pred].update(effective_date="UNKNOWN", effective_date_basis="E9",
                                            effective_date_confidence="low")
        old_n, new_n = pred, nid
        d_pred, d_this = graph["nodes"][pred]["effective_date"], graph["nodes"][nid]["effective_date"]
        if "UNKNOWN" not in (d_pred, d_this) and d_pred > d_this:  # record kept on the superseded clause
            old_n, new_n = nid, pred
        new_node = graph["nodes"][new_n]
        explicit = EXPLICIT_EVIDENCE.get(new_n)
        edge(old_n, new_n, "superseded_by", new_node["effective_date"], "explicit" if explicit else "implicit",
             "medium", new_node["doc_id"], explicit or new_node["clause_text_snippet"],
             f"staging record: {short} {c['clause_ref']} amends/supersedes {sup['doc']} {sup['clause_ref']}")
    for f, t, rel, d, et, conf, qdoc, q, note in EXTRA_EDGES:
        edge(f, t, rel, d, et, conf, qdoc, q, note)
    # status at the snapshot date, for every node with an outgoing supersession edge in force
    for e in graph["edges"]:
        n = graph["nodes"][e["from"]]
        if e["relation"] == "superseded_by" and e["from_date"] not in (None, "UNKNOWN") and e["from_date"] <= SNAPSHOT:
            n["status_at_snapshot"] = "superseded"
    # the 2015 UP Regulations are superseded in full by the 2019 Regulations (Reg 1(3))
    graph["superseded_documents"]["UP-C3-001"] = "2019-01-04"
    edge("UP-C3-001#cl-5.1", "UP-C3-002#cl-1.3", "consolidated_into", "2019-01-04", "explicit", "medium", "UP-C3-002",
         EXPLICIT_EVIDENCE["UP-C3-002#cl-6.2"], "Backs superseded_documents[UP-C3-001]: whole-instrument supersession.")
    validate_graph(SupersessionGraph.model_validate(graph))
    (out / "graph" / "supersession.json").write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
                                                     encoding="utf-8", newline="\n")
    report["nodes"], report["edges"] = len(graph["nodes"]), len(graph["edges"])
    report["new_nodes"] = sum(1 for n in graph["nodes"].values() if n.get("verification_status") == UNVERIFIED)
    report["new_edges"] = sum(1 for e in graph["edges"] if e.get("verification_status") == UNVERIFIED)
    return report


def main() -> None:
    out = CORPUS_R3_DIR
    out.mkdir(parents=True, exist_ok=True)
    docs = build_documents(out)
    report = build_graph(out, docs)
    report["documents"] = len(docs)
    report["new_documents"] = sum(1 for d in docs if d.verification_status == UNVERIFIED)
    report["by_jurisdiction"] = {c: sum(1 for d in docs if d.doc_id.startswith(c))
                                 for c in ("IN", "MH", "RJ", "GJ", "KA", "TN", "DL", "UP")}
    (out / "BUILD_REPORT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    bad = {k: v for k, v in report["quote_checks"].items() if v == "not_found"}
    print(json.dumps({k: v for k, v in report.items() if k != "quote_checks"}, indent=1))
    print("quotes not found in r3 text:", json.dumps(bad, indent=1))
    import build_applicability_r3  # the graph copy brought r2's applicability.json; add the r3 predicates

    build_applicability_r3.main()


if __name__ == "__main__":
    main()
