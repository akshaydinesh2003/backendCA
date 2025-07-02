# app.py (Final backend reflecting summary, history, chatbot)

from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import uuid
import datetime
import json
import os
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# === Load environment variables ===
load_dotenv()
GENAI_API_KEY = os.getenv("GENAI_API_KEY")

# === Flask App ===
app = Flask(__name__)
CORS(app)

# === Firebase Initialization ===
cred = credentials.Certificate("firebase-service-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# === Gemini API Setup ===
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# === Utility: Extract PDF Text ===
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()

# === Utility: Generate Summary ===
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

# === Routes ===

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "✅ CA Web Backend is running"})

@app.route("/process-pdf", methods=["POST"])
def process_pdf():
    file = request.files.get('file')
    user_id = request.form.get('user_id')

    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        text = extract_text_from_pdf(file)
        output = generate_summary(text)
        print("🔍 Gemini raw output:", output)

        # Clean markdown triple backticks if present
        output = output.strip()
        if output.startswith("```json"):
            output = output[7:]
        if output.endswith("```"):
            output = output[:-3]

        parsed = json.loads(output)

        doc_id = str(uuid.uuid4())
        db.collection("users").document(user_id).collection("summaries").document(doc_id).set({
            "original_text": text[:1000],
            "mcqs": parsed.get("mcqs", []),
            "summary": parsed.get("summary", []),
            "gk_points": parsed.get("gk_points", []),
            "created_at": datetime.datetime.utcnow()
        })

        return jsonify({"status": "success", "doc_id": doc_id})

    except Exception as e:
        return jsonify({"error": f"{str(e)}", "raw_output": output}), 500

@app.route("/summaries/<user_id>", methods=["GET"])
def get_summaries(user_id):
    try:
        docs = db.collection("users").document(user_id).collection("summaries").stream()
        summaries = [{"id": doc.id, **doc.to_dict()} for doc in docs]
        return jsonify(summaries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/summary/<user_id>/<doc_id>", methods=["GET"])
def get_summary(user_id, doc_id):
    try:
        doc_ref = db.collection("users").document(user_id).collection("summaries").document(doc_id)
        doc = doc_ref.get()
        return jsonify(doc.to_dict()) if doc.exists else jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/quiz/<user_id>", methods=["POST"])
def save_quiz(user_id):
    try:
        data = request.json
        quiz_id = str(uuid.uuid4())
        db.collection("users").document(user_id).collection("quizzes").document(quiz_id).set({
            "questions": data.get("questions", []),
            "score": data.get("score", 0),
            "taken_on": datetime.datetime.utcnow()
        })
        return jsonify({"status": "saved", "quiz_id": quiz_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@app.route("/summary/<user_id>/<doc_id>", methods=["DELETE"])
def delete_summary(user_id, doc_id):
    try:
        db.collection("users").document(user_id).collection("summaries").document(doc_id).delete()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/chat", methods=["POST"])
def chat_reply():
    try:
        data = request.json
        user_msg = data.get("message", "")

        prompt = f"""You're an AI current affairs tutor.
Answer the following in a concise, simple manner.

Q: {user_msg}
A:"""

        response = model.generate_content(prompt)
        return jsonify({"reply": response.text.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# === Run ===
if __name__ == "__main__":
    app.run(debug=True)
    CORS(app, origins=["https://frontend-ca-one.vercel.app"])
