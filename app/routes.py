from flask import Blueprint, request, jsonify
import firebase_admin
from firebase_admin import firestore, storage
import whisper
from google.cloud import vision
import os
import io
from datetime import datetime
import pytz

# Initialize Flask blueprint
routes = Blueprint('routes', __name__)

# Initialize Firestore and Storage
db = firestore.client()
bucket = storage.bucket()
gcv_client = vision.ImageAnnotatorClient()

# Whisper model (load once)
whisper_model = whisper.load_model("base")

# Utility: Get current time in IST
def get_current_time():
    tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")

# --------- API: Add Expense ---------
@routes.route('/add_expense', methods=['POST'])
def add_expense():
    """
    Add an expense manually.
    Expects JSON: {user_id, category, amount, note}
    """
    data = request.json
    user_id = data.get('user_id', 'anonymous')
    expense = {
        "category": data["category"],
        "amount": data["amount"],
        "note": data.get("note", ""),
        "timestamp": get_current_time(),
        "type": "manual"
    }
    db.collection("users").document(user_id).collection("expenses").add(expense)
    return jsonify({"message": "Expense added!"}), 201

# --------- API: Upload Bill Image & OCR ---------
@routes.route('/upload_bill', methods=['POST'])
def upload_bill():
    """
    Uploads a bill image, runs OCR, and saves metadata.
    Expects multipart/form-data: file, user_id
    """
    file = request.files['file']
    user_id = request.form.get('user_id', 'anonymous')
    filename = file.filename
    img_bytes = file.read()
    # Upload to Firebase Storage
    blob = bucket.blob(f'uploads/{user_id}/{filename}')
    blob.upload_from_string(img_bytes, content_type='image/jpeg')
    public_url = blob.public_url
    # OCR with Google Vision
    from ocr.photo_ocr import extract_text_from_image
    ocr_text = extract_text_from_image(img_bytes)
    # Store in Firestore
    data = {
        "img_url": public_url,
        "ocr_text": ocr_text,
        "timestamp": get_current_time(),
        "type": "bill"
    }
    db.collection("users").document(user_id).collection("bills").add(data)
    return jsonify({"ocr_text": ocr_text, "img_url": public_url}), 201

# --------- API: Voice Logging ---------
@routes.route('/voice_expense', methods=['POST'])
def voice_expense():
    """
    Upload an audio file, transcribe it with Whisper, and extract expense info.
    Expects multipart/form-data: file, user_id
    """
    file = request.files['file']
    user_id = request.form.get('user_id', 'anonymous')
    audio_bytes = file.read()
    # Save temp audio file for Whisper
    temp_audio_path = "temp.wav"
    with open(temp_audio_path, "wb") as f:
        f.write(audio_bytes)
    result = whisper_model.transcribe(temp_audio_path, fp16=False)
    os.remove(temp_audio_path)
    transcript = result["text"]
    # Simple parsing for amount and category
    import re
    amt = re.findall(r"\b\d{2,6}\b", transcript)
    cat = None
    for c in ["food", "transport", "bill", "shopping", "entertainment", "medical", "other", "lunch", "dinner", "breakfast"]:
        if c in transcript.lower():
            cat = c.title()
    expense = {
        "category": cat or "Other",
        "amount": float(amt[0]) if amt else 0.0,
        "note": transcript,
        "timestamp": get_current_time(),
        "type": "voice"
    }
    db.collection("users").document(user_id).collection("expenses").add(expense)
    return jsonify({"transcript": transcript, "category": expense["category"], "amount": expense["amount"]}), 201

# --------- API: Get Expenses ---------
@routes.route('/expenses/<user_id>', methods=['GET'])
def get_expenses(user_id):
    """
    Returns all expenses for the given user.
    """
    docs = db.collection("users").document(user_id).collection("expenses").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    expenses = [doc.to_dict() for doc in docs]
    return jsonify(expenses), 200

# --------- API: Get Insights ---------
@routes.route('/insights/<user_id>', methods=['GET'])
def get_insights(user_id):
    """
    Returns summary stats for a user's expenses.
    """
    docs = db.collection("users").document(user_id).collection("expenses").stream()
    import pandas as pd
    df = pd.DataFrame([doc.to_dict() for doc in docs])
    if not df.empty:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        cat_sum = df.groupby("category")["amount"].sum().sort_values(ascending=False).to_dict()
        total_spent = df["amount"].sum()
        num_expenses = len(df)
        insights = {
            "categorywise": cat_sum,
            "total_spent": total_spent,
            "num_expenses": num_expenses
        }
        return jsonify(insights), 200
    else:
        return jsonify({"message": "No data"}), 200

# --------- API: Health Check ---------
@routes.route('/health', methods=['GET'])
def health():
    """
    Returns health status for monitoring.
    """
    return jsonify({"status": "ok"}), 200