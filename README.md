# Budgetlytic Credentials Setup Guide

This document explains **in detail** how to obtain the credentials required for running Budgetlytic (both backend and frontend), how to structure your `.env` file, and what each credential does in relation to the packages in `requirements.txt`.

---

## 1. What Credentials Do You Need?

To run Budgetlytic, you need:

1. **A Google Cloud service account JSON key**  
   - Used for Firebase Admin SDK and Google Cloud Vision API.
2. **Your Firebase Storage Bucket name**  
   - Used to upload and retrieve files (receipts, audio, etc).

These credentials are provided to your app via a `.env` file.

---

## 2. Step-by-Step: How to Get Each Credential

### **A. Google Cloud Service Account Key**

This file (`serviceAccountKey.json`) gives your app permission to use:
- **Firebase Admin SDK** (for Firestore, Storage)  
- **Google Cloud Vision API** (for image OCR)

**How to get it:**

#### 1. Go to [Google Cloud Console](https://console.cloud.google.com/).

#### 2. Select your project
- This should be the project linked to your Firebase app.

#### 3. Enable Required APIs
- Go to **APIs & Services > Library**.
- Enable:
  - **Cloud Firestore API**
  - **Cloud Storage**
  - **Cloud Vision API**

#### 4. Create a Service Account
- Go to **IAM & Admin > Service Accounts**.
- Click **Create Service Account**.
- Give it a name (e.g., "budgetlytic-backend").
- Click **Create and Continue**.

#### 5. Grant Roles
- Assign these roles for the service account:
  - **Editor** (or more restrictive roles: "Cloud Datastore User", "Storage Admin", "Vision API User")
- Click **Continue** and then **Done**.

#### 6. Generate a JSON Key
- Click your service account in the list.
- Go to the **"Keys"** tab.
- Click **"Add Key" > "Create new key"**.
- Choose **JSON** and click **Create**.
- A file will be downloaded (e.g., `serviceAccountKey.json`).

**Where to put it:**  
- Place this file in your project root directory or wherever you plan to point to it in your `.env`.

---

### **B. Firebase Storage Bucket Name**

This is required for the app to upload and retrieve files (images, audio) via Firebase Storage.

**How to find it:**

1. Go to [Firebase Console](https://console.firebase.google.com/).
2. Select your project.
3. Click **Storage** in the left menu.
4. At the top, you’ll see your bucket name.  
   - It looks like: `your-project-id.appspot.com`

---

## 3. How to Structure Your .env File

Your `.env` file should look like this:

```
GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
```

- `GOOGLE_APPLICATION_CREDENTIALS`  
  - Points to the service account JSON downloaded in the steps above.
  - Can be a relative or absolute path.

- `FIREBASE_STORAGE_BUCKET`  
  - The name of your Firebase Storage bucket.

**Example:**
```
GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
FIREBASE_STORAGE_BUCKET=budgetlytic-1234.appspot.com
```

**Do not commit your `.env` or service account key to public repositories!**

---

## 4. What Do These Credentials Enable? (Relation to requirements.txt)

Here’s how these credentials connect to the main libraries in `requirements.txt`:

| Package             | What it does                                             | Credential Needed                          | Why?                                  |
|---------------------|---------------------------------------------------------|--------------------------------------------|---------------------------------------|
| `firebase-admin`    | Access Firestore and Storage                            | Service Account JSON + Storage bucket name | Authenticates all Firebase actions    |
| `google-cloud-vision` | OCR for bill/receipt images using Google Vision API     | Service Account JSON                       | Required for Vision API calls         |
| `python-dotenv`     | Loads `.env` credentials into your Python environment   | `.env` file                                | Makes credentials available to app    |
| `pytz`              | Timezone handling (no credentials needed)               | –                                          | –                                     |
| `pillow`            | Image processing (no credentials needed)                | –                                          | –                                     |
| `openai-whisper`    | Local audio transcription (no credentials needed)       | –                                          | –                                     |
| `streamlit`         | Frontend UI (loads `.env` for user identification, etc) | `.env` file                                | Uses user/session info if configured  |
| `omnidimension`     | Voice parsing (no credentials needed)                   | –                                          | –                                     |

**Summary:**
- The **service account JSON** is fundamental for all Firebase and Google Vision API actions.
- The **storage bucket name** tells the app where to upload/download files in Firebase Storage.
- Both backend (Flask API) and frontend (Streamlit) load these credentials using `python-dotenv`.

---

## 5. Additional Notes

- If you add more cloud features (like Google OAuth for login), you will need to add new credentials (e.g., `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) to your `.env`.
- Always keep your credentials safe—never commit `.env` or JSON keys to source control.
- If deploying to cloud platforms, set these as **environment variables** in your hosting environment.

---

## 6. Troubleshooting

- **File Not Found?**  
  Make sure the path in `GOOGLE_APPLICATION_CREDENTIALS` matches the location of your JSON key.
- **Permission Denied?**  
  Ensure your service account has the correct roles (Editor, or at least Firestore/Storage/Vision access).

---

**You must complete these credential steps before running the backend or frontend.**  
If you have issues, check the error logs—they usually provide hints if a credential is missing or misconfigured.
