from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import shutil
import os
import re
import uuid
import threading

load_dotenv()

from app.extractor import process_financial_pdf
from app.excel_generator import generate_excel

app = FastAPI(title="FinXtract")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "/tmp/outputs")
TEMP_DIR      = os.getenv("TEMP_DIR", "/tmp/pdf_pages")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ── In-memory job store ───────────────────────────────────────────────────────
# { job_id: { "status": "processing|done|error", "file": path, "filename": name, "error": msg } }
jobs = {}


def get_company_name(structured_data, original_filename):
    name = structured_data.get("company_name", "").strip()
    if name and name.lower() not in ("", "unknown", "n/a", "financial statement", "none"):
        return name
    raw   = os.path.splitext(original_filename)[0].replace("_", " ").replace("-", " ")
    noise = ["quarterly", "annual", "financial", "statements", "statement",
             "results", "report", "q1", "q2", "q3", "q4", "audited",
             "consolidated", "standalone"]
    words = [w for w in raw.split() if w.lower() not in noise]
    name  = " ".join(words).strip()
    return name if name else "Financial Statement"


def make_safe_filename(name):
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_", ".")).strip()
    safe = re.sub(r'\s+', ' ', safe)
    return safe if safe else "Financial_Statement"


def run_extraction(job_id, file_path, original_filename):
    """Runs in background thread — no timeout risk."""
    try:
        structured_data, metadata = process_financial_pdf(file_path)

        try:
            os.remove(file_path)
        except Exception:
            pass

        if not structured_data or not structured_data.get("line_items"):
            jobs[job_id] = {"status": "error", "error": "Could not extract financial data from this PDF."}
            return

        company_name = get_company_name(structured_data, original_filename)
        structured_data["company_name"] = company_name

        excel_path    = generate_excel(structured_data, metadata, output_folder=OUTPUT_FOLDER)
        download_name = f"{make_safe_filename(company_name)}.xlsx"

        jobs[job_id] = {
            "status":   "done",
            "file":     excel_path,
            "filename": download_name
        }
        print(f"Job {job_id} complete: {download_name}")

    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        jobs[job_id] = {"status": "error", "error": str(e)}


# ── Routes ────────────────────────────────────────────────────────────────────
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
        client    = genai.Client(api_key=api_key)
        models    = client.models.list()
        available = [
            getattr(m, 'name', str(m))
            for m in models
            if 'gemini' in getattr(m, 'name', str(m)).lower()
        ]
        return {"key_loaded": api_key[:12] + "...", "gemini_models": available}
    except Exception as e:
        return {"error": str(e)}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accepts PDF, starts background extraction, returns job_id immediately."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    job_id            = str(uuid.uuid4())
    original_filename = file.filename
    file_path         = os.path.join(UPLOAD_FOLDER, f"{job_id}_{original_filename}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print(f"Job {job_id} started: {original_filename}")

    # Mark as processing
    jobs[job_id] = {"status": "processing"}

    # Run extraction in background thread — avoids Render's 30s HTTP timeout
    t = threading.Thread(target=run_extraction, args=(job_id, file_path, original_filename))
    t.daemon = True
    t.start()

    return JSONResponse({"job_id": job_id})


@app.get("/status/{job_id}")
def check_status(job_id: str):
    """Poll this endpoint to check job progress."""
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    if job["status"] == "processing":
        return JSONResponse({"status": "processing"})

    if job["status"] == "error":
        return JSONResponse({"status": "error", "error": job["error"]})

    if job["status"] == "done":
        return JSONResponse({"status": "done", "filename": job["filename"]})


@app.get("/download/{job_id}")
def download_file(job_id: str):
    """Download the completed Excel file."""
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=404, detail="File not ready or not found")

    return FileResponse(
        job["file"],
        filename=job["filename"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )