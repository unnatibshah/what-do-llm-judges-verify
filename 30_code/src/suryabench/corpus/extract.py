"""Enhanced text extraction pipeline with layout awareness, table preservation, and OCR fallback.

Protocol §4 requirement:
1. Extract text to corpus/text/<doc_id>.txt with provenance metadata recorded in <doc_id>.meta.json.
2. Layout awareness via pdfplumber: header/footer bounding-box margin stripping.
3. Tabular structure preservation: convert tables into GitHub-style Markdown tables.
4. OCR fallback via rapidocr-onnxruntime + pymupdf for scanned/empty pages.
"""

import importlib.metadata
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from suryabench.core.enums import TextLayer
from suryabench.core.exceptions import SuryaBenchError
from suryabench.corpus.manifest import compute_file_sha256
from suryabench.corpus.translator import (
    clean_bilingual_ocr_text,
    detect_language,
    is_predominantly_devanagari,
    translate_text_to_english,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionMetadata:
    """Provenance metadata for an extracted text document."""

    doc_id: str
    source_filename: str
    source_sha256: str
    tool: str
    tool_version: str
    text_layer: TextLayer
    extracted_at: str
    char_count: int
    page_count: int
    tables_extracted: int = 0
    detected_language: str = "en"
    translated: bool = False
    translation_engine: str | None = None


def clean_ocr_text(text: str) -> str:
    """Repair common whitespace concatenation and formatting artifacts in OCR output."""
    if not text:
        return ""

    import re

    # 0. Clean known OCR corruptions of bilingual letterheads
    text = clean_bilingual_ocr_text(text)

    # 1. Spacing after punctuation (colons, commas, semicolons)
    text = re.sub(r"([,;:])([^\s\d/])", r"\1 \2", text)
    text = re.sub(r"(:)(\d{1,2}[a-zA-Z])", r"\1 \2", text)
    text = re.sub(r"(,)(\d{4})", r"\1 \2", text)

    # 2. Number boundaries with letters
    text = re.sub(r"([a-zA-Z]{3,})(\d{4})\b", r"\1 \2", text)
    text = re.sub(r"\b(dated)(\d{2}\.)", r"\1 \2", text, flags=re.IGNORECASE)

    # 3. CamelCase transitions: lower to UPPER (e.g. SolarDivision -> Solar Division)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    # 4. Acronyms followed by capitalized word: e.g. OMNo -> OM No, SPVDivision -> SPV Division
    text = re.sub(
        r"\b(SPV|ALMM|CFA|MNRE|MERC|RERC|MSEDCL|JVVNL|AVVNL|DCR|OM)([A-Z][a-z])",
        r"\1 \2",
        text,
    )
    text = re.sub(
        r"([a-z])(SPV|ALMM|CFA|MNRE|MERC|RERC|MSEDCL|JVVNL|AVVNL|DCR)\b",
        r"\1 \2",
        text,
    )

    # 5. Common administrative compound words and fused phrases
    common_fused = [
        ("OFFICEMEMORANDUM", "OFFICE MEMORANDUM"),
        ("Governmentof", "Government of"),
        ("Ministryof", "Ministry of"),
        ("ofNew", "of New"),
        ("New&", "New &"),
        ("&Renewable", "& Renewable"),
        ("RenewableEnergy", "Renewable Energy"),
        ("LodiRoad", "Lodi Road"),
        ("NewDelhi", "New Delhi"),
        ("RooftopSolar", "Rooftop Solar"),
        ("SolarDivision", "Solar Division"),
        ("AkshayUrja", "Akshay Urja"),
        ("UrjaBhawan", "Urja Bhawan"),
        ("MuftBijli", "Muft Bijli"),
        ("BijliYojana", "Bijli Yojana"),
        ("Thisrefers", "This refers"),
        ("regardingnotification", "regarding notification"),
        ("toresidential", "to residential"),
        ("thecomponent", "the component"),
        ("Implementationof", "Implementation of"),
        ("Guidelinesfor", "Guidelines for"),
        ("solarlights", "solar lights"),
        ("solarstreet", "solar street"),
        ("efficiencythresholds", "efficiency thresholds"),
        ("agriculturalpumps", "agricultural pumps"),
        ("domesticcontent", "domestic content"),
        ("technicalfeasibility", "technical feasibility"),
        ("powerplants", "power plants"),
    ]
    for fused, separated in common_fused:
        text = re.sub(re.escape(fused), separated, text, flags=re.IGNORECASE)

    # 6. Trailing prepositions attached to previous word before an uppercase word
    text = re.sub(
        r"\b([a-zA-Z]{3,})(of|for|and|with|from|under|regarding)\s+([A-Z])",
        r"\1 \2 \3",
        text,
    )

    # 7. Normalise multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def format_table_as_markdown(table: list[list[str | None]]) -> str:
    """Convert a 2D grid of cell texts into a clean GitHub-style Markdown table."""
    if not table or not table[0]:
        return ""

    # Clean whitespace and newlines inside cells
    cleaned: list[list[str]] = []
    for row in table:
        cleaned_row = [
            (cell or "").replace("\n", " ").replace("\r", " ").strip() for cell in row
        ]
        if any(cleaned_row):  # Skip completely blank rows
            cleaned.append(cleaned_row)

    if not cleaned:
        return ""

    # Normalize row lengths to match max column count
    max_cols = max(len(row) for row in cleaned)
    if max_cols == 0:
        return ""

    normalized_rows: list[list[str]] = [r + [""] * (max_cols - len(r)) for r in cleaned]

    header = normalized_rows[0]
    data_start_idx = 1

    # Merge multi-tier headers if row 1 contains sub-column names for empty header cells
    if len(normalized_rows) > 1:
        row1 = normalized_rows[1]
        if any(not h and r for h, r in zip(header, row1, strict=False)):
            merged_header: list[str] = []
            last_super_header = ""
            for h, r in zip(header, row1, strict=False):
                if h:
                    last_super_header = h
                sub = r.strip()
                if last_super_header and sub and last_super_header != sub:
                    merged_header.append(f"{last_super_header} ({sub})")
                elif sub:
                    merged_header.append(sub)
                elif last_super_header:
                    merged_header.append(last_super_header)
                else:
                    merged_header.append("")
            header = merged_header
            data_start_idx = 2

    # If header has empty columns, provide fallback labels
    header_cells = [col if col else f"Col_{i + 1}" for i, col in enumerate(header)]

    lines = ["| " + " | ".join(header_cells) + " |"]
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    for data_row in normalized_rows[data_start_idx:]:
        lines.append("| " + " | ".join(data_row) + " |")

    return "\n".join(lines)


def _ocr_page_rapidocr(raw_file: Path, page_idx: int) -> str:
    """Perform OCR on a single page using pymupdf rendering and RapidOCR."""
    try:
        import pymupdf
        from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]

        doc = pymupdf.open(str(raw_file))  # type: ignore[no-untyped-call]
        if page_idx >= len(doc):
            return ""

        page = doc[page_idx]
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")  # type: ignore[no-untyped-call]

        ocr_engine = RapidOCR()
        ocr_result, _ = ocr_engine(img_bytes)

        if not ocr_result:
            return ""

        raw_lines = [item[1] for item in ocr_result if len(item) > 1 and item[1]]
        full_text = "\n".join(raw_lines)
        return clean_ocr_text(full_text)
    except Exception as e:
        logger.warning("OCR failed for %s page %d: %s", raw_file.name, page_idx, e)
        return ""


def _extract_pdf_plumber(
    raw_file: Path,
) -> tuple[str, int, int, TextLayer, str, bool]:
    """Extract text from PDF using layout-aware pdfplumber with inline table preservation.

    Returns:
        tuple of (extracted_text, page_count, tables_count, text_layer, detected_language, translated).
    """
    import pdfplumber

    extracted_pages: list[str] = []
    total_tables = 0
    used_ocr = False
    doc_translated = False
    page_languages: list[str] = []

    with pdfplumber.open(raw_file) as pdf:
        page_count = len(pdf.pages)
        if page_count == 0:
            # Some scanned PDF 1.3 files expose no page tree to pdfplumber; PyMuPDF still
            # renders them, so OCR every page it sees.
            import pymupdf

            n = len(pymupdf.open(str(raw_file)))  # type: ignore[no-untyped-call]
            pages = [_ocr_page_rapidocr(raw_file, i).strip() for i in range(n)]
            text = "\n\n".join(f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(pages) if t)
            layer = TextLayer.OCR if text else TextLayer.NONE
            return text, n, 0, layer, detect_language(text) if text else "en", False

        for page_idx, page in enumerate(pdf.pages):
            width = float(page.width)
            height = float(page.height)

            # 1. Detect tables
            found_tables = page.find_tables()
            page_elements: list[str] = []

            if found_tables:
                sorted_tables = sorted(found_tables, key=lambda t: float(t.bbox[1]))
                current_top = 0.0

                for t in sorted_tables:
                    t_top = float(t.bbox[1])
                    t_bottom = float(t.bbox[3])

                    # Text band strictly above this table
                    if t_top > current_top + 3:
                        above_box = (0, current_top, width, t_top)
                        above_text = (page.crop(above_box).extract_text() or "").strip()
                        if above_text:
                            page_elements.append(above_text)

                    # Formatted Markdown table
                    raw_table = t.extract()
                    md_table = format_table_as_markdown(raw_table)
                    if md_table:
                        page_elements.append(md_table)
                        total_tables += 1

                    current_top = max(current_top, t_bottom)

                # Text band below final table
                if current_top < height - 3:
                    below_box = (0, current_top, width, height)
                    below_text = (page.crop(below_box).extract_text() or "").strip()
                    if below_text:
                        page_elements.append(below_text)

            else:
                # No tables on this page: extract full text directly
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    page_elements.append(page_text)

            # 2. Check for scanned / empty page -> fallback to RapidOCR
            current_page_text = "\n\n".join(page_elements).strip()
            if len(current_page_text) < 30:
                ocr_text = _ocr_page_rapidocr(raw_file, page_idx)
                if len(ocr_text) > len(current_page_text):
                    current_page_text = ocr_text.strip()
                    used_ocr = True

            # 3. Language auto-detection, CID corruption recovery, and translation to English
            import re
            has_cid_corruption = len(re.findall(r"\(cid:\d+\)", current_page_text)) > 5
            page_lang = "mr" if has_cid_corruption else detect_language(current_page_text)
            page_languages.append(page_lang)

            is_devanagari = is_predominantly_devanagari(current_page_text, threshold=0.15) or page_lang in {"hi", "mr"}

            # SURYABENCH_TRANSLATE=0 keeps Hindi/Marathi pages as extracted: machine translation
            # would put model-written text into an authentic corpus.
            translate = os.environ.get("SURYABENCH_TRANSLATE", "1") != "0"
            if (is_devanagari or has_cid_corruption) and not translate:
                current_page_text = f"[Untranslated {page_lang} page]\n{current_page_text}"
            elif is_devanagari or has_cid_corruption:
                translated_page = translate_text_to_english(current_page_text)
                if translated_page and translated_page.strip():
                    lang_label = (
                        "Hindi"
                        if page_lang == "hi"
                        else ("Marathi" if (page_lang == "mr" or has_cid_corruption) else page_lang.upper())
                    )
                    current_page_text = f"[Translated from {lang_label} to English]\n{translated_page}"
                    doc_translated = True
            else:
                current_page_text = clean_bilingual_ocr_text(current_page_text)

            if current_page_text:
                extracted_pages.append(
                    f"--- Page {page_idx + 1} ---\n{current_page_text}"
                )

    full_text = "\n\n".join(extracted_pages).strip()

    if len(full_text) < 20 and page_count > 0:
        layer = TextLayer.NONE
    elif used_ocr:
        layer = TextLayer.OCR
    else:
        layer = TextLayer.NATIVE

    # Compute overall document language
    non_en = [lang for lang in page_languages if lang != "en"]
    if not non_en:
        doc_lang = "en"
    elif len(non_en) == len(page_languages):
        doc_lang = non_en[0]
    else:
        doc_lang = f"bilingual_{non_en[0]}_en"

    return full_text, page_count, total_tables, layer, doc_lang, doc_translated


def _extract_pdf_text_fallback(
    raw_file: Path,
) -> tuple[str, int, int, TextLayer, str, bool]:
    """Fallback text extractor using pypdf if pdfplumber fails."""
    import pypdf

    reader = pypdf.PdfReader(str(raw_file))
    page_count = len(reader.pages)
    pages_text: list[str] = []
    doc_translated = False

    for page in reader.pages:
        page_text = page.extract_text() or ""
        page_text = clean_bilingual_ocr_text(page_text.strip())
        pages_text.append(page_text)

    full_text = "\n\n".join(pages_text).strip()
    doc_lang = detect_language(full_text)
    if is_predominantly_devanagari(full_text, threshold=0.15) or doc_lang in {"hi", "mr"}:
        full_text = translate_text_to_english(full_text)
        doc_translated = True

    layer = TextLayer.NONE if len(full_text) < 20 and page_count > 0 else TextLayer.NATIVE

    return full_text, page_count, 0, layer, doc_lang, doc_translated


def extract_document(
    raw_file: Path,
    doc_id: str,
    text_dir: Path,
    forced_text_layer: TextLayer | None = None,
) -> tuple[Path, Path]:
    """Extract text from a raw document with layout, table, OCR, and translation awareness.

    Args:
        raw_file: Path to source file in raw corpus directory.
        doc_id: Unique document ID.
        text_dir: Directory where text and meta JSON will be stored.
        forced_text_layer: Manually specify TextLayer (e.g. if known to be OCR).

    Returns:
        tuple of (text_file_path, meta_file_path).
    """
    if not raw_file.exists():
        raise SuryaBenchError(f"Raw source file does not exist: '{raw_file}'")

    text_dir.mkdir(parents=True, exist_ok=True)
    suffix = raw_file.suffix.lower()

    source_sha256 = compute_file_sha256(raw_file)
    extracted_text: str = ""
    page_count: int = 1
    tables_extracted: int = 0
    tool: str = "native"
    tool_version: str = "1.0.0"
    text_layer: TextLayer = TextLayer.NATIVE
    detected_language: str = "en"
    translated: bool = False
    translation_engine: str | None = None

    if suffix == ".pdf":
        try:
            tool_version = importlib.metadata.version("pdfplumber")
            tool = "pdfplumber+rapidocr"
            (
                extracted_text,
                page_count,
                tables_extracted,
                detected_layer,
                detected_language,
                translated,
            ) = _extract_pdf_plumber(raw_file)
            text_layer = forced_text_layer or detected_layer
            if translated:
                translation_engine = "ollama:qwen2.5:7b+bilingual_cache"
        except Exception as e:
            logger.warning(
                "pdfplumber extraction failed for %s, falling back to pypdf: %s", raw_file.name, e
            )
            tool = "pypdf_fallback"
            try:
                tool_version = importlib.metadata.version("pypdf")
            except Exception:
                tool_version = "unknown"
            (
                extracted_text,
                page_count,
                tables_extracted,
                detected_layer,
                detected_language,
                translated,
            ) = _extract_pdf_text_fallback(raw_file)
            text_layer = forced_text_layer or detected_layer
            if translated:
                translation_engine = "ollama:qwen2.5:7b+bilingual_cache"

    elif suffix in {".txt", ".md"}:
        raw_text = raw_file.read_text(encoding="utf-8")
        extracted_text = clean_bilingual_ocr_text(raw_text)
        tool = "native_text_reader"
        tool_version = "python_builtin"
        text_layer = forced_text_layer or TextLayer.NATIVE
        page_count = 1
        detected_language = detect_language(extracted_text)
        if is_predominantly_devanagari(extracted_text, threshold=0.15) or detected_language in {"hi", "mr"}:
            extracted_text = translate_text_to_english(extracted_text)
            translated = True
            translation_engine = "ollama:qwen2.5:7b+bilingual_cache"
    else:
        try:
            raw_text = raw_file.read_text(encoding="utf-8", errors="replace")
            extracted_text = clean_bilingual_ocr_text(raw_text)
            tool = "utf8_fallback"
            tool_version = "python_builtin"
            text_layer = forced_text_layer or TextLayer.NATIVE
            detected_language = detect_language(extracted_text)
        except Exception as e:
            raise SuryaBenchError(
                f"Unsupported file format for extraction: '{raw_file.name}' ({e})"
            ) from e

    # Write text file
    text_file = text_dir / f"{doc_id}.txt"
    text_file.write_text(extracted_text, encoding="utf-8", newline="\n")

    # Build and write metadata
    meta = ExtractionMetadata(
        doc_id=doc_id,
        source_filename=raw_file.name,
        source_sha256=source_sha256,
        tool=tool,
        tool_version=tool_version,
        text_layer=text_layer,
        extracted_at=datetime.now(UTC).isoformat(),
        char_count=len(extracted_text),
        page_count=page_count,
        tables_extracted=tables_extracted,
        detected_language=detected_language,
        translated=translated,
        translation_engine=translation_engine,
    )

    meta_file = text_dir / f"{doc_id}.meta.json"
    with open(meta_file, "w", encoding="utf-8", newline="\n") as f:
        json.dump(asdict(meta), f, indent=2)

    return text_file, meta_file
