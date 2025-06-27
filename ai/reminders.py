import os
from datetime import datetime, timedelta
import pytz
import requests
import json
import streamlit as st

# Default timezone for reminders
DEFAULT_TIMEZONE = "Asia/Kolkata"

# Fetch FCM server key securely from environment variable for push notifications
FCM_SERVER_KEY = os.environ.get("FCM_SERVER_KEY")


def get_local_now():
    """Get the current time in the default timezone."""
    return datetime.now(pytz.timezone(DEFAULT_TIMEZONE))


def parse_remind_dt(dt_str):
    """Parse ISO datetime string to a datetime object with timezone."""
    return datetime.fromisoformat(dt_str).astimezone(pytz.timezone(DEFAULT_TIMEZONE))


def get_reminders(db, user_id):
    """
    Fetch all reminders for the user from Firestore.
    Args:
        db: Firestore client
        user_id: User's unique ID
    Returns:
        List of reminder documents as dicts
    """
    docs = db.collection("users").document(user_id).collection("reminders").stream()
    reminders = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        reminders.append(data)
    return reminders


def add_reminder(db, user_id, message, remind_dt):
    """
    Add a new reminder for the user in Firestore.
    Args:
        db: Firestore client
        user_id: User's unique ID
        message: Reminder message
        remind_dt: Datetime object for when to send reminder
    """
    db.collection("users").document(user_id).collection("reminders").add({
        "message": message,
        "remind_dt": remind_dt.isoformat(),
        "created_at": datetime.utcnow().isoformat(),
        "sent": False,
    })


def delete_reminder(db, user_id, reminder_id):
    """
    Delete a reminder for the user from Firestore.
    Args:
        db: Firestore client
        user_id: User's unique ID
        reminder_id: Firestore doc ID of the reminder
    """
    db.collection("users").document(user_id).collection("reminders").document(reminder_id).delete()


def store_fcm_token(db, user_id, token):
    """
    Store the FCM token for the user in Firestore.
    Args:
        db: Firestore client
        user_id: User's unique ID
        token: FCM device token from the browser/device
    """
    db.collection("users").document(user_id).set({"fcm_token": token}, merge=True)


def send_fcm_push(token, title, body):
    """
    Send a push notification to a device using FCM.
    Args:
        token: FCM device token
        title: Notification title
        body: Notification body
    Returns:
        (status_code, response_text)
    """
    if not FCM_SERVER_KEY:
        print("FCM_SERVER_KEY not set in environment!")
        return 401, "FCM server key missing"
    url = "https://fcm.googleapis.com/fcm/send"
    headers = {
        "Authorization": f"key={FCM_SERVER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": token,
        "notification": {
            "title": title,
            "body": body,
            "icon": "https://app.com/icon.png" 
        }
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return response.status_code, response.text


def process_due_reminders(db):
    """
    Check all users' reminders and send push notifications for due ones.
    Should be run periodically (e.g., every minute) in a background job or cloud function.
    Args:
        db: Firestore client
    """
    users = db.collection("users").stream()
    now = get_local_now()
    for user_doc in users:
        user_id = user_doc.id
        user_data = user_doc.to_dict()
        token = user_data.get("fcm_token")
        if not token:
            continue  # Skip users who haven't registered for push notifications
        reminders = db.collection("users").document(user_id).collection("reminders") \
            .where("sent", "==", False).stream()
        for rem in reminders:
            data = rem.to_dict()
            rem_dt = parse_remind_dt(data["remind_dt"])
            # If reminder is due (now or past), and not already sent
            if rem_dt <= now and not data.get("sent"):
                # Send push notification
                status, resp = send_fcm_push(
                    token,
                    "⏰ Reminder from Budgetlytic",
                    data["message"]
                )
                # Mark as sent if successfully delivered
                if status == 200:
                    rem.reference.update({"sent": True})


def reminders_ui(db, user_id, fcm_token=None):
    """
    Streamlit UI for managing reminders and registering for push notifications.
    Args:
        db: Firestore client
        user_id: User's unique ID
        fcm_token: FCM device token, automatically sent from frontend JS
    """
    st.header("🔔 Reminders & Push Notifications")
    st.info("Set reminders for bills, goals, or anything! We'll send you a push notification at the scheduled time if notifications are enabled in your browser.")

    # --- FCM token registration from JS ---
    if fcm_token:
        store_fcm_token(db, user_id, fcm_token)
        st.success("Push notifications enabled for your device!")

    # --- Reminder creation form ---
    with st.form("add_reminder_form", clear_on_submit=True):
        message = st.text_input("Reminder message", placeholder="E.g. Pay electricity bill, Transfer to savings...")
        date = st.date_input("Date", min_value=get_local_now().date())
        time = st.time_input("Time", value=(get_local_now() + timedelta(minutes=2)).time())
        submitted = st.form_submit_button("Add Reminder")
        if submitted:
            remind_dt = datetime.combine(date, time)
            remind_dt = pytz.timezone(DEFAULT_TIMEZONE).localize(remind_dt)
            add_reminder(db, user_id, message, remind_dt)
            st.success("Reminder set!")

    # --- List all upcoming reminders ---
    reminders = get_reminders(db, user_id)
    st.markdown("### Upcoming Reminders")
    upcoming = [r for r in reminders if parse_remind_dt(r["remind_dt"]) >= get_local_now()]
    upcoming = sorted(upcoming, key=lambda r: r["remind_dt"])
    if upcoming:
        for r in upcoming:
            rem_dt = parse_remind_dt(r["remind_dt"])
            st.markdown(f"- **{rem_dt.strftime('%a, %d %b %Y %H:%M')}**: {r['message']}")
            if st.button(f"Delete", key=f"del_{r['id']}"):
                delete_reminder(db, user_id, r["id"])
                st.experimental_rerun()
    else:
        st.info("No upcoming reminders. Set one above!")