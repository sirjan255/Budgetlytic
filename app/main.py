import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage
import whisper
from PIL import Image
import io
import os
from google.cloud import vision
from dotenv import load_dotenv
import pytz
from datetime import datetime
import base64

#    SETUP & INITIALIZATION

# Load environment variables from .env file (for API keys, Firebase, etc.)
load_dotenv()

# --- Firebase Setup ---
# Initialize Firebase app only once (avoid duplicate errors in Streamlit)
if not firebase_admin._apps:
    # Using either the environment variable or a local service account key file
    cred = credentials.Certificate(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json"))
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.environ.get("FIREBASE_STORAGE_BUCKET", "some-bucket.appspot.com")
    })
db = firestore.client()         # Firestore database client
bucket = storage.bucket()       # Firebase Storage bucket for files/images

# --- Google Vision Setup ---
# Google OCR client for extracting text from images (bills/receipts)
gcv_client = vision.ImageAnnotatorClient()

# --- Whisper Setup ---
# Load Whisper model once and cache it for efficiency (choose model size as needed)
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")  # can use "small", "medium", "large" for accuracy/speed

whisper_model = load_whisper_model()

# --- Budgetlytic AI Categorizer Import ---
from ai.categorizer import category_ui, suggest_categories

#    UTILITY FUNCTIONS

def get_user_id():
    """
    Get user identifier for storing/fetching user-specific data.
    Uses session state, falls back to 'anonymous' for demo.
    """
    return st.session_state.get("user_id", "anonymous")

def save_to_firestore(user_id, collection, data):
    """
    Save a data dictionary to a given Firestore subcollection for a user.
    """
    db.collection("users").document(user_id).collection(collection).add(data)

def upload_image_to_firebase(img_bytes, filename):
    """
    Upload image bytes to Firebase Storage and return the public URL.
    """
    blob = bucket.blob(f'uploads/{get_user_id()}/{filename}')
    blob.upload_from_string(img_bytes, content_type='image/jpeg')
    return blob.public_url

def ocr_image(image_bytes):
    """
    Uses Google Vision OCR to extract text from image bytes.
    """
    from ocr.photo_ocr import extract_text_from_image
    return extract_text_from_image(image_bytes)

def transcribe_audio(audio_bytes):
    """
    Use Whisper model to transcribe audio bytes (wav or mp3).
    Saves audio temporarily to disk due to Whisper API requirements.
    """
    with open("temp.wav", "wb") as f:
        f.write(audio_bytes)
    result = whisper_model.transcribe("temp.wav", fp16=False)
    os.remove("temp.wav")
    return result["text"]

def show_avatar():
    """
    Display Budgetlytic logo/avatar at the top.
    """
    st.image("https://cdn-icons-png.flaticon.com/512/4825/4825038.png", width=80, caption="Budgetlytic AI")

def get_current_time():
    """
    Get current timestamp in IST (India Standard Time) for expense logging.
    """
    tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")

# --- App Configurations ---
st.set_page_config(page_title="Budgetlytic", page_icon=":money_with_wings:")

# --- App Header & Branding ---
show_avatar()
st.title("Budgetlytic :money_with_wings:")
st.markdown("**Your AI-powered personal finance assistant!**")

# --- Sidebar Navigation ---
menu = st.sidebar.radio("Navigate", [
    "Add Expense", 
    "Upload Bill", 
    "Voice Logging", 
    "View Expenses", 
    "Insights", 
    "Settings", 
    "About"
])

#    PAGE: Add Expense
if menu == "Add Expense":
    st.header("Add Expense Manually")
    # Category selection
    amount = st.number_input("Amount (INR)", min_value=1.0, step=1.0)
    note = st.text_input("Notes (optional, e.g. details of the expense)")
    st.markdown("#### AI-based Category Suggestion")
    category = category_ui(note)
    if not category:
        # fallback to manual choice if user doesn't select from AI UI
        category = st.selectbox("Or choose manually", [
            "Food & Dining", "Transport", "Utilities & Bills", "Shopping", "Entertainment", "Medical & Health", 
            "Gifts & Donations", "Children & Education", "Investment & Savings", "Personal Care", "Home & Rent", "Other"
        ])
    if st.button("Add Expense"):
        data = {
            "category": category,
            "amount": amount,
            "note": note,
            "timestamp": get_current_time(),
            "type": "manual"
        }
        save_to_firestore(get_user_id(), "expenses", data)
        st.success("Expense logged!")


#    PAGE: Upload Bill/Receipt
elif menu == "Upload Bill":
    st.header("Upload Bill or Receipt")
    uploaded_img = st.file_uploader("Upload an image (jpg/png)", type=["jpg", "jpeg", "png"])
    if uploaded_img:
        image_bytes = uploaded_img.read()
        st.image(image_bytes, caption="Uploaded Bill", width=350)
        # OCR using Google Vision
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
            public_url = upload_image_to_firebase(image_bytes, uploaded_img.name)
            data = {
                "img_url": public_url,
                "ocr_text": ocr_text,
                "category": bill_category,
                "timestamp": get_current_time(),
                "type": "bill"
            }
            save_to_firestore(get_user_id(), "bills", data)
            st.success("Bill saved and OCR data extracted!")


#    PAGE: Voice Logging
elif menu == "Voice Logging":
    st.header("Log an Expense by Voice")
    st.info("Record or upload your expense (e.g., 'I spent 150 rupees on lunch')")
    audio_file = st.file_uploader("Upload audio (wav/mp3)", type=["wav", "mp3"])
    if audio_file:
        audio_bytes = audio_file.read()
        st.audio(audio_bytes, format="audio/wav")
        # Transcribe audio using Whisper
        transcript = transcribe_audio(audio_bytes)
        st.subheader("Transcribed Text")
        st.write(transcript)
        st.markdown("#### AI-based Category Suggestion")
        voice_category = category_ui(transcript)
        # Try amount extraction (fallback to user input if not detected)
        import re
        amt = re.findall(r"\b\d{2,8}\b", transcript)
        extracted_amt = float(amt[0]) if amt else 0.0
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

#    PAGE: View Expenses
elif menu == "View Expenses":
    st.header("Expense History")
    # Fetch all user's expenses from Firestore (most recent first)
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
        # Display as a table: Timestamp | Category | Amount | Note
        st.table(rows)
    else:
        st.info("No expenses found!")

#    PAGE: Insights (Charts, Stats)
elif menu == "Insights":
    st.header("Spending Insights (Beta)")
    docs = db.collection("users").document(get_user_id()).collection("expenses").stream()
    import pandas as pd
    df = pd.DataFrame([doc.to_dict() for doc in docs])
    if not df.empty:
        # Convert amount to numeric for calculations
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        # Category-wise spending summary
        cat_sum = df.groupby("category")["amount"].sum().sort_values(ascending=False)
        st.bar_chart(cat_sum)
        st.metric("Total Spent", f"₹{df['amount'].sum():,.2f}")
        st.metric("Number of Expenses", len(df))
        # Highlight highest spending category
        if not cat_sum.empty and cat_sum.iloc[0] > 0:
            st.warning(f"Highest spending: **{cat_sum.index[0]}** (₹{cat_sum.iloc[0]:,.2f})")
    else:
        st.info("Not enough data for insights. Add more expenses!")

#    PAGE: Settings
elif menu == "Settings":
    st.header("Settings")
    # For demo: allowing user to set a custom user ID (can replace with OAuth in production)
    user_id = st.text_input("Set your User ID (for privacy & syncing)", value=get_user_id())
    if st.button("Save User ID"):
        st.session_state["user_id"] = user_id
        st.success("User ID updated! Reload the page to sync data.")


#    PAGE: About
elif menu == "About":
    st.header("About Budgetlytic")
    st.markdown("""
    **Budgetlytic** is an AI-powered, privacy-respecting personal finance assistant built with Streamlit, Firebase, Google Vision, and OpenAI Whisper.

    - **Log expenses** by text, voice, or bill image  
    - **Get insights** on your spending  
    - **All your data stays private & secure**  
    - **No bank access required**  
    - Hackathon-ready, extensible, and secure!
    ---
    _Made with ❤️ by Team Budgetlytic_
    """)