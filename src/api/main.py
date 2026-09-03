"""FastAPI-приложение DocForge.

Слой api не содержит бизнес-логики генерации/извлечения — только HTTP-обвязку
(схемы запросов, сборку данных для шаблона, коды ответов, middleware).
Сама логика — в engine/ и extractor/, сюда попадает через DI (dependencies.py).
"""

import logging
import re
import tomllib
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.dependencies import get_extractor, get_generator
from src.api.security import rate_limit_key, verify_api_key
from src.core.config import ROOT_DIR, settings
from src.core.exceptions import DocForgeError, ExtractionError
from src.core.logging_config import configure_logging
from src.engine.generator import DocumentGenerator
from src.engine.templates import AppealData, ClaimData, ContractData
from src.extractor.extractor import EntityExtractor

configure_logging()
logger = logging.getLogger(__name__)

# Суд, который подставляется в апелляционную жалобу, если клиент не указал
# свой в запросе — по умолчанию берём типовой апелляционный арбитражный суд.
DEFAULT_APPEAL_COURT = "Девятый арбитражный апелляционный суд"

DEFAULT_ATTACHMENTS = [
    "Квитанция об уплате государственной пошлины",
    "Копия искового заявления для ответчика",
    "Документы, подтверждающие обстоятельства дела",
]

DEFAULT_APPEAL_ARGUMENTS = (
    "Заявитель не согласен с решением суда первой инстанции и полагает его "
    "подлежащим отмене как вынесенное с нарушением норм материального и "
    "процессуального права."
)

DEFAULT_SERVICE_DESCRIPTION = "Оказание услуг согласно условиям настоящего Договора"

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---------------------------------------------------------------------------
# Версия — читается напрямую из pyproject.toml, а не через
# importlib.metadata.version("docforge"): пакет не ставится через
# `pip install .` в рантайм-образе (см. CHANGELOG), поэтому метаданные
# дистрибутива там попросту отсутствуют.
# ---------------------------------------------------------------------------
def _read_version() -> str:
    try:
        with open(ROOT_DIR / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception:  # noqa: BLE001 — версия не критична для работы сервиса
        logger.warning("Не удалось прочитать версию из pyproject.toml", exc_info=True)
        return "0.0.0-dev"


APP_VERSION = _read_version()

limiter = Limiter(key_func=rate_limit_key, default_limits=[settings.rate_limit])

app = FastAPI(
    title="DocForge",
    description="API для генерации юридических документов и извлечения сущностей из текста судебных решений.",
    version=APP_VERSION,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Middleware: лимит размера тела запроса.
#
# Без него злоумышленник может прислать многомегабайтный текст на /extract и
# нагрузить NER-пайплайн. Проверяем Content-Length там, где он есть — это
# дешёвая защита от очевидного случая; настоящий стриминг-лимит на уровне
# ASGI-сервера конфигурируется отдельно и этим middleware не заменяется.
# ---------------------------------------------------------------------------
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                length = None
            if length is not None and length > settings.max_request_body_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"error": "Request body too large"},
                )
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)


# ---------------------------------------------------------------------------
# Обработчики исключений.
#
# ExtractionError — вина клиента (пустой/непригодный текст) -> 422.
# Остальные DocForgeError (генерация, шаблоны) — вина сервера/конфигурации,
# но их текст уже безопасен для показа (см. engine/generator.py) -> 500.
# Любое НЕ-DocForgeError исключение — потенциально содержит секреты
# (строки подключения, внутренние пути и т.п.), поэтому наружу уходит
# только generic-сообщение, а полная трассировка — в лог.
# ---------------------------------------------------------------------------
@app.exception_handler(ExtractionError)
async def extraction_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"error": str(exc)})


@app.exception_handler(DocForgeError)
async def docforge_error_handler(request: Request, exc: DocForgeError) -> JSONResponse:
    logger.warning("DocForge domain error: %s", exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Схемы запросов.
# ---------------------------------------------------------------------------
class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=settings.max_extraction_text_length)


class GenerateClaimRequest(BaseModel):
    plaintiff: str = Field(min_length=1)
    defendant: str = Field(min_length=1)
    claim_amount: int = Field(gt=0)
    case_number: str = Field(min_length=1)
    plaintiff_representative: str = ""


class GenerateAppealRequest(BaseModel):
    plaintiff: str = Field(min_length=1)
    defendant: str = Field(min_length=1)
    claim_amount: int = Field(gt=0)
    case_number: str = Field(min_length=1)
    court: str = ""
    plaintiff_representative: str = ""
    appeal_arguments: str = ""


class GenerateContractRequest(BaseModel):
    customer: str = Field(min_length=1)
    contractor: str = Field(min_length=1)
    contract_amount: int = Field(gt=0)
    contract_number: str = Field(min_length=1)
    customer_representative: str = ""
    contractor_representative: str = ""
    service_description: str = ""


# ---------------------------------------------------------------------------
# Эндпоинты.
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
async def version() -> dict[str, str]:
    return {"version": APP_VERSION, "environment": settings.environment}


@app.post("/extract", dependencies=[Depends(verify_api_key)])
@limiter.limit(settings.rate_limit)
async def extract(
    request: Request,
    body: ExtractRequest,
    extractor: Annotated[EntityExtractor, Depends(get_extractor)],
) -> dict[str, str]:
    result = extractor.extract(body.text)
    return {
        "court": result.court,
        "judge": result.judge,
        "case_number": result.case_number,
        "plaintiff": result.plaintiff,
        "defendant": result.defendant,
        "claim_amount": result.claim_amount,
    }


@app.post("/generate/claim", dependencies=[Depends(verify_api_key)])
@limiter.limit(settings.rate_limit)
async def generate_claim(
    request: Request,
    body: GenerateClaimRequest,
    generator: Annotated[DocumentGenerator, Depends(get_generator)],
) -> Response:
    data: ClaimData = {
        "court_name": settings.default_court,
        "plaintiff": body.plaintiff,
        "defendant": body.defendant,
        "claim_amount": body.claim_amount,
        "case_number": body.case_number,
        "legal_articles": settings.default_legal_articles,
        "attachments": DEFAULT_ATTACHMENTS,
        "plaintiff_representative": body.plaintiff_representative,
    }
    content = generator.generate("claim.j2", data)
    return _docx_response(content, f"claim_{body.case_number}.docx")


@app.post("/generate/appeal", dependencies=[Depends(verify_api_key)])
@limiter.limit(settings.rate_limit)
async def generate_appeal(
    request: Request,
    body: GenerateAppealRequest,
    generator: Annotated[DocumentGenerator, Depends(get_generator)],
) -> Response:
    data: AppealData = {
        "court_name": body.court or DEFAULT_APPEAL_COURT,
        "plaintiff": body.plaintiff,
        "defendant": body.defendant,
        "claim_amount": body.claim_amount,
        "case_number": body.case_number,
        "appeal_arguments": body.appeal_arguments or DEFAULT_APPEAL_ARGUMENTS,
        "legal_articles": settings.default_legal_articles,
        "attachments": DEFAULT_ATTACHMENTS,
        "plaintiff_representative": body.plaintiff_representative,
    }
    content = generator.generate("appeal.j2", data)
    return _docx_response(content, f"appeal_{body.case_number}.docx")


@app.post("/generate/contract", dependencies=[Depends(verify_api_key)])
@limiter.limit(settings.rate_limit)
async def generate_contract(
    request: Request,
    body: GenerateContractRequest,
    generator: Annotated[DocumentGenerator, Depends(get_generator)],
) -> Response:
    data: ContractData = {
        "customer": body.customer,
        "contractor": body.contractor,
        "service_description": body.service_description or DEFAULT_SERVICE_DESCRIPTION,
        "contract_amount": body.contract_amount,
        "contract_number": body.contract_number,
        # Дата всегда берётся на момент генерации, а не хардкодится (регрессия из CHANGELOG).
        "contract_date": date.today().strftime("%d.%m.%Y"),
        "customer_representative": body.customer_representative,
        "contractor_representative": body.contractor_representative,
    }
    content = generator.generate("contract.j2", data)
    return _docx_response(content, f"contract_{body.contract_number}.docx")


def _content_disposition(filename: str) -> str:
    """Content-Disposition с юникодным именем файла (RFC 6266).

    HTTP-заголовки кодируются как latin-1 — номера дел вида «А40-1» содержат
    кириллицу, которая в latin-1 не существует, и голый `filename="..."`
    с такой строкой валит запрос с UnicodeEncodeError ещё до отправки
    ответа. Поэтому `filename=` — ASCII-заглушка (кириллица заменена на
    «_», нужна только старым клиентам, которые не понимают filename*),
    а настоящее, читаемое имя файла — в `filename*=UTF-8''...`, которое
    использует любой современный браузер.
    """
    ascii_fallback = re.sub(r"[^\x20-\x7e]", "_", filename) or "document.docx"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


def _docx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": _content_disposition(filename)},
    )
