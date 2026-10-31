"""Language detection, bilingual text handling, and translation for regulatory corpus documents."""

import hashlib
import json
import logging
import re
import urllib.request

from suryabench.paths import CORPUS_DIR

logger = logging.getLogger("translator")

CACHE_FILE = CORPUS_DIR / "translation_cache.json"

# Devanagari Unicode Range
DEVANAGARI_RANGE = ("\u0900", "\u097F")

# Known OCR corruptions of Hindi/Bilingual ministerial letterheads to clean English
OCR_BILINGUAL_LINE_PATTERNS = [
    # Lines with OCR noise followed by slash and English ministry/government names
    (r"(?im)^.*?(?:/|\b)\s*(?:Government of India|Govt\.? of India)\b.*$", "Government of India"),
    (
        r"(?im)^.*?(?:/|\b)\s*(?:Ministry of New\s*(?:&|and)\s*Renewable Energy(?:\s*\([A-Z]+\))?)\b.*$",
        "Ministry of New & Renewable Energy (MNRE)",
    ),
    (
        r"(?im)^.*?(?:/|\b)\s*(?:Grid Solar(?:\s*Power)?\s*Division)\b.*$",
        "Grid Solar Power Division",
    ),
    (
        r"(?im)^.*?(?:/|\b)\s*(?:Rooftop Solar\s*Division)\b.*$",
        "Rooftop Solar Division",
    ),
    (
        r"(?im)^.*?(?:/|\b)\s*(?:Ministry of Power)\b.*$",
        "Ministry of Power",
    ),
    (
        r"(?im)^.*?(?:/|\b)\s*(?:Solar Photovoltaic Division|SPV Division)\b.*$",
        "SPV Division",
    ),
]

# Standalone phrase replacements for Hindi/Devanagari administrative headers
STANDALONE_HINDI_REPLACEMENTS = [
    (r"भारत\s*सरकार", "Government of India"),
    (r"नवीन\s*और\s*नवीकरणीय\s*ऊर्जा\s*मंत्रालय", "Ministry of New & Renewable Energy (MNRE)"),
    (r"ग्रिड\s*सौर\s*ऊर्जा\s*प्रभाग", "Grid Solar Power Division"),
    (r"विद्युत\s*मंत्रालय", "Ministry of Power"),
    (r"राजस्थान\s*विद्युत\s*विनियामक\s*आयोग", "Rajasthan Electricity Regulatory Commission"),
    (r"महाराष्ट्र\s*विद्युत\s*नियामक\s*आयोग", "Maharashtra Electricity Regulatory Commission"),
    (r"महाारााष्ट्र\s*शाासन\s*रााजपत्र", "Maharashtra Government Gazette"),
    (r"महाराष्ट्र\s*शासन\s*राजपत्र", "Maharashtra Government Gazette"),
    (r"राजस्[्\s]*थान\s*राज-?पत्र", "Rajasthan Gazette"),
    (r"कार्यालय\s*ज्ञापन", "Office Memorandum"),
    (r"अधिसूचना", "Notification"),
    (r"विनियम", "Regulations"),
    (r"संशोधन", "Amendment"),
    (r"राजपत्र", "Gazette"),
    (r"विशषे\s*ाांक|विशेषांक", "Extraordinary"),
    (r"साधिकार\s*प्रकाशशत|साधिकार\s*प्रकाशित", "Published by Authority"),
    (r"भाग\s*[-–—]?\s*([०-९\d]+)", r"Part \1"),
    (r"वितरण\s*लाइसेंसधारी", "Distribution Licensee"),
    (r"नेट\s*मीटरिंग", "Net Metering"),
    (r"\bजनवरी\b|जनवरी(?=\s*\d)", "January"),
    (r"\bफरवरी\b|फरवरी(?=\s*\d)", "February"),
    (r"\bमार्च\b|मार्च(?=\s*\d)", "March"),
    (r"\bअप्रैल\b|अप्रैल(?=\s*\d)", "April"),
    (r"\bमई\b|मई(?=\s*\d)", "May"),
    (r"\bजून\b|जून(?=\s*\d)", "June"),
    (r"\bजुलाई\b|जुलाई(?=\s*\d)", "July"),
    (r"\bअगस्त\b|अगस्त(?=\s*\d)", "August"),
    (r"\bसितंबर\b|\bसितम्बर\b|सितंबर(?=\s*\d)|सितम्बर(?=\s*\d)", "September"),
    (r"\bअक्टूबर\b|\bअक्‍टूबर\b|अक्टूबर(?=\s*\d)|अक्‍टूबर(?=\s*\d)", "October"),
    (r"\bनवंबर\b|\bनवम्बर\b|नवंबर(?=\s*\d)|नवम्बर(?=\s*\d)", "November"),
    (r"\bदिसंबर\b|\bदिसम्बर\b|दिसंबर(?=\s*\d)|दिसम्बर(?=\s*\d)", "December"),
    # Running headers in Maharashtra & Rajasthan gazettes
    (
        r"असाधा+रा?ण\s+भा+ग\s+चा+रा?-क,\s*ऑगस्ट\s*२९,\s*२०२४/भा+द्रपद\s*७,\s*शाके\s*१९४६",
        "Extraordinary Part 4-C, August 29, 2024 / Bhadrapada 7, Saka 1946",
    ),
    (r"महाराष्ट्र\s*शासन\s*(?:राजपत्र|Gazette)?", "Maharashtra Government Gazette"),
    (
        r"भाग्?[्\s]*7.*?(29[0-9])",
        r"Part 7 Rajasthan Gazette, October 06, 2023 [Page \1]",
    ),
    (
        r"(29[0-9]).*?भाग्?[्\s]*7",
        r"Part 7 Rajasthan Gazette, October 06, 2023 [Page \1]",
    ),
    (
        r"राज[्\s]*य[्\s]*के[्\s]*[ररी]+[्\s]*य[्\s]*म[्\s]*[ुरु]+[्\s]*णालय[्\s,]*जयप[ुरु]+[्\s]*।?",
        "Government Central Press, Jaipur.",
    ),
    (
        r"राज[्\s]*य[्\s]*के[्\s]*ीय[्\s]*म[्\s]*[ुरु]+[्\s]*णालय,[्\s]*जयप[ुरु]+[्\s]*।?",
        "Government Central Press, Jaipur.",
    ),
    (
        r"राज्?\s*्य?\s*के\s*्?र\s*ीय\s*म\s*[ुरु]+\s*णालय,\s*जयपु?र\s*।?",
        "Government Central Press, Jaipur.",
    ),
    (
        r"राज्य\s*केन?्?द?्रीय\s*म[\u0930\u0941\s]*णालय\s*,?\s*जयप[\u0930\u0941\s]*",
        "Government Central Press, Jaipur.",
    ),
    (
        r"राज्य\s*केन?्?द?्रीय\s*म[ुरु]+णालय\s*,?\s*जयपु?र",
        "Government Central Press, Jaipur.",
    ),
    (r"\bPA\s*र\.े", "P.R. No."),
    (r"\b१016\b", "2016"),
]


def load_cache() -> dict[str, str]:
    """Load translation cache from disk."""
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            return {}
    return {}


def save_cache(cache: dict[str, str]) -> None:
    """Save translation cache to disk."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    except Exception as e:
        logger.warning("Failed to save translation cache: %s", e)


def get_devanagari_ratio(text: str) -> float:
    """Compute the ratio of Devanagari characters to total alphabetic characters."""
    if not text:
        return 0.0
    alpha_chars = [c for c in text if c.isalpha() or (DEVANAGARI_RANGE[0] <= c <= DEVANAGARI_RANGE[1])]
    if not alpha_chars:
        return 0.0
    dev_chars = [c for c in alpha_chars if DEVANAGARI_RANGE[0] <= c <= DEVANAGARI_RANGE[1]]
    return len(dev_chars) / len(alpha_chars)


def is_predominantly_devanagari(text: str, threshold: float = 0.20) -> bool:
    """Check if text has substantial Devanagari (Hindi/Marathi) content."""
    return get_devanagari_ratio(text) >= threshold


def detect_language(text: str) -> str:
    """Auto-detect the language of the text.

    Returns:
        ISO 639-1 language code: 'hi', 'mr', 'en', or other detected code.
    """
    if not text or len(text.strip()) < 10:
        return "en"

    # Fast script check for Devanagari
    dev_ratio = get_devanagari_ratio(text)
    if dev_ratio > 0.15:
        # Check for Marathi vs Hindi specific markers
        marathi_markers = ["आहे", "च्या", "आणि", "तील", "तून", "झालेली", "करण्यासाठी", "झाले", "म्हटले"]
        if any(marker in text for marker in marathi_markers):
            return "mr"
        try:
            import langdetect  # type: ignore[import-untyped]

            detected = langdetect.detect(text)
            if detected in {"hi", "mr"}:
                return str(detected)
        except Exception:
            pass
        return "hi"

    # For mostly Latin text, use langdetect
    try:
        import langdetect

        detected = langdetect.detect(text)
        return str(detected)
    except Exception:
        return "en"


def clean_bilingual_ocr_text(text: str) -> str:
    """Clean known OCR artifacts, mangled Hindi strings, and bilingual letterheads."""
    if not text:
        return ""

    # Normalize zero-width characters and duplicate vowel marks
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    text = re.sub(r"([\u093e-\u094d])\1+", r"\1", text)

    # 1. Clean entire lines that matched bilingual letterheads with OCR garbage
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        cleaned_line = line
        for pattern, replacement in OCR_BILINGUAL_LINE_PATTERNS:
            if re.search(pattern, cleaned_line):
                cleaned_line = replacement
                break
        cleaned_lines.append(cleaned_line)
    text = "\n".join(cleaned_lines)

    # 2. Clean specific standalone Hindi phrases
    for pattern, replacement in STANDALONE_HINDI_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 3. Clean specific OCR garbled strings
    specific_garbles = [
        (r"\bRdHRhR\b", "Government of India"),
        (r"\bRHRch\s*R\b", "Government of India"),
        (r"\bd3ieu3GeR\b", "Ministry of New & Renewable Energy (MNRE)"),
        (r"\bdl\s*3\s*desu\s*N\s*3Gf\s*le\s*R\b", "Ministry of New & Renewable Energy (MNRE)"),
        (r"\baTTla\s*T\(cErT\b", "Government of India"),
        (r",Ta,T\s*3#\{\s*dad,PitT\s*3dtdqTdq", "Ministry of New & Renewable Energy (MNRE)"),
        (r"fOg\s*B\}\{\s*5alf\s*qHTq", "Grid Solar Power Division"),
        (r"HRa\s*TFM\{", "Government of India"),
        (r"giNa\s*altER", "Government of India"),
        (r"HBiaTFMT\{", "Government of India"),
        (r"fBs\s*HITsat\s*WTFT", "Grid Solar Power Division"),
        (r"fBs\s*HITSd\s*WITH", "Grid Solar Power Division"),
        (r"fIts\s*d\(sd\s*miNT", "Grid Solar Power Division"),
        (r"adta3#Tadb6WfMnRtdqlav", "Ministry of New & Renewable Energy (MNRE)"),
        (r"Hdta3\{kHdMWfh\s*5atHqTaT", "Ministry of New & Renewable Energy (MNRE)"),
        (r"HzftH3\$\{nfb6wfHn#\s*;tqTHq", "Ministry of New & Renewable Energy (MNRE)"),
        (r"HRR中", "Government of India"),
        (r"Hd\s*HR中T", "Government of India"),
        (r"水\*水", ""),
    ]
    for pattern, replacement in specific_garbles:
        text = re.sub(pattern, replacement, text)

    return text


def translate_text_to_english(
    text: str,
    host: str = "http://127.0.0.1:11434",
    model: str = "qwen2.5:7b",
    timeout: float = 60.0,
) -> str:
    """Translate Hindi/Marathi regulatory text to English using local Ollama.

    Splits text into chunks if too long, utilizes disk caching, and preserves
    technical parameters and legal clause identifiers.
    """
    text = text.strip()
    if not text:
        return ""

    # Check cache first
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cache = load_cache()
    if text_hash in cache:
        return cache[text_hash]

    # If text is too long for a single prompt, split by paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1 and len(text) > 800:
        translated_paragraphs = []
        for p in paragraphs:
            if is_predominantly_devanagari(p, threshold=0.10):
                translated_paragraphs.append(
                    translate_text_to_english(p, host=host, model=model, timeout=timeout)
                )
            else:
                translated_paragraphs.append(clean_bilingual_ocr_text(p))
        joined = "\n\n".join(translated_paragraphs)
        cache[text_hash] = joined
        save_cache(cache)
        return joined

    prompt = (
        "You are an authoritative legal and regulatory translator for Indian government documents. "
        "Translate the following official gazette or regulatory text from Hindi or Marathi into clear, professional English. "
        "Strictly preserve all numbers, percentages, dates, statutory clause references, and legal terms. "
        "Output ONLY the English translation without any conversational preamble, commentary, or notes:\n\n"
        f"{text}"
    )

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_resp = data.get("response", "")
            translation = str(raw_resp).strip() if raw_resp else ""
            if translation:
                cache[text_hash] = translation
                save_cache(cache)
                return translation
    except Exception as e:
        logger.warning("Translation failed via %s: %s", host, e)

    # Fallback to cleaned text if translation service times out or fails
    return clean_bilingual_ocr_text(text)
