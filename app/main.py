from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import shutil
import os

load_dotenv()

from app.extractor import process_financial_pdf
from app.excel_generator import generate_excel

app = FastAPI(title="Financial Statement Extraction Tool")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "/tmp/outputs")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/check-gemini")
def check_gemini():
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"error": "GEMINI_API_KEY not set in .env"}

        client = genai.Client(api_key=api_key)
        models  = client.models.list()
        available = [
            getattr(m, 'name', str(m))
            for m in models
            if 'gemini' in getattr(m, 'name', str(m)).lower()
        ]
        return {
            "key_loaded":         api_key[:12] + "...",
            "gemini_models":      available,
            "total_models_found": len(available)
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print(f"File saved: {file_path}")

    structured_data, metadata = process_financial_pdf(file_path)

    # Clean up uploaded PDF
    try:
        os.remove(file_path)
    except Exception:
        pass

    if not structured_data or not structured_data.get("line_items"):
        return JSONResponse(
            status_code=422,
            content={
                "error":   "Could not extract financial data from the PDF.",
                "details": metadata
            }
        )

    excel_path = generate_excel(structured_data, metadata, output_folder=OUTPUT_FOLDER)

    # Build download filename from extracted company name
    company_name  = structured_data.get("company_name", "Financial Statement")
    safe_name     = "".join(c for c in company_name if c.isalnum() or c in (" ", "-", "_", ".")).strip()
    download_name = f"{safe_name}.xlsx" if safe_name else "Financial_Statement.xlsx"

    return FileResponse(
        excel_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )