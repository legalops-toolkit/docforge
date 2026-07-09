from src.api.exceptions import TemplateNotFoundError
import pytest


def test_generate_claim(generator):
    data = {
        "court_name": "Тест",
        "plaintiff": "ООО Тест",
        "defendant": "Иванов",
        "claim_amount": 100000,
        "case_number": "А40-1",
        "legal_articles": "309 ГК",
        "attachments": ["Док"],
        "plaintiff_representative": "Петров",
    }
    result = generator.generate("claim.j2", data)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_appeal(generator):
    data = {
        "court_name": "Тест",
        "plaintiff": "ООО Тест",
        "defendant": "Иванов",
        "claim_amount": 100000,
        "case_number": "А40-1",
        "appeal_arguments": "Доводы",
        "legal_articles": "270 АПК",
        "attachments": ["Док"],
        "plaintiff_representative": "Петров",
    }
    result = generator.generate("appeal.j2", data)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_contract(generator):
    data = {
        "customer": "ООО Тест",
        "contractor": "Иванов",
        "service_description": "Услуги",
        "contract_amount": 100000,
        "contract_number": "1",
        "contract_date": "01.01.2024",
        "customer_representative": "Петров",
        "contractor_representative": "Иванов",
    }
    result = generator.generate("contract.j2", data)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_missing_template_raises(generator):
    with pytest.raises(TemplateNotFoundError):
        generator.generate("does_not_exist.j2", {})
