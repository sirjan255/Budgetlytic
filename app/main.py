import streamlit as st
from dotenv import load_dotenv
import os
import cloudinary
import cloudinary.uploader
from firebase_admin import credentials, firestore, initialize_app
import whisper
from PIL import Image
import io
from google.cloud import vision
import pytz
from datetime import datetime
import base64
import re

# ---- LOAD ENVIRONMENT ----
load_dotenv()

# ---- CLOUDINARY SETUP ----
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# ---- FIRESTORE SETUP ----
if not hasattr(st.session_state, "_firebase_initialized"):
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")
    cred = credentials.Certificate(cred_path)
    initialize_app(cred)
    st.session_state._firebase_initialized = True
db = firestore.client()

# ---- GOOGLE VISION SETUP ----
gcv_client = vision.ImageAnnotatorClient()

# ---- WHISPER SETUP ----
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")
whisper_model = load_whisper_model()

from ai.categorizer import category_ui, suggest_categories

# ---- UTILITY FUNCTIONS ----
def get_user_id():
    """Get user identifier for storing/fetching user-specific data."""
    return st.session_state.get("user_id", "anonymous")

def save_to_firestore(user_id, collection, data):
    """Save a data dictionary to a given Firestore subcollection for a user."""
    db.collection("users").document(user_id).collection(collection).add(data)

def upload_image_to_cloudinary(img_bytes, filename):
    """Upload image bytes to Cloudinary and return the public URL."""
    result = cloudinary.uploader.upload(img_bytes, public_id=f'uploads/{get_user_id()}/{filename}')
    return result['secure_url']

def ocr_image(image_bytes):
    """Extract text from image using Google Cloud Vision OCR."""
    from ocr.photo_ocr import extract_text_from_image
    return extract_text_from_image(image_bytes)

def transcribe_audio(audio_bytes):
    """Transcribe audio bytes using Whisper."""
    with open("temp.wav", "wb") as f:
        f.write(audio_bytes)
    result = whisper_model.transcribe("temp.wav", fp16=False)
    os.remove("temp.wav")
    return result["text"]

def show_avatar():
    """Display Budgetlytic logo/avatar at the top."""
    st.image("https://cdn-icons-png.flaticon.com/512/4825/4825038.png", width=80, caption="Budgetlytic AI")

def get_current_time():
    """Return the current time in Asia/Kolkata timezone."""
    tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")

# ---- MAIN APP LOGIC ----

st.set_page_config(page_title="Budgetlytic", page_icon=":moneybag:", layout="centered")
show_avatar()
st.title("💸 Budgetlytic: Smarter Spending with AI")

menu = st.sidebar.selectbox("Navigate", [
    "Upload Bill", "Voice Expense", "View Expenses", "Insights", "Reminders"
])

if menu == "Upload Bill":
    st.header("📄 Upload Bill/Receipt")
    uploaded_img = st.file_uploader("Upload a bill/receipt image (JPG/PNG)", type=['jpg', 'jpeg', 'png'])
    if uploaded_img is not None:
        image_bytes = uploaded_img.read()
        st.image(image_bytes, caption="Uploaded Bill", width=350)
        ocr_text = ocr_image(image_bytes)
        st.subheader("Extracted Text")
        st.code(ocr_text)
        st.markdown("#### AI-based Category Suggestion")
        bill_category = category_ui(ocr_text)
        if not bill_category:
            bill_category = st.selectbox("Or choose manually", [
                "Food & Dining", "Transport", "Utilities & Bills", "Shopping", "Entertainment", "Medical & Health", 
                "Gifts & Donations", "Children & Education", "Investment & Savings", "Personal Care", "Home & Rent", "Other"
            ])
        if st.button("Save Bill Data"):
            public_url = upload_image_to_cloudinary(image_bytes, uploaded_img.name)
            data = {
                "img_url": public_url,
                "ocr_text": ocr_text,
                "category": bill_category,
                "timestamp": get_current_time(),
                "type": "bill"
            }
            save_to_firestore(get_user_id(), "bills", data)
            st.success("Bill data saved!")

elif menu == "Voice Expense":
    st.header("Log Expense by Voice")
    uploaded_audio = st.file_uploader("Upload a voice note (WAV/MP3)", type=['wav', 'mp3'])
    if uploaded_audio is not None:
        audio_bytes = uploaded_audio.read()
        transcript = transcribe_audio(audio_bytes)
        st.subheader("Transcribed Text")
        st.code(transcript)
        st.markdown("#### AI-based Category Suggestion")
        voice_category = category_ui(transcript)
        amt = re.findall(r"\b\d{2,6}\b", transcript)
        extracted_amt = float(amt[0]) if amt else None
        amount_voice = st.number_input("Amount (from voice or enter manually)", min_value=1.0, step=1.0, value=extracted_amt or 1.0)
        if not voice_category:
            voice_category = st.selectbox("Or choose manually", [
                "Food & Dining", "Transport", "Utilities & Bills", "Shopping", "Entertainment", "Medical & Health", 
                "Gifts & Donations", "Children & Education", "Investment & Savings", "Personal Care", "Home & Rent", "Other"
            ])
        if st.button("Save Voice Expense"):
            data = {
                "category": voice_category,
                "amount": amount_voice,
                "note": transcript,
                "timestamp": get_current_time(),
                "type": "voice"
            }
            save_to_firestore(get_user_id(), "expenses", data)
            st.success("Voice expense saved!")

elif menu == "View Expenses":
    st.header("Expense History")
    docs = db.collection("users").document(get_user_id()).collection("expenses").order_by(
        "timestamp", direction=firestore.Query.DESCENDING
    ).stream()
    rows = []
    for doc in docs:
        d = doc.to_dict()
        rows.append([
            d.get("timestamp"), d.get("category"), d.get("amount"), d.get("note", "")
        ])
    if rows:
        st.table(rows)
    else:
        st.info("No expenses found!")

elif menu == "Insights":
    st.header("Spending Insights (Beta)")
    docs = db.collection("users").document(get_user_id()).collection("expenses").stream()
    import pandas as pd
    df = pd.DataFrame([doc.to_dict() for doc in docs])
    if not df.empty:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        st.subheader("Category-wise Spending")
        st.bar_chart(df.groupby("category")["amount"].sum())
        st.subheader("Monthly Spending")
        df["month"] = pd.to_datetime(df["timestamp"]).dt.to_period("M").astype(str)
        st.line_chart(df.groupby("month")["amount"].sum())
    else:
        st.info("No expenses data for insights!")

elif menu == "Reminders":
    st.header("🔔 Reminders & Push Notifications")
    st.info("Set reminders for bills, goals, or anything! We'll send you a push notification at the scheduled time if notifications are enabled in your browser.")