# 🚀 FinXtract — AI-Powered Financial Statement Extraction Engine

A web-based AI system that extracts structured financial statements from PDF annual reports and generates professionally formatted Excel financial models.

---

## 🎯 Problem Statement

Annual reports are typically 150–300 page PDFs containing:

- Complex financial tables  
- Inconsistent layouts across companies  
- Mixed digital and scanned content  
- Multi-period financial data  

Financial analysts often spend hours manually copying numbers into Excel.

Traditional PDF parsers fail on:
- Scanned documents  
- Non-tabular layouts  
- Complex formatting  

**FinXtract solves this using a hybrid AI + rule-based architecture.**

---

## 🧠 How It Works

FinXtract automatically selects the best extraction strategy using a 3-layer hybrid pipeline:

```
PDF Uploaded
    │
    ├─ Strategy 1: pdfplumber table extraction
    │   → Digital PDFs with structured tables (~95% accuracy)
    │
    ├─ Strategy 2: pdfplumber text + Groq LLM
    │   → Digital PDFs without tables (~60–70% accuracy)
    │
    └─ Strategy 3: Gemini Vision
        → Scanned / image-based PDFs (~85–90% accuracy)
```

The extracted data is validated, structured into JSON, and converted into a styled Excel model with formulas.

---

## 🏗 System Architecture

```
User Upload
     │
     ▼
FastAPI Backend
     │
     ▼
Hybrid Extraction Engine
     ├─ pdfplumber (tables)
     ├─ Groq LLaMA 3.3 70B
     └─ Gemini 2.5 Flash (Vision)
     │
     ▼
Structured JSON Validation
     │
     ▼
Excel Generator (openpyxl)
     │
     ▼
Downloadable Financial Model
```

---

## 📊 Output Excel Features

The generated Excel file includes:

- Multi-period financial columns  
- All Income Statement line items  
- EBITDA auto-calculation  
- PAT Margin & PBT Margin formulas  
- Cost ratio calculation  
- Styled sections and totals  
- Metadata sheet (company, currency, units)  

This produces a ready-to-use financial model.

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + Uvicorn |
| PDF Table Extraction | pdfplumber |
| PDF → Image | pdf2image + Pillow |
| LLM (Text PDFs) | Groq — LLaMA 3.3 70B |
| Vision AI (Scanned PDFs) | Google Gemini 2.5 Flash |
| Excel Generation | openpyxl |
| Frontend | HTML + CSS (Vanilla) |

---

## 📁 Project Structure

```
Research-Portal/
├── app/
│   ├── __init__.py
|   ├── main.py
│   ├── extractor.py
│   ├── llm_mapper.py
│   ├── gemini_vision.py
│   └── excel_generator.py
├── templates/
├── static/
├── .env
├── render.yaml
└── requirements.txt
```

---

## 🚀 Local Setup

### Prerequisites

- Python 3.10+
- Poppler (for pdf2image)

### Install Poppler

**Windows:**  
Download from https://github.com/oschwartz10612/poppler-windows/releases
and add the `bin/` folder to your system PATH.

**Mac:**
```bash
brew install poppler
```

**Linux:**
```bash
sudo apt install poppler-utils
```

---

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file:

```
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
```

Run the app:

```bash
uvicorn app.main:app --reload
```

Open in browser:

```
http://127.0.0.1:8000
```

---

## 🌐 Deployment (Render)

1. Push project to GitHub
2. Create a new Web Service on Render
3. Add environment variables:
   - GROQ_API_KEY
   - GEMINI_API_KEY
4. Deploy

Render free tier supported.

---

## 🔐 Security & Privacy

- Files processed in temporary directories  
- No persistent data storage  
- API keys stored via environment variables  
- HTTPS deployment supported  

---

## 🚀 Why Hybrid Architecture?

| Approach | Limitation |
|----------|------------|
| Rule-based only | Breaks on layout variation |
| LLM only | Expensive & inconsistent |
| OCR only | Poor structural mapping |

FinXtract balances:
- Speed  
- Accuracy  
- Cost  
- Robustness  

---

## 📈 Performance (Approximate)

| Strategy | Avg Time | Accuracy |
|----------|----------|----------|
| Table Extraction | 2–3 sec | ~95% |
| Text + LLM | 4–6 sec | ~65% |
| Vision AI | 6–10 sec | ~85–90% |

---

## 🔮 Future Roadmap

- Balance Sheet extraction  
- Cash Flow extraction  
- Batch processing  
- Company comparison mode  
- Financial ratio automation  
- Dashboard analytics layer  

---

## 📄 License

MIT License — free to use and modify.