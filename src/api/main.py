from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from src.api.dependencies import get_extractor, get_generator
from src.api.exceptions import DocForgeError
from src.core.config import DEFAULT_COURT, DEFAULT_LEGAL_ARTICLES
from src.engine.generator import DocumentGenerator
from src.engine.templates import AppealData, ClaimData, ContractData
from src.extractor.extractor import EntityExtractor
app = FastAPI(
    title="DocForge API",
    version="1.0.0",
    description="API для автоматической генерации юридических документов",
    docs_url="/docs",
    redoc_url="/redoc",
)
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
class RulingText(BaseModel):
    text: str = Field(..., min_length=1, description="Текст судебного решения")
class GenerateRequest(BaseModel):
    plaintiff: str
    defendant: str
    claim_amount: float
    case_number: str
    court_name: str = DEFAULT_COURT
@app.exception_handler(DocForgeError)
async def docforge_exception_handler(request: Request, exc: DocForgeError) -> JSONResponse:
    del request
    return JSONResponse(status_code=400, content={"error": str(exc)})
@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
@app.post("/extract", tags=["Extraction"])
async def extract(
    ruling: RulingText,
    extractor_svc: EntityExtractor = Depends(get_extractor),
) -> dict:
    return extractor_svc.extract(ruling.text)
@app.post("/generate/claim", tags=["Generation"])
async def generate_claim_endpoint(
    data: GenerateRequest,
    gen: DocumentGenerator = Depends(get_generator),
) -> Response:
    claim_data: ClaimData = {
        "court_name": data.court_name,
        "plaintiff": data.plaintiff,
        "defendant": data.defendant,
        "claim_amount": data.claim_amount,
        "case_number": data.case_number,
        "legal_articles": DEFAULT_LEGAL_ARTICLES,
        "attachments": ["Копия договора", "Расчёт задолженности", "Платёжное поручение"],
        "plaintiff_representative": "Генеральный директор",
    }
    doc_bytes = gen.generate("claim.j2", dict(claim_data))
    return Response(
        content=doc_bytes,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=iskovoe_zayavlenie.docx"},
    )
@app.post("/generate/appeal", tags=["Generation"])
async def generate_appeal_endpoint(
    data: GenerateRequest,
    gen: DocumentGenerator = Depends(get_generator),
) -> Response:
    appeal_data: AppealData = {
        "court_name": "Девятый арбитражный апелляционный суд",
        "plaintiff": data.plaintiff,
        "defendant": data.defendant,
        "claim_amount": data.claim_amount,
        "case_number": data.case_number,
        "appeal_arguments": "Суд первой инстанции неполно выяснил обстоятельства дела.",
        "legal_articles": "270, 272 АПК РФ",
        "attachments": ["Копия решения суда", "Квитанция об оплате госпошлины"],
        "plaintiff_representative": "Генеральный директор",
    }
    doc_bytes = gen.generate("appeal.j2", dict(appeal_data))
    return Response(
        content=doc_bytes,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=apellyatsionnaya_zhaloba.docx"},
    )
@app.post("/generate/contract", tags=["Generation"])
async def generate_contract_endpoint(
    data: GenerateRequest,
    gen: DocumentGenerator = Depends(get_generator),
) -> Response:
    contract_data: ContractData = {
        "customer": data.plaintiff,
        "contractor": data.defendant,
        "service_description": "Юридическое сопровождение деятельности Заказчика",
        "contract_amount": data.claim_amount,
        "contract_number": data.case_number,
        "contract_date": "01.07.2026",
        "customer_representative": "Генеральный директор",
        "contractor_representative": "Иванов И.И.",
    }
    doc_bytes = gen.generate("contract.j2", dict(contract_data))
    return Response(
        content=doc_bytes,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=dogovor.docx"},
    )
