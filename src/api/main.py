"""Точка входа FastAPI приложения DocForge."""

import logging
import time
import tomllib
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.dependencies import get_extractor, get_generator
from src.api.security import rate_limit_key, verify_api_key
from src.core.config import DEFAULT_COURT, DEFAULT_LEGAL_ARTICLES, settings
from src.core.exceptions import DocForgeError
from src.core.logging_config import configure_logging
from src.engine.generator import DocumentGenerator
from src.engine.templates import AppealData, ClaimData, ContractData
from src.extractor.extractor import EntityExtractor, ExtractionResult

configure_logging()
logger = logging.getLogger(__name__)


def _resolve_version() -> str:
    """Версия читается напрямую из pyproject.toml, а не через
    importlib.metadata — пакет docforge никогда не ставится через
    `pip install .` в рантайм-образе (Dockerfile ставит только
    requirements.txt), поэтому метаданных пакета там просто нет."""
    pyproject_path = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
        logger.warning("Не удалось прочитать версию из pyproject.toml, использую 0.0.0-dev")
        return "0.0.0-dev"


APP_VERSION = _resolve_version()

# Rate limiting: ключ — API-ключ клиента, если он передан (X-API-Key),
# иначе IP. Значение лимита конфигурируется через DOCFORGE_RATE_LIMIT.
limiter = Limiter(key_func=rate_limit_key, default_limits=[settings.rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201 - FastAPI lifespan signature
    logger.info(
        "DocForge запускается | env=%s | version=%s | auth_enabled=%s | rate_limit=%s",
        settings.environment,
        APP_VERSION,
        settings.auth_enabled,
        settings.rate_limit,
    )
    yield
    logger.info("DocForge останавливается")


app = FastAPI(
    title="DocForge API",
    version=APP_VERSION,
    description=(
        "API для автоматической генерации юридических документов "
        "(исковое заявление, апелляционная жалоба, договор) и извлечения "
        "сущностей из текста судебных решений."
    ),
    contact={"name": "DocForge contributors", "url": "https://github.com/legalops-toolkit/docforge"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
# Подавление ниже: обработчик из slowapi объявлен как принимающий конкретный
# RateLimitExceeded, а starlette ждёт обработчик, принимающий любой Exception.
# Сузить сигнатуру нельзя (код чужой), расширить — значит потерять типизацию;
# несоответствие безопасное, потому что starlette зовёт обработчик только для
# того класса исключения, под который он зарегистрирован.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Дефолт для полей *_representative, если запрос его не передал. Раньше
# "Генеральный директор" было продублировано как строковый литерал в трёх
# местах ниже (claim/appeal/contract) плюс отдельный, ничем не обоснованный
# "Иванов И.И." для contractor_representative — теперь один источник правды.
DEFAULT_REPRESENTATIVE_TITLE = "Генеральный директор"


def _docx_response(doc_bytes: bytes, filename: str) -> Response:
    """Единая точка сборки HTTP-ответа с сгенерированным .docx.

    Раньше эта же связка content/media_type/Content-Disposition была
    скопирована в трёх generate-эндпоинтах — любое изменение (например,
    добавить Content-Length или поменять схему именования файла) пришлось
    бы вносить трижды и легко забыть одну из копий.
    """
    return Response(
        content=doc_bytes,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ──────────────────────────────────────────────────────────────────────────
# Middleware: лимит размера тела запроса + структурированное логирование запросов
# ──────────────────────────────────────────────────────────────────────────


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > settings.max_request_body_bytes:
        logger.warning(
            "Отклонён запрос %s: тело %s байт превышает лимит %s",
            request.url.path,
            content_length,
            settings.max_request_body_bytes,
        )
        return JSONResponse(status_code=413, content={"error": "Request body too large"})
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ──────────────────────────────────────────────────────────────────────────
# Схемы запросов/ответов
# ──────────────────────────────────────────────────────────────────────────


class RulingText(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_extraction_text_length,
        description="Текст судебного решения",
        examples=["Арбитражный суд города Москвы рассмотрел дело № А40-12345/2024..."],
    )


class GenerateRequest(BaseModel):
    """Данные для искового заявления и апелляционной жалобы — оба документа
    описывают судебный спор, поэтому используют одну и ту же процессуальную
    терминологию (истец/ответчик)."""

    plaintiff: str = Field(..., min_length=1, max_length=500, examples=["ООО «Ромашка»"])
    defendant: str = Field(..., min_length=1, max_length=500, examples=["Иванов Иван Иванович"])
    claim_amount: float = Field(..., gt=0, examples=[500000])
    case_number: str = Field(..., min_length=1, max_length=100, examples=["А40-12345/2024"])
    court_name: str = Field(default=DEFAULT_COURT, max_length=500, examples=[DEFAULT_COURT])


class ContractGenerateRequest(BaseModel):
    """Данные для договора оказания услуг.

    Раньше договор генерировался из той же GenerateRequest, что и иск/
    апелляция, с полями plaintiff/defendant — в договоре нет ни истца, ни
    суда, только заказчик и исполнитель, поэтому старая схема требовала
    молчаливого ремаппинга (plaintiff -> customer) прямо в теле эндпоинта.
    Отдельная схема называет вещи так, как их называет сам документ.
    """

    customer: str = Field(..., min_length=1, max_length=500, examples=["ООО «Ромашка»"])
    contractor: str = Field(..., min_length=1, max_length=500, examples=["ИП Иванов Иван Иванович"])
    contract_amount: float = Field(..., gt=0, examples=[500000])
    contract_number: str = Field(..., min_length=1, max_length=100, examples=["Д-2026-014"])
    service_description: str = Field(
        default="Юридическое сопровождение деятельности Заказчика",
        max_length=1000,
        examples=["Юридическое сопровождение деятельности Заказчика"],
    )
    customer_representative: str = Field(
        default=DEFAULT_REPRESENTATIVE_TITLE, max_length=300, examples=[DEFAULT_REPRESENTATIVE_TITLE]
    )
    contractor_representative: str = Field(
        default=DEFAULT_REPRESENTATIVE_TITLE, max_length=300, examples=[DEFAULT_REPRESENTATIVE_TITLE]
    )


class ErrorResponse(BaseModel):
    error: str = Field(..., examples=["Шаблон claim.j2 не найден"])


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class VersionResponse(BaseModel):
    version: str = Field(..., examples=["1.0.0"])
    environment: str = Field(..., examples=["production"])


ERROR_RESPONSES: dict[int | str, dict] = {
    400: {"model": ErrorResponse, "description": "Доменная ошибка (шаблон/генерация/извлечение)"},
    401: {"description": "Неверный или отсутствующий X-API-Key (если аутентификация включена)"},
    422: {"description": "Ошибка валидации входных данных"},
    429: {"description": "Превышен лимит запросов (rate limit)"},
}


# ──────────────────────────────────────────────────────────────────────────
# Обработчики ошибок — никогда не отдаём наружу трейсбек
# ──────────────────────────────────────────────────────────────────────────


@app.exception_handler(DocForgeError)
async def docforge_exception_handler(request: Request, exc: DocForgeError) -> JSONResponse:
    logger.warning("DocForgeError на %s: %s", request.url.path, exc)
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Полный traceback уходит только в лог. Раньше наружу отдавался str(exc)
    # везде, где environment != "production" — а дефолт как раз
    # "development", и то же значение прописано в docker-compose.yml, то
    # есть эталонный деплой из репозитория утекал бы по умолчанию. Теперь
    # ответ всегда generic, независимо от environment: для локальной
    # отладки логов достаточно, HTTP-тело — не место для деталей исключения.
    logger.exception("Необработанная ошибка на %s", request.url.path)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Internal server error"})


# ──────────────────────────────────────────────────────────────────────────
# Эндпоинты
# ──────────────────────────────────────────────────────────────────────────


@app.get("/health", tags=["Health"], response_model=HealthResponse, summary="Проверка живости сервиса")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/version", tags=["Health"], response_model=VersionResponse, summary="Версия и окружение сервиса")
async def get_version() -> VersionResponse:
    return VersionResponse(version=APP_VERSION, environment=settings.environment)


@app.post(
    "/extract",
    tags=["Extraction"],
    response_model=ExtractionResult,
    responses=ERROR_RESPONSES,
    summary="Извлечь сущности из текста судебного решения",
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(settings.rate_limit)
async def extract(
    request: Request,
    ruling: RulingText,
    extractor_svc: EntityExtractor = Depends(get_extractor),
) -> ExtractionResult:
    logger.info("POST /extract, длина текста=%d", len(ruling.text))
    return extractor_svc.extract(ruling.text)


@app.post(
    "/generate/claim",
    tags=["Generation"],
    responses={**ERROR_RESPONSES, 200: {"content": {DOCX_MEDIA_TYPE: {}}, "description": "Сгенерированный .docx"}},
    summary="Сгенерировать исковое заявление",
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(settings.rate_limit)
async def generate_claim_endpoint(
    request: Request,
    data: GenerateRequest,
    gen: DocumentGenerator = Depends(get_generator),
) -> Response:
    logger.info("POST /generate/claim, case_number=%s", data.case_number)
    claim_data: ClaimData = {
        "court_name": data.court_name,
        "plaintiff": data.plaintiff,
        "defendant": data.defendant,
        "claim_amount": data.claim_amount,
        "case_number": data.case_number,
        "legal_articles": DEFAULT_LEGAL_ARTICLES,
        "attachments": ["Копия договора", "Расчёт задолженности", "Платёжное поручение"],
        "plaintiff_representative": DEFAULT_REPRESENTATIVE_TITLE,
    }
    doc_bytes = gen.generate("claim.j2", dict(claim_data))
    return _docx_response(doc_bytes, "iskovoe_zayavlenie.docx")


@app.post(
    "/generate/appeal",
    tags=["Generation"],
    responses={**ERROR_RESPONSES, 200: {"content": {DOCX_MEDIA_TYPE: {}}, "description": "Сгенерированный .docx"}},
    summary="Сгенерировать апелляционную жалобу",
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(settings.rate_limit)
async def generate_appeal_endpoint(
    request: Request,
    data: GenerateRequest,
    gen: DocumentGenerator = Depends(get_generator),
) -> Response:
    logger.info("POST /generate/appeal, case_number=%s", data.case_number)
    appeal_data: AppealData = {
        "court_name": "Девятый арбитражный апелляционный суд",
        "plaintiff": data.plaintiff,
        "defendant": data.defendant,
        "claim_amount": data.claim_amount,
        "case_number": data.case_number,
        "appeal_arguments": "Суд первой инстанции неполно выяснил обстоятельства дела.",
        "legal_articles": "270, 272 АПК РФ",
        "attachments": ["Копия решения суда", "Квитанция об оплате госпошлины"],
        "plaintiff_representative": DEFAULT_REPRESENTATIVE_TITLE,
    }
    doc_bytes = gen.generate("appeal.j2", dict(appeal_data))
    return _docx_response(doc_bytes, "apellyatsionnaya_zhaloba.docx")


@app.post(
    "/generate/contract",
    tags=["Generation"],
    responses={**ERROR_RESPONSES, 200: {"content": {DOCX_MEDIA_TYPE: {}}, "description": "Сгенерированный .docx"}},
    summary="Сгенерировать договор оказания услуг",
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(settings.rate_limit)
async def generate_contract_endpoint(
    request: Request,
    data: ContractGenerateRequest,
    gen: DocumentGenerator = Depends(get_generator),
) -> Response:
    logger.info("POST /generate/contract, contract_number=%s", data.contract_number)
    contract_data: ContractData = {
        "customer": data.customer,
        "contractor": data.contractor,
        "service_description": data.service_description,
        "contract_amount": data.contract_amount,
        "contract_number": data.contract_number,
        # Раньше здесь был захардкожен литерал "01.07.2026" — каждый
        # сгенерированный договор получал одну и ту же (к тому же будущую)
        # дату независимо от того, когда его реально сформировали.
        "contract_date": date.today().strftime("%d.%m.%Y"),
        "customer_representative": data.customer_representative,
        # Раньше здесь был захардкожен "Иванов И.И." — случайное имя,
        # никак не связанное с реальным контрагентом.
        "contractor_representative": data.contractor_representative,
    }
    doc_bytes = gen.generate("contract.j2", dict(contract_data))
    return _docx_response(doc_bytes, "dogovor.docx")
