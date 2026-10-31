"""Unit tests for language auto-detection, Devanagari normalization, and translation engine."""

from unittest.mock import patch

from suryabench.corpus.translator import (
    clean_bilingual_ocr_text,
    detect_language,
    get_devanagari_ratio,
    is_predominantly_devanagari,
    translate_text_to_english,
)


def test_detect_language_english() -> None:
    """Test detecting pure English text."""
    en_text = (
        "In exercise of the powers conferred by Section 181 of the Electricity Act, 2003, "
        "the Rajasthan Electricity Regulatory Commission hereby makes the following Regulations."
    )
    assert detect_language(en_text) == "en"
    assert not is_predominantly_devanagari(en_text)
    assert get_devanagari_ratio(en_text) == 0.0


def test_detect_language_hindi() -> None:
    """Test detecting predominantly Hindi text."""
    hi_text = (
        "राजस्थान विद्युत विनियामक आयोग अधिसूचना जयपुर, अगस्त 28, 2023 "
        "विद्युत अधिनियम 2003 की धारा 61, 66, 86 सपठित धारा 181 द्वारा प्रदत्त शक्तियों का प्रयोग करते हुए।"
    )
    assert detect_language(hi_text) in ("hi", "bilingual_hi_en")
    assert is_predominantly_devanagari(hi_text)


def test_detect_language_marathi() -> None:
    """Test detecting Marathi text."""
    mr_text = (
        "महाराष्ट्र शासन राजपत्र असाधारण भाग चार-क महाराष्ट्र विद्युत नियामक आयोग "
        "सौर ऊर्जा निर्मिती संच आणि छतावरील अपारंपरिक ऊर्जा प्रणाली."
    )
    assert detect_language(mr_text) in ("mr", "bilingual_mr_en")
    assert is_predominantly_devanagari(mr_text)


def test_clean_bilingual_ocr_text() -> None:
    """Test cleaning noisy OCR ministerial headings into standard English."""
    sample_ocr = (
        "aTTla T(cErT / Government of India\n"
        "dl 3 desu N 3Gf le R / Ministry of New & Renewable Energy\n"
        "Block No. 14, CGO Complex, Lodhi Road, New Delhi"
    )
    cleaned = clean_bilingual_ocr_text(sample_ocr)
    assert "Government of India" in cleaned
    assert "Ministry of New & Renewable Energy (MNRE)" in cleaned
    assert "aTTla" not in cleaned


def test_clean_standalone_hindi_headings() -> None:
    """Test standardizing Devanagari gazette titles into English."""
    hindi_gazette = (
        "राजस्थान राजपत्र विशेषांक\n"
        "साधिकार प्रकाशित\n"
        "अधिसूचना"
    )
    cleaned = clean_bilingual_ocr_text(hindi_gazette)
    assert "Rajasthan Gazette" in cleaned
    assert "Extraordinary" in cleaned
    assert "Published by Authority" in cleaned
    assert "Notification" in cleaned


def test_translate_text_to_english_with_cache() -> None:
    """Test translating text utilizing cache or mock."""
    sample_text = "राजस्थान विद्युत विनियामक आयोग अधिसूचना"
    # Test with cache hit or mock
    with patch("suryabench.corpus.translator.load_cache") as mock_cache:
        mock_cache.return_value = {
            "d182bbcf9d69aa8fa958ec789a80fa9dc36f7de75ff89066601f0faeefc2666f": "Rajasthan Electricity Regulatory Commission Notification"
        }
        with patch("hashlib.sha256") as mock_sha:
            mock_sha.return_value.hexdigest.return_value = "d182bbcf9d69aa8fa958ec789a80fa9dc36f7de75ff89066601f0faeefc2666f"
            res = translate_text_to_english(sample_text)
            assert res == "Rajasthan Electricity Regulatory Commission Notification"
