import pytest

from src.api.exceptions import ExtractionError


def test_extract_entities(extractor, sample_ruling_text):
    result = extractor.extract(sample_ruling_text)
    assert "plaintiff" in result
    assert "defendant" in result
    assert "claim_amount" in result
    assert "case_number" in result
    assert result["case_number"] == "А40-12345/2024"


def test_extract_empty_text(extractor):
    with pytest.raises(ExtractionError):
        extractor.extract("")
