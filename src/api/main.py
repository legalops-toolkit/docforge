from fastapi import FastAPI
from pydantic import BaseModel
app = FastAPI(
    title="DocForge API",
    version="1.0.0",
    description="API для генерации юридических документов",
    docs_url="/docs",
    redoc_url="/redoc"
)
class RulingText(BaseModel):
    text: str
class GenerateRequest(BaseModel):
    plaintiff: str
    defendant: str
    claim_amount: float
    case_number: str
    court_name: str = "Арбитражный суд г. Москвы"
@app.get("/health", tags=["Health"])
async def health():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}

@app.post("/extract", tags=["Extraction"])
async def extract(ruling: RulingText):
    """Извлечение данных из судебного акта (заглушка)"""
    # TODO: Подключить модель для реального извлечения данных
    return {
        "plaintiff": "ООО Ромашка",
        "defendant": "Иванов Иван Иванович",
        "claim_amount": 500000.00,
        "judge": "Петрова А.С.",
        "case_number": "А40-12345/2024"
    }
@app.post("/generate/claim", tags=["Generation"])
async def generate_claim(data: GenerateRequest):
    """Генерация искового заявления"""
    # TODO: Реализовать генерацию .docx через шаблоны
    return {
        "status": "success",
        "message": "Исковое заявление успешно сгенерировано",
        "filename": "iskovoe_zayavlenie.docx"
    }
@app.post("/generate/appeal", tags=["Generation"])
async def generate_appeal(data: GenerateRequest):
    """Генерация апелляционной жалобы"""
    # TODO: Реализовать генерацию .docx через шаблоны
    return {
        "status": "success",
        "message": "Апелляционная жалоба успешно сгенерирована",
        "filename": "apellyatsionnaya_zhaloba.docx"
    }
@app.post("/generate/contract", tags=["Generation"])
async def generate_contract(data: GenerateRequest):
    """Генерация договора"""
    # TODO: Реализовать генерацию .docx через шаблоны
    return {
        "status": "success",
        "message": "Договор успешно сгенерирован",
        "filename": "dogovor.docx"
    }