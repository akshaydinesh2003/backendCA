import fitz  # PyMuPDF
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

# === Load API key from .env ===
load_dotenv()
GENAI_API_KEY = os.getenv("GENAI_API_KEY")

# === Configure Gemini ===
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# === Extract text from PDF ===
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as f:
        doc = fitz.open(stream=f.read(), filetype="pdf")
    return "\n".join([page.get_text() for page in doc]).strip()

# === Generate summary using Gemini ===
def generate_summary(text):
    prompt = f"""
You're an AI that helps students learn current affairs.

Given this text, return ONLY a raw JSON object with these keys:
- mcqs: list of multiple choice questions with options and correct answer
- summary: bullet point summary of events
- gk_points: related general knowledge points

❗ Return pure JSON without any explanation, comments, or markdown formatting.
❗ Do not include triple backticks or labels.

TEXT:
{text[:15000]}
"""
    response = model.generate_content(prompt)
    return response.text

# === Run the test ===
def main():
    pdf_path = "30_June_2025_CA.pdf"  # or full path like r"D:\...\30_June_2025_CA.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found at path: {pdf_path}")
        return

    text = extract_text_from_pdf(pdf_path)
    print("✅ Extracted text length:", len(text))

    output = generate_summary(text)
    print("\n🔍 Gemini raw output:\n", output)

    # 🧹 Clean markdown code block formatting (e.g., ```json ... ```)
    output = output.strip()
    if output.startswith("```json"):
        output = output[7:]  # remove ```json\n
    if output.endswith("```"):
        output = output[:-3]  # remove trailing ```

    try:
        parsed = json.loads(output)
        print("\n✅ Parsed JSON successfully. Keys:", parsed.keys())
    except json.JSONDecodeError as e:
        print("\n❌ JSON parsing failed:", str(e))
        print("\n🔴 Cleaned Output that failed to parse:\n", output)

if __name__ == "__main__":
    main()
