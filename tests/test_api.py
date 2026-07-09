from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_endpoint():
    response = client.post("/extract", json={"text": "ООО Ромашка против Иванова"})
    assert response.status_code == 200
    data = response.json()
    assert "plaintiff" in data


def test_extract_endpoint_empty_text_returns_400():
    response = client.post("/extract", json={"text": ""})
    assert response.status_code in (400, 422)


def test_generate_claim_endpoint():
    response = client.post(
        "/generate/claim",
        json={
            "plaintiff": "ООО Тест",
            "defendant": "Иванов",
            "claim_amount": 100000,
            "case_number": "А40-1",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_generate_appeal_endpoint():
    response = client.post(
        "/generate/appeal",
        json={
            "plaintiff": "ООО Тест",
            "defendant": "Иванов",
            "claim_amount": 100000,
            "case_number": "А40-1",
        },
    )
    assert response.status_code == 200


def test_generate_contract_endpoint():
    response = client.post(
        "/generate/contract",
        json={
            "plaintiff": "ООО Тест",
            "defendant": "Иванов",
            "claim_amount": 100000,
            "case_number": "А40-1",
        },
    )
    assert response.status_code == 200
