import os
import re
import json
from dotenv import load_dotenv

load_dotenv()

MODELS_TO_TRY = [
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-flash-latest",
]


def extract_with_gemini_vision(image_paths):
    from google import genai
    from PIL import Image

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found")
        return None

    client = genai.Client(api_key=api_key)

    images = []
    for path in image_paths:
        try:
            images.append(Image.open(path))
            print(f"  Loaded image: {path}")
        except Exception as e:
            print(f"  Could not load image {path}: {e}")

    if not images:
        print("No images to process")
        return None

    prompt = """You are a financial data extraction expert.

Look at these financial statement pages carefully and extract ALL Income Statement / P&L data.

Return ONLY a valid JSON object in exactly this format:
{
  "company_name": "Tata Motors Limited",
  "currency": "INR",
  "units": "crores",
  "years": ["Q4 FY2025", "Q3 FY2025", "Q4 FY2024", "FY2025", "FY2024"],
  "line_items": [
    {
      "name": "Revenue from Operations",
      "values": [119503, 112608, 119033, 439695, 434016]
    }
  ]
}

STRICT RULES:
- Extract company_name from the document header, title, or letterhead.
- Read EVERY row carefully left to right — do NOT skip any row.
- The values array MUST match the years array order exactly, column by column.
- Use null for any missing value — do NOT skip columns or shift values.
- Extract ALL line items including sub-items, totals, and EPS rows.
- Numbers are plain integers/floats — no commas, no currency symbols.
- Negative numbers use minus sign e.g. -7428.
- Return ONLY the JSON. No explanation, no markdown, no code blocks.
"""

    content = images + [prompt]

    for model_name in MODELS_TO_TRY:
        print(f"  Trying model: {model_name}...")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=content,
            )
            raw = response.text.strip()
            print(f"  ✅ {model_name} responded. Raw length: {len(raw)}")

            os.makedirs("debug", exist_ok=True)
            with open("debug/gemini_response.txt", "w", encoding="utf-8") as f:
                f.write(raw)

            result = _parse_json(raw)
            if result:
                print(f"  ✅ JSON parsed — {len(result.get('line_items', []))} line items")
                print(f"  Company: {result.get('company_name', 'Unknown')}")
                return result
            else:
                print(f"  ⚠️  JSON parse failed — trying next model")

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                print(f"  ⚠️  {model_name} quota exceeded — trying next...")
            elif "404" in err_str or "not found" in err_str.lower():
                print(f"  ⚠️  {model_name} not available — trying next...")
            else:
                print(f"  ❌ {model_name} error: {err_str[:200]}")
            continue

    print("  ❌ All Gemini models exhausted")
    return None


def _parse_json(raw):
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    cleaned = re.sub(r'```(?:json)?', '', raw).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    start = raw.find('{')
    end   = raw.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end+1])
        except Exception as e:
            print(f"  JSON parse failed: {e}")
            print("  First 300 chars:", raw[:300])
    return None