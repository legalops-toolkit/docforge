"""Конфигурация шаблонов и данные по умолчанию."""

from typing import TypedDict


class ClaimData(TypedDict, total=False):
    court_name: str
    plaintiff: str
    defendant: str
    claim_amount: float
    case_number: str
    legal_articles: str
    attachments: list[str]
    plaintiff_representative: str
    date: str


class AppealData(TypedDict, total=False):
    court_name: str
    plaintiff: str
    defendant: str
    claim_amount: float
    case_number: str
    appeal_arguments: str
    legal_articles: str
    attachments: list[str]
    plaintiff_representative: str
    date: str


class ContractData(TypedDict, total=False):
    customer: str
    contractor: str
    service_description: str
    contract_amount: float
    contract_number: str
    contract_date: str
    customer_representative: str
    contractor_representative: str
    date: str
