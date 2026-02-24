import os
import re
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def extract_structured_financials(text):

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not found")
        return None

    print("GROQ KEY LOADED:", api_key[:10], "...")
    client = Groq(api_key=api_key)
    cleaned_text = _clean_ocr_text(text)

    prompt = f"""You are a financial data extraction expert.

Extract the Income Statement / P&L data from the text below and return ONLY a valid JSON object.

Output format:
{{
  "company_name": "Tata Motors Limited",
  "currency": "INR",
  "units": "crores",
  "years": ["Q4 FY2025", "Q3 FY2025", "Q4 FY2024", "FY2025", "FY2024"],
  "line_items": [
    {{
      "name": "Revenue from Operations",
      "values": [119503, 112608, 119033, 438695, 434016]
    }}
  ]
}}

STRICT RULES:
- Return ONLY the JSON object. No explanation. No markdown. No code blocks.
- Extract company_name from the document header or title.
- values array must match the order of years array exactly.
- Use null for any missing value.
- Extract ALL line items visible in the document.
- Numbers should be plain numbers (no commas, no currency symbols).
- Negative numbers use minus sign e.g. -7428.

Financial Document Text:
{cleaned_text[:10000]}
"""

    print("Calling Groq API...")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial data extraction API. You ONLY output valid JSON. Never output anything else."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            max_tokens=4096
        )

        raw = response.choices[0].message.content
        print("Groq responded. Raw length:", len(raw))
        _save_debug(cleaned_text, raw)
        result = _extract_json(raw)

        if result:
            print(f"Successfully extracted {len(result.get('line_items', []))} line items.")
            print(f"Company: {result.get('company_name', 'Unknown')}")
        else:
            print("Failed to extract valid JSON from LLM response.")

        return result

    except Exception as e:
        print(f"Groq API error: {e}")
        return None


def _clean_ocr_text(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'[|]{2,}', '', text)
    return text.strip()


def _extract_json(raw):
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
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    start = raw.find('{')
    end   = raw.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end+1])
        except Exception as e:
            print(f"All JSON parse strategies failed: {e}")
            print("First 500 chars:", raw[:500])
    return None


def _save_debug(text, raw_response):
    os.makedirs("debug", exist_ok=True)
    with open("debug/ocr_text.txt", "w", encoding="utf-8") as f:
        f.write(text)
    with open("debug/llm_response.txt", "w", encoding="utf-8") as f:
        f.write(raw_response)
    print("Debug files saved.")