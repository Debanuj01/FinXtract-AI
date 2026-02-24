import os
import pdfplumber
from pdf2image import convert_from_path
from app.llm_mapper import extract_structured_financials
from app.gemini_vision import extract_with_gemini_vision

TEMP_DIR = os.getenv("TEMP_DIR", "/tmp/pdf_pages")


# ── Strategy 1: pdfplumber direct table extraction ────────────────────────────
def extract_tables_pdfplumber(pdf_path):
    all_tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if tables:
                    print(f"  [pdfplumber] Page {page_num+1}: found {len(tables)} table(s)")
                    all_tables.extend(tables)
    except Exception as e:
        print(f"  pdfplumber error: {e}")
    return all_tables


def is_scanned_table(tables):
    """
    Returns True if pdfplumber found tables but they are empty/image-based.
    Scanned PDFs return tables full of None values — no actual text content.
    """
    if not tables:
        return False

    total_cells  = 0
    none_cells   = 0
    filled_cells = 0

    for table in tables:
        for row in table:
            if row:
                for cell in row:
                    total_cells += 1
                    if cell is None or str(cell).strip() == "":
                        none_cells += 1
                    else:
                        filled_cells += 1

    if total_cells == 0:
        return False

    none_ratio = none_cells / total_cells
    print(f"  Table content check: {filled_cells} filled / {total_cells} total cells ({none_ratio*100:.0f}% empty)")

    # If more than 70% of cells are empty/None → scanned PDF
    return none_ratio > 0.70


def map_tables_to_json(tables):
    """
    Convert pdfplumber table arrays into our standard JSON structure.
    Only called for genuinely digital PDFs with real text content.
    """
    if not tables:
        return None

    years      = []
    line_items = []
    currency   = "INR"
    units      = "crores"

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Find header row (contains year/quarter labels)
        header_row_idx = None
        for i, row in enumerate(table):
            if row and any(
                cell and any(kw in str(cell).upper()
                for kw in ["FY", "Q1", "Q2", "Q3", "Q4", "YEAR", "MARCH", "QUARTER"])
                for cell in row
            ):
                header_row_idx = i
                break

        if header_row_idx is None:
            continue

        header_row = table[header_row_idx]

        col_years = []
        for cell in header_row[1:]:
            if cell and str(cell).strip():
                col_years.append(str(cell).strip())

        if not col_years:
            continue

        if not years:
            years = col_years

        for row in table[header_row_idx + 1:]:
            if not row or not row[0]:
                continue

            name = str(row[0]).strip()
            if not name or name.lower() in ("particulars", ""):
                continue

            if "crore" in name.lower():
                units = "crores"
            elif "million" in name.lower():
                units = "millions"

            values = []
            for cell in row[1:len(col_years)+1]:
                if cell is None or str(cell).strip() in ("", "-", "–", "—", "NA"):
                    values.append(None)
                else:
                    try:
                        cleaned = str(cell).replace(",", "").replace("(", "-").replace(")", "").strip()
                        values.append(float(cleaned) if "." in cleaned else int(cleaned))
                    except ValueError:
                        values.append(None)

            line_items.append({"name": name, "values": values})

    if not line_items:
        return None

    return {
        "currency":   currency,
        "units":      units,
        "years":      years,
        "line_items": line_items
    }


# ── Strategy 2: pdfplumber plain text → Groq LLM ─────────────────────────────
def extract_text_pdfplumber(pdf_path):
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception as e:
        print(f"  pdfplumber text error: {e}")
    return full_text


# ── Strategy 3: Gemini Vision ─────────────────────────────────────────────────
def extract_pages_as_images(pdf_path):
    os.makedirs(TEMP_DIR, exist_ok=True)
    image_paths = []
    try:
        images = convert_from_path(pdf_path, dpi=200)
        for i, img in enumerate(images):
            img_path = os.path.join(TEMP_DIR, f"page_{i+1}.png")
            img.save(img_path, "PNG")
            image_paths.append(img_path)
        print(f"  Converted {len(image_paths)} pages to images")
    except Exception as e:
        print(f"  pdf2image error: {e}")
    return image_paths


def cleanup_images(image_paths):
    for path in image_paths:
        try:
            os.remove(path)
        except Exception:
            pass


# ── Main orchestrator ─────────────────────────────────────────────────────────
def process_financial_pdf(pdf_path):

    print(f"\n{'='*60}")
    print(f"Processing: {os.path.basename(pdf_path)}")
    print(f"{'='*60}")

    # ── STRATEGY 1: Direct table extraction (digital PDFs only) ──────────────
    print("\n[Strategy 1] Attempting pdfplumber table extraction...")
    tables = extract_tables_pdfplumber(pdf_path)

    if tables:
        # Check if this is a scanned PDF masquerading as having tables
        if is_scanned_table(tables):
            print("  ℹ️  Tables are image-based (scanned PDF) — skipping to Gemini Vision")
        else:
            structured = map_tables_to_json(tables)
            if structured and structured.get("line_items"):
                print(f"  ✅ Table extraction successful — {len(structured['line_items'])} line items")
                return structured, {
                    "confidence": "High",
                    "method":     "pdfplumber direct table extraction",
                    "accuracy":   "~95% — native table parsing"
                }
            else:
                print("  ⚠️  Tables found but could not parse year/column structure")
    else:
        print("  ℹ️  No tables detected")

    # ── STRATEGY 2: Text extraction + Groq LLM ────────────────────────────────
    print("\n[Strategy 2] Attempting pdfplumber text + Groq LLM...")
    text = extract_text_pdfplumber(pdf_path)

    if text.strip():
        print(f"  Extracted {len(text)} characters of text")
        structured = extract_structured_financials(text)
        if structured and structured.get("line_items"):
            print(f"  ✅ LLM text extraction successful — {len(structured['line_items'])} line items")
            return structured, {
                "confidence": "Medium",
                "method":     "pdfplumber text + Groq LLaMA",
                "accuracy":   "~60% — depends on PDF text quality"
            }
        else:
            print("  ⚠️  LLM extraction failed or returned empty")
    else:
        print("  ℹ️  No text found in PDF — confirmed scanned document")

    # ── STRATEGY 3: Gemini Vision ──────────────────────────────────────────────
    print("\n[Strategy 3] Falling back to Gemini Vision (scanned PDF)...")
    image_paths = extract_pages_as_images(pdf_path)

    if not image_paths:
        print("  ❌ Could not convert PDF to images")
        return {}, {"confidence": "Low", "method": "all strategies failed", "accuracy": "0%"}

    try:
        structured = extract_with_gemini_vision(image_paths)
    finally:
        cleanup_images(image_paths)

    if structured and structured.get("line_items"):
        print(f"  ✅ Gemini Vision successful — {len(structured['line_items'])} line items")
        return structured, {
            "confidence": "High",
            "method":     "Gemini Vision (gemini-2.5-flash)",
            "accuracy":   "~90% — vision model reads table directly"
        }

    print("  ❌ All strategies failed")
    return {}, {
        "confidence": "Low",
        "method":     "all strategies failed",
        "accuracy":   "0%"
    }