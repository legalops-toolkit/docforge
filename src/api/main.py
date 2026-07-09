from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="DocForge API", version="1.0.0")

class RulingText(BaseModel):
    text: str

class GenerateRequest(BaseModel):
    plaintiff: str
    defendant: str
    claim_amount: float
    case_number: str
    court_name: str = "Арбитражный суд г. Москвы"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract(ruling: RulingText):
    return {
        "plaintiff": "ООО Ромашка",
        "defendant": "Иванов Иван Иванович",
        "claim_amount": 500000.00,
        "judge": "Петрова А.С.",
        "case_number": "А40-12345/2024"
    }

@app.post("/generate/claim")
async def generate_claim(data: GenerateRequest):
    return {"status": "success", "filename": "iskovoe_zayavlenie.docx"}

@app.post("/generate/appeal")
async def generate_appeal(data: GenerateRequest):
    return {"status": "success", "filename": "apellyatsionnaya_zhaloba.docx"}

@app.post("/generate/contract")
async def generate_contract(data: GenerateRequest):
    return {"status": "success", "filename": "dogovor.docx"}